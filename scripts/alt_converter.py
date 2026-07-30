#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


GENUI_PROFILE = "genui@0.7.0-alpha.7"
DEFAULT_DSL_NAME = "card.dsl.jsonl"
DEFAULT_ALT_NAME = "card.alt.txt"
DEFAULT_ASC_NAME = "card.asc.txt"
DEFAULT_LAYOUT_REPORT_NAME = "card.layout-report.txt"
DEFAULT_TASKSPEC_NAME = "task.taskSpec.json"
SURFACE_ID = "surface_card"
CATALOG_ID = "ohos.a2ui.extended.catalog"
LAYOUT_TOP_LEVEL_FIELDS = {
    "id", "component", "children", "styles", "itemMargin", "space", "wrap", "vertical"
}
SIMPLE_BINDING_PATTERN = re.compile(r"^\{\{\s*\$\{([^}]+)\}\s*\}\}$")

COMPONENTS = {
    "Text",
    "Image",
    "Divider",
    "Progress",
    "Button",
    "Checkbox",
    "Row",
    "Column",
    "List",
    "Stack",
}
CONTAINERS = {"Row", "Column", "List", "Stack"}
VIRTUAL_COMPONENTS = {"Repeat"}
RING_PROGRESS_TYPES = {"ring", "eclipse", "scaleRing"}
ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
NUMBER_PATTERN = re.compile(r"^-?(?:\d+(?:\.\d*)?|\.\d+)(?:vp|fp|px|%)?$")

MAIN_FROM_DSL = {
    "start": "start",
    "center": "center",
    "end": "end",
    "spaceBetween": "between",
    "spaceAround": "around",
    "spaceEvenly": "evenly",
}
MAIN_TO_DSL = {value: key for key, value in MAIN_FROM_DSL.items()}

ATTRIBUTE_ORDER = [
    "box",
    "size",
    "pad",
    "margin",
    "gap",
    "main",
    "cross",
    "align",
    "wrap",
    "grow",
    "shrink",
    "visible",
    "direction",
    "scroll",
    "axis",
    "len",
    "stroke",
    "font",
    "chars",
    "lines",
    "overflow",
    "text",
    "fit",
    "ratio",
    "type",
    "color",
    "shape",
    "selected",
    "unselected",
    "mark",
    "radius",
    "bg",
    "fg",
    "gradient",
    "border",
    "shadow",
    "style",
    "clip",
    "role",
    "protect",
]

COMMON_NODE_ATTRS = {
    "box",
    "pad",
    "margin",
    "grow",
    "shrink",
    "radius",
    "bg",
    "gradient",
    "border",
    "shadow",
    "style",
    "clip",
    "role",
    "protect",
}
COMPONENT_NODE_ATTRS = {
    "Text": {"font", "lines", "overflow", "text", "fg"},
    "Image": {"size", "fit", "ratio"},
    "Divider": {"axis", "len", "stroke", "color"},
    "Progress": {"size", "type", "color"},
    "Button": {"font", "chars", "fg"},
    "Checkbox": {"shape", "selected", "unselected", "mark"},
    "Row": {"gap", "main", "cross", "wrap"},
    "Column": {"gap", "main", "cross"},
    "List": {"gap", "direction", "scroll"},
    "Stack": {"align"},
    "Repeat": {"visible", "role"},
}


class ConversionError(ValueError):
    pass


@dataclass
class AltNode:
    component: str
    node_id: str
    attrs: dict[str, Any] = field(default_factory=dict)
    children: list["AltNode"] = field(default_factory=list)
    line_number: int = 0


@dataclass
class AltDocument:
    root: AltNode


@dataclass
class ValidationIssue:
    severity: str
    node_id: str
    message: str


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("alt_converter")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


LOGGER = configure_logging()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def format_number(value: float | int) -> str:
    number = float(value)
    if math.isfinite(number) and number.is_integer():
        return str(int(number))
    return format(number, ".6g")


def is_dynamic(value: Any) -> bool:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped.startswith("{{") and stripped.endswith("}}")
    if isinstance(value, dict):
        return any(is_dynamic(child) for child in value.values())
    if isinstance(value, list):
        return any(is_dynamic(child) for child in value)
    return False


def encode_alt_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format_number(value)
    if isinstance(value, (dict, list)):
        return compact_json(value)
    text = str(value)
    if not text or any(character.isspace() for character in text):
        return json.dumps(text, ensure_ascii=False)
    return text


def parse_alt_value(value: str) -> Any:
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if value.startswith(("{", "[", '"')):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConversionError(f"invalid JSON attribute value {value!r}: {exc}") from exc
    if re.fullmatch(r"-?(?:\d+(?:\.\d*)?|\.\d+)", value):
        number = float(value)
        return int(number) if number.is_integer() else number
    return value


def split_alt_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    quote = False
    escaped = False
    depth = 0
    for character in text:
        if quote:
            current.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = False
            continue
        if character == '"':
            quote = True
            current.append(character)
            continue
        if character in "{[(":
            depth += 1
            current.append(character)
            continue
        if character in "}])":
            depth -= 1
            if depth < 0:
                raise ConversionError("unbalanced ALT attribute delimiters")
            current.append(character)
            continue
        if character.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current.clear()
            continue
        current.append(character)
    if quote or depth != 0:
        raise ConversionError("unterminated ALT quote or attribute value")
    if current:
        tokens.append("".join(current))
    return tokens


def normalize_edge(value: Any) -> str | None:
    if value is None or is_dynamic(value):
        return None
    if isinstance(value, (int, float, str)):
        return encode_alt_value(value)
    if isinstance(value, list):
        if len(value) == 1:
            return encode_alt_value(value[0])
        if len(value) == 2:
            return f"{encode_alt_value(value[0])}/{encode_alt_value(value[1])}"
        if len(value) == 4:
            if all(side == value[0] for side in value):
                return encode_alt_value(value[0])
            if value[0] == value[2] and value[1] == value[3]:
                return f"{encode_alt_value(value[0])}/{encode_alt_value(value[1])}"
            return "/".join(encode_alt_value(side) for side in value)
        return encode_alt_value(value)
    if not isinstance(value, dict):
        return encode_alt_value(value)
    if "all" in value:
        return encode_alt_value(value["all"])
    if "vertical" in value or "horizontal" in value:
        vertical = value.get("vertical", 0)
        horizontal = value.get("horizontal", 0)
        return f"{encode_alt_value(vertical)}/{encode_alt_value(horizontal)}"
    sides = [value.get(name, 0) for name in ("top", "right", "bottom", "left")]
    if all(side == sides[0] for side in sides):
        return encode_alt_value(sides[0])
    if sides[0] == sides[2] and sides[1] == sides[3]:
        return f"{encode_alt_value(sides[0])}/{encode_alt_value(sides[1])}"
    return "/".join(encode_alt_value(side) for side in sides)


def parse_edge(value: Any) -> Any:
    if isinstance(value, (int, float, dict)):
        return value
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        if len(value) == 2:
            return {"vertical": value[0], "horizontal": value[1]}
        if len(value) == 4:
            return dict(zip(("top", "right", "bottom", "left"), value))
        raise ConversionError(f"edge array must have 1, 2, or 4 items: {value!r}")
    text = str(value)
    parts = text.split("/")
    parsed = [parse_dimension_token(part) for part in parts]
    if any(part is None for part in parsed):
        raise ConversionError(f"invalid edge value: {value!r}")
    if len(parsed) == 1:
        return parsed[0]
    if len(parsed) == 2:
        return [parsed[0], parsed[1], parsed[0], parsed[1]]
    if len(parsed) == 4:
        return parsed
    raise ConversionError(f"edge value must have 1, 2, or 4 parts: {value!r}")


def parse_dimension_token(value: Any) -> int | float | str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    if text == "auto":
        return None
    if not NUMBER_PATTERN.fullmatch(text):
        return None
    suffix = next((unit for unit in ("vp", "fp", "px", "%") if text.endswith(unit)), "")
    raw = text[: -len(suffix)] if suffix else text
    number = float(raw)
    if suffix:
        return f"{format_number(number)}{suffix}"
    return int(number) if number.is_integer() else number


def numeric_dimension(value: Any) -> float | None:
    parsed = parse_dimension_token(value)
    if isinstance(parsed, (int, float)):
        return float(parsed)
    if isinstance(parsed, str) and parsed.endswith(("vp", "fp", "px")):
        try:
            return float(parsed[:-2])
        except ValueError:
            return None
    return None


def parse_box(value: Any) -> tuple[Any | None, Any | None]:
    text = str(value)
    if "x" not in text:
        raise ConversionError(f"box must use WIDTHxHEIGHT: {value!r}")
    width_text, height_text = text.rsplit("x", 1)
    width = parse_dimension_token(width_text)
    height = parse_dimension_token(height_text)
    if width_text != "auto" and width is None:
        raise ConversionError(f"invalid box width: {width_text!r}")
    if height_text != "auto" and height is None:
        raise ConversionError(f"invalid box height: {height_text!r}")
    return width, height


def edge_numbers(value: Any) -> tuple[float, float, float, float]:
    if value is None:
        return 0.0, 0.0, 0.0, 0.0
    parsed = parse_edge(value)
    if isinstance(parsed, (int, float, str)):
        number = numeric_dimension(parsed) or 0.0
        return number, number, number, number
    if isinstance(parsed, dict):
        if "vertical" in parsed or "horizontal" in parsed:
            vertical = numeric_dimension(parsed.get("vertical", 0)) or 0.0
            horizontal = numeric_dimension(parsed.get("horizontal", 0)) or 0.0
            return vertical, horizontal, vertical, horizontal
        return tuple(
            numeric_dimension(parsed.get(side, 0)) or 0.0
            for side in ("top", "right", "bottom", "left")
        )  # type: ignore[return-value]
    return 0.0, 0.0, 0.0, 0.0


def node_role(node_id: str, component: str) -> str:
    lowered = node_id.lower()
    if node_id == "root":
        return "shell"
    if component == "Button" or any(token in lowered for token in ("action", "button", "cta")):
        return "action"
    if component == "Image":
        return "asset"
    if component == "Checkbox":
        return "selection"
    if component == "Divider":
        return "separator"
    if component == "Progress":
        return "metric"
    if any(token in lowered for token in ("title", "heading")):
        return "title"
    if any(token in lowered for token in ("primary", "hero", "main_value")):
        return "primary"
    if any(token in lowered for token in ("status", "badge")):
        return "status"
    if any(token in lowered for token in ("support", "caption", "subtitle", "hint", "meta", "time", "date")):
        return "support"
    if component in CONTAINERS:
        return "group"
    return component.lower()


def should_protect(node_id: str, component: str, role: str) -> bool:
    if component == "Button" or role in {"title", "primary", "status", "action"}:
        return True
    lowered = node_id.lower()
    return any(token in lowered for token in ("time", "date", "price", "count", "total", "value"))


def add_static_attr(
    attrs: dict[str, Any],
    key: str,
    value: Any,
    diagnostics: list[str],
    source_name: str,
) -> None:
    if value is None:
        return
    if is_dynamic(value):
        diagnostics.append(f"dropped dynamic layout style {source_name}")
        return
    attrs[key] = value


def box_from_styles(styles: dict[str, Any], diagnostics: list[str]) -> tuple[Any | None, Any | None]:
    width = styles.get("width")
    height = styles.get("height")
    if is_dynamic(width):
        diagnostics.append("dropped dynamic layout style styles.width")
        width = None
    if is_dynamic(height):
        diagnostics.append("dropped dynamic layout style styles.height")
        height = None
    return width, height


def extract_alt_attrs(component: dict[str, Any], diagnostics: list[str]) -> dict[str, Any]:
    component_type = str(component.get("component", ""))
    node_id = str(component.get("id", ""))
    styles_value = component.get("styles", {})
    styles = styles_value if isinstance(styles_value, dict) else {}
    attrs: dict[str, Any] = {}
    width, height = box_from_styles(styles, diagnostics)

    if component_type == "Divider":
        vertical = bool(styles.get("vertical", component.get("vertical", False)))
        attrs["axis"] = "v" if vertical else "h"
        length = height if vertical else width
        thickness = styles.get("strokeWidth")
        if thickness is None:
            thickness = width if vertical else height
        if length is not None:
            attrs["len"] = length
        if thickness is not None and not is_dynamic(thickness):
            attrs["stroke"] = thickness
    elif component_type in {"Image", "Progress"} and width is not None and width == height:
        attrs["size"] = width
    elif width is not None or height is not None:
        attrs["box"] = f"{encode_alt_value(width if width is not None else 'auto')}x{encode_alt_value(height if height is not None else 'auto')}"

    padding = normalize_edge(styles.get("padding"))
    margin = normalize_edge(styles.get("margin"))
    if padding is not None:
        attrs["pad"] = padding
    if margin is not None:
        attrs["margin"] = margin

    gap = component.get("space") if component_type == "List" else component.get("itemMargin")
    add_static_attr(attrs, "gap", gap, diagnostics, "space" if component_type == "List" else "itemMargin")

    if "justifyContent" in styles:
        main = MAIN_FROM_DSL.get(str(styles["justifyContent"]), str(styles["justifyContent"]))
        add_static_attr(attrs, "main", main, diagnostics, "styles.justifyContent")
    add_static_attr(attrs, "cross", styles.get("alignItems"), diagnostics, "styles.alignItems")
    add_static_attr(attrs, "align", styles.get("alignContent"), diagnostics, "styles.alignContent")
    add_static_attr(attrs, "wrap", component.get("wrap"), diagnostics, "wrap")
    add_static_attr(attrs, "grow", styles.get("layoutWeight"), diagnostics, "styles.layoutWeight")
    add_static_attr(attrs, "shrink", styles.get("flexShrink"), diagnostics, "styles.flexShrink")

    if component_type in {"Text", "Button"}:
        font_size = styles.get("fontSize")
        font_weight = styles.get("fontWeight")
        if not is_dynamic(font_size) and not is_dynamic(font_weight):
            if font_size is not None and font_weight is not None:
                attrs["font"] = f"{encode_alt_value(font_size)}/{encode_alt_value(font_weight)}"
            elif font_size is not None:
                attrs["font"] = font_size
            elif component_type == "Button":
                attrs["font"] = "16/500"
        elif font_size is not None or font_weight is not None:
            diagnostics.append("dropped dynamic font style")
            if component_type == "Button":
                attrs["font"] = "16/500"

        if component_type == "Button":
            capacity_font = numeric_dimension(font_size) if not is_dynamic(font_size) else None
            capacity_font = capacity_font or 16.0
            capacity_width = numeric_dimension(width)
            if capacity_width is not None:
                attrs["chars"] = max(0, int(math.floor((capacity_width - 24.0) / capacity_font)))

    if component_type == "Text":
        add_static_attr(attrs, "lines", styles.get("maxLines"), diagnostics, "styles.maxLines")
        add_static_attr(attrs, "overflow", styles.get("textOverflow"), diagnostics, "styles.textOverflow")
        add_static_attr(attrs, "text", styles.get("textAlign"), diagnostics, "styles.textAlign")
    elif component_type == "Image":
        add_static_attr(attrs, "fit", styles.get("objectFit"), diagnostics, "styles.objectFit")
        add_static_attr(attrs, "ratio", styles.get("aspectRatio"), diagnostics, "styles.aspectRatio")
    elif component_type == "Progress":
        add_static_attr(attrs, "type", styles.get("type"), diagnostics, "styles.type")
        add_static_attr(attrs, "color", styles.get("color"), diagnostics, "styles.color")
    elif component_type == "Divider":
        add_static_attr(attrs, "color", styles.get("color"), diagnostics, "styles.color")
    elif component_type == "Checkbox":
        add_static_attr(attrs, "shape", styles.get("shape"), diagnostics, "styles.shape")
        add_static_attr(attrs, "selected", styles.get("selectedColor"), diagnostics, "styles.selectedColor")
        unselected = styles.get("unselectedColor", styles.get("unSelectedColor"))
        add_static_attr(attrs, "unselected", unselected, diagnostics, "styles.unselectedColor")
        mark = styles.get("mark")
        if isinstance(mark, dict) and not is_dynamic(mark):
            mark_size = mark.get("size", 20)
            mark_width = mark.get("strokeWidth", 2)
            mark_color = mark.get("strokeColor", "#FFFFFFFF")
            attrs["mark"] = "/".join(
                encode_alt_value(item) for item in (mark_size, mark_width, mark_color)
            )
    elif component_type == "List":
        add_static_attr(attrs, "direction", styles.get("listDirection"), diagnostics, "styles.listDirection")
        add_static_attr(attrs, "scroll", styles.get("scrollBar"), diagnostics, "styles.scrollBar")

    add_static_attr(attrs, "radius", styles.get("borderRadius"), diagnostics, "styles.borderRadius")
    add_static_attr(attrs, "bg", styles.get("backgroundColor"), diagnostics, "styles.backgroundColor")
    if component_type in {"Text", "Button"}:
        add_static_attr(attrs, "fg", styles.get("fontColor"), diagnostics, "styles.fontColor")
    add_static_attr(attrs, "gradient", styles.get("linearGradient"), diagnostics, "styles.linearGradient")
    border_width = styles.get("borderWidth")
    border_color = styles.get("borderColor")
    if border_width is not None and not is_dynamic(border_width) and not is_dynamic(border_color):
        attrs["border"] = (
            f"{encode_alt_value(border_width)}/{encode_alt_value(border_color)}"
            if border_color is not None
            else encode_alt_value(border_width)
        )
    add_static_attr(attrs, "shadow", styles.get("shadow"), diagnostics, "styles.shadow")
    if styles.get("clip") is True:
        attrs["clip"] = True

    role = node_role(node_id, component_type)
    attrs["role"] = role
    if should_protect(node_id, component_type, role):
        attrs["protect"] = True
    _, represented_styles = apply_alt_styles(AltNode(component_type, node_id, copy.deepcopy(attrs)))
    extra_styles: dict[str, Any] = {}
    for key, value in styles.items():
        represented = represented_styles.get(key)
        if key in {"padding", "margin"} and key in represented_styles:
            if normalize_edge(value) == normalize_edge(represented):
                continue
        elif key in represented_styles and represented == value:
            continue
        extra_styles[key] = copy.deepcopy(value)
    if extra_styles:
        attrs["style"] = extra_styles
    return attrs


def parse_jsonl_messages(text: str, source: str = "DSL") -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 3:
        raise ConversionError(f"GenUI DSL must contain exactly 3 non-empty JSONL lines, got {len(lines)}")
    messages: list[dict[str, Any]] = []
    for index, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConversionError(f"invalid JSON on {source} line {index}: {exc}") from exc
        if not isinstance(value, dict):
            raise ConversionError(f"DSL line {index} must be a JSON object")
        messages.append(value)
    expected = ("createSurface", "updateComponents", "updateDataModel")
    for index, key in enumerate(expected):
        if key not in messages[index]:
            raise ConversionError(f"DSL line {index + 1} must contain {key}")
    return messages[0], messages[1], messages[2]


def read_jsonl_messages(path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not path.is_file():
        raise ConversionError(f"DSL file does not exist: {path}")
    return parse_jsonl_messages(path.read_text(encoding="utf-8-sig"), str(path))


def validate_restored_content(document: AltDocument, dsl_text: str) -> None:
    nodes: dict[str, AltNode] = {}

    def collect(node: AltNode) -> None:
        if node.component != "Repeat":
            nodes[node.node_id] = node
        for child in node.children:
            collect(child)

    collect(document.root)
    _, update_message, _ = parse_jsonl_messages(dsl_text, "ASC-restored DSL")
    components = update_message.get("updateComponents", {}).get("components", [])
    for component in components:
        if not isinstance(component, dict):
            continue
        node = nodes.get(str(component.get("id", "")))
        if node is None or node.component != "Button":
            continue
        label = component.get("label", "")
        if not isinstance(label, str) or is_dynamic(label):
            raise ConversionError(
                f"{node.node_id}: model-generated Button label must be a bounded static string"
            )
        chars = node.attrs.get("chars")
        if not isinstance(chars, int) or len(label) > chars:
            raise ConversionError(
                f"{node.node_id}: Button label {label!r} contains {len(label)} characters "
                f"but ALT chars={chars!r}"
            )
        width, _ = node_box(node, intrinsic=False)
        required_width = estimated_text_width(label, node_font_size(node, 16.0)) + 24.0
        if width is None or width + 0.01 < required_width:
            raise ConversionError(
                f"{node.node_id}: Button width cannot contain label {label!r}; "
                f"requires at least {required_width:g}vp"
            )


def size_from_surface(create_message: dict[str, Any]) -> str:
    surface = create_message.get("createSurface")
    if not isinstance(surface, dict):
        raise ConversionError("createSurface must be an object")
    width = surface.get("width")
    height = surface.get("height")
    if width == 140 and height == 140:
        return "2x2"
    if width == 300 and height == 140:
        return "2x4"
    raise ConversionError(f"unsupported surface size: {width}x{height}")


def pointer_get(root: Any, pointer: str) -> Any:
    if pointer in {"", "/"}:
        return root
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    current = root
    for raw_part in pointer.strip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def dsl_to_alt(path: Path, task_spec: dict[str, Any] | None) -> tuple[AltDocument, str, list[str], int]:
    create_message, update_message, data_message = read_jsonl_messages(path)
    size = size_from_surface(create_message)
    if task_spec is not None and task_spec.get("size") not in {None, size}:
        raise ConversionError(
            f"TaskSpec.size {task_spec.get('size')!r} does not match DSL surface size {size!r}"
        )
    update = update_message.get("updateComponents")
    if not isinstance(update, dict):
        raise ConversionError("updateComponents must be an object")
    root_id = update.get("root")
    components_value = update.get("components")
    if not isinstance(root_id, str) or not root_id:
        raise ConversionError("updateComponents.root must be a non-empty string")
    if not isinstance(components_value, list):
        raise ConversionError("updateComponents.components must be an array")

    component_map: dict[str, dict[str, Any]] = {}
    for component in components_value:
        if not isinstance(component, dict):
            raise ConversionError("every component must be an object")
        node_id = component.get("id")
        component_type = component.get("component")
        if not isinstance(node_id, str) or not ID_PATTERN.fullmatch(node_id):
            raise ConversionError(f"invalid component id: {node_id!r}")
        if component_type not in COMPONENTS:
            raise ConversionError(f"unsupported component {component_type!r} on node {node_id!r}")
        if node_id in component_map:
            raise ConversionError(f"duplicate component id: {node_id}")
        component_map[node_id] = component
    if root_id not in component_map:
        raise ConversionError(f"root component does not exist: {root_id}")

    diagnostics: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    parent_of: dict[str, str] = {}
    data_model = data_message.get("updateDataModel", {}).get("value", {})

    def build(node_id: str, parent_id: str | None = None) -> AltNode:
        if node_id in visiting:
            raise ConversionError(f"component cycle detected at {node_id}")
        if parent_id is not None and node_id in parent_of and parent_of[node_id] != parent_id:
            raise ConversionError(
                f"component {node_id} has multiple parents: {parent_of[node_id]} and {parent_id}"
            )
        if node_id not in component_map:
            raise ConversionError(f"component reference does not exist: {node_id}")
        if parent_id is not None:
            parent_of[node_id] = parent_id
        visiting.add(node_id)
        source = component_map[node_id]
        node = AltNode(
            component=str(source["component"]),
            node_id=node_id,
            attrs=extract_alt_attrs(source, diagnostics),
        )
        children = source.get("children")
        if isinstance(children, list):
            for child_id in children:
                if not isinstance(child_id, str):
                    raise ConversionError(f"{node_id}.children must contain component IDs")
                node.children.append(build(child_id, node_id))
        elif isinstance(children, dict):
            template_id = children.get("componentId")
            collection_path = children.get("path")
            if not isinstance(template_id, str) or not isinstance(collection_path, str):
                raise ConversionError(f"{node_id}.children template must contain componentId and path")
            collection = pointer_get(data_model, collection_path)
            visible = len(collection) if isinstance(collection, list) else 1
            repeat_id = f"{node_id}_items"
            repeat = AltNode(
                component="Repeat",
                node_id=repeat_id,
                attrs={"visible": max(1, visible), "role": "collection"},
            )
            repeat.children.append(build(template_id, repeat_id))
            node.children.append(repeat)
        elif children is not None:
            raise ConversionError(f"{node_id}.children must be an array or template object")
        visiting.remove(node_id)
        visited.add(node_id)
        return node

    root = build(root_id)
    orphan_count = len(set(component_map) - visited)
    return AltDocument(root), size, diagnostics, orphan_count


def alt_nodes(document: AltDocument) -> list[AltNode]:
    nodes: list[AltNode] = []

    def visit(node: AltNode) -> None:
        if node.component != "Repeat":
            nodes.append(node)
        for child in node.children:
            visit(child)

    visit(document.root)
    return nodes


def binding_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = SIMPLE_BINDING_PATTERN.fullmatch(value.strip())
    return match.group(1) if match else None


def semantic_attrs(
    component: dict[str, Any],
    task_spec: dict[str, Any],
) -> dict[str, Any]:
    component_type = str(component.get("component", ""))
    semantic = {
        key: copy.deepcopy(value)
        for key, value in component.items()
        if key not in LAYOUT_TOP_LEVEL_FIELDS
    }
    attrs: dict[str, Any] = {}

    content = semantic.pop("content", None)
    if content is not None:
        path = binding_path(content)
        if path is not None:
            attrs["bind"] = path
        elif is_dynamic(content):
            attrs["expr"] = content
        else:
            attrs["text"] = content

    src = semantic.pop("src", None)
    if src is not None:
        matched_asset = None
        for index, candidate in enumerate(task_spec.get("assetCandidates", [])):
            if not isinstance(candidate, dict):
                continue
            bind_to = candidate.get("bindTo")
            if src == candidate.get("src") or (
                isinstance(bind_to, str) and binding_path(src) == bind_to
            ):
                matched_asset = index
                break
        if matched_asset is not None:
            attrs["asset"] = matched_asset
        else:
            path = binding_path(src)
            if path is not None:
                attrs["bind"] = path
            elif is_dynamic(src):
                attrs["expr"] = src
            else:
                attrs["src"] = src

    on_click = semantic.pop("onClick", None)
    if on_click is not None:
        matched_event = None
        for index, candidate in enumerate(task_spec.get("eventCandidates", [])):
            if on_click == [candidate]:
                matched_event = index
                break
        attrs["event" if matched_event is not None else "onClick"] = (
            matched_event if matched_event is not None else on_click
        )

    select = semantic.pop("select", None)
    if select is not None:
        path = binding_path(select)
        attrs["bind" if path is not None else "select"] = path if path is not None else select

    for key in ("value", "total"):
        if key not in semantic:
            continue
        value = semantic.pop(key)
        path = binding_path(value) if component_type == "Progress" else None
        attrs[key] = path if path is not None else value

    attrs.update(semantic)
    return attrs


def build_asc(
    original: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
    document: AltDocument,
    task_spec: dict[str, Any],
) -> str:
    update = original[1].get("updateComponents", {})
    components = update.get("components", []) if isinstance(update, dict) else []
    component_map = {
        component["id"]: component
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    lines: list[str] = []
    for node in alt_nodes(document):
        component = component_map[node.node_id]
        attrs = semantic_attrs(component, task_spec)
        if not attrs:
            continue
        tokens = [node.component, node.node_id]
        for key, value in attrs.items():
            tokens.append(f"{key}={encode_alt_value(value)}")
        lines.append(" ".join(tokens))
    return "\n".join(lines).rstrip() + "\n"


def parse_asc(path: Path, document: AltDocument) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise ConversionError(f"ASC file does not exist: {path}")
    nodes = alt_nodes(document)
    node_map = {node.node_id: node for node in nodes}
    node_order = {node.node_id: index for index, node in enumerate(nodes)}
    result: dict[str, dict[str, Any]] = {}
    previous = -1
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        tokens = split_alt_tokens(line.strip())
        if len(tokens) < 3:
            raise ConversionError(f"ASC line {line_number} must contain component, id, and properties")
        component_type, node_id = tokens[:2]
        node = node_map.get(node_id)
        if node is None or node.component != component_type:
            raise ConversionError(f"ASC line {line_number} does not map to the matching ALT node")
        if node_id in result or node_order[node_id] <= previous:
            raise ConversionError("ASC nodes must be unique and follow ALT preorder")
        attrs: dict[str, Any] = {}
        for token in tokens[2:]:
            if "=" not in token:
                raise ConversionError(f"ASC line {line_number} contains invalid property {token!r}")
            key, raw_value = token.split("=", 1)
            if key in {"styles", "style", "id", "component", "children"}:
                raise ConversionError(f"ASC cannot contain layout/style field {key!r}")
            attrs[key] = parse_alt_value(raw_value)
        result[node_id] = attrs
        previous = node_order[node_id]
    return result


def apply_asc_to_dsl(
    base_text: str,
    document: AltDocument,
    task_spec: dict[str, Any],
    asc: dict[str, dict[str, Any]],
) -> str:
    messages = list(parse_jsonl_messages(base_text, "generated base DSL"))
    components = messages[1]["updateComponents"]["components"]
    for component in components:
        node_id = component["id"]
        for key in list(component):
            if key not in LAYOUT_TOP_LEVEL_FIELDS:
                del component[key]
        attrs = asc.get(node_id, {})
        component_type = component["component"]
        for key, value in attrs.items():
            if key == "text":
                component["content"] = value
            elif key == "bind":
                target = "select" if component_type == "Checkbox" else "src" if component_type == "Image" else "content"
                component[target] = f"{{{{ ${{{value}}} }}}}"
            elif key == "expr":
                target = "src" if component_type == "Image" else "content"
                component[target] = value
            elif key == "asset":
                candidates = task_spec.get("assetCandidates", [])
                if not isinstance(value, int) or value < 0 or value >= len(candidates):
                    raise ConversionError(f"{node_id}: invalid ASC asset index {value!r}")
                candidate = candidates[value]
                bind_to = candidate.get("bindTo") if isinstance(candidate, dict) else None
                component["src"] = f"{{{{ ${{{bind_to}}} }}}}" if isinstance(bind_to, str) else candidate["src"]
            elif key == "event":
                candidates = task_spec.get("eventCandidates", [])
                if not isinstance(value, int) or value < 0 or value >= len(candidates):
                    raise ConversionError(f"{node_id}: invalid ASC event index {value!r}")
                component["onClick"] = [copy.deepcopy(candidates[value])]
            elif key == "onClick":
                component["onClick"] = value
            elif key in {"value", "total"} and component_type == "Progress" and isinstance(value, str) and value.startswith("/"):
                component[key] = f"{{{{ ${{{value}}} }}}}"
            elif key == "select":
                component["select"] = value
            else:
                component[key] = value
    return "\n".join(compact_json(message) for message in messages) + "\n"


def ordered_attrs(attrs: dict[str, Any]) -> Iterable[tuple[str, Any]]:
    emitted: set[str] = set()
    for key in ATTRIBUTE_ORDER:
        if key in attrs:
            emitted.add(key)
            yield key, attrs[key]
    for key in sorted(set(attrs) - emitted):
        yield key, attrs[key]


def serialize_alt(document: AltDocument) -> str:
    lines: list[str] = []

    def emit(node: AltNode, depth: int) -> None:
        tokens = [node.component, node.node_id]
        for key, value in ordered_attrs(node.attrs):
            if key in {"clip", "protect"} and value is True:
                tokens.append(key)
            elif value is not None:
                tokens.append(f"{key}={encode_alt_value(value)}")
        lines.append("  " * depth + " ".join(tokens))
        for child in node.children:
            emit(child, depth + 1)

    emit(document.root, 0)
    return "\n".join(lines).rstrip() + "\n"


def parse_alt(path: Path) -> AltDocument:
    if not path.is_file():
        raise ConversionError(f"ALT file does not exist: {path}")
    raw_lines = path.read_text(encoding="utf-8-sig").splitlines()
    content = [(index, line) for index, line in enumerate(raw_lines, 1) if line.strip()]
    if not content:
        raise ConversionError("ALT file is empty")
    roots: list[AltNode] = []
    stack: list[AltNode] = []
    seen_ids: set[str] = set()
    for line_number, line in content:
        if "\t" in line[: len(line) - len(line.lstrip())]:
            raise ConversionError(f"line {line_number}: ALT indentation cannot contain tabs")
        leading = len(line) - len(line.lstrip(" "))
        if leading % 2 != 0:
            raise ConversionError(f"line {line_number}: indentation must use two spaces per level")
        depth = leading // 2
        tokens = split_alt_tokens(line.strip())
        if len(tokens) < 2:
            raise ConversionError(f"line {line_number}: node must contain component and id")
        component, node_id = tokens[0], tokens[1]
        if component not in COMPONENTS | VIRTUAL_COMPONENTS:
            raise ConversionError(f"line {line_number}: unsupported component {component!r}")
        if not ID_PATTERN.fullmatch(node_id):
            raise ConversionError(f"line {line_number}: invalid node id {node_id!r}")
        if node_id in seen_ids:
            raise ConversionError(f"line {line_number}: duplicate node id {node_id!r}")
        attrs: dict[str, Any] = {}
        for token in tokens[2:]:
            if "=" in token:
                key, raw_value = token.split("=", 1)
                if not key:
                    raise ConversionError(f"line {line_number}: empty attribute name")
                attrs[key] = parse_alt_value(raw_value)
            elif token in {"clip", "protect"}:
                attrs[token] = True
            else:
                raise ConversionError(f"line {line_number}: unknown flag {token!r}")
        if component == "Repeat":
            allowed_attrs = COMPONENT_NODE_ATTRS[component]
        elif component == "Divider":
            allowed_attrs = (COMMON_NODE_ATTRS - {"box"}) | COMPONENT_NODE_ATTRS[component]
        else:
            allowed_attrs = COMMON_NODE_ATTRS | COMPONENT_NODE_ATTRS[component]
        unknown_attrs = sorted(set(attrs) - allowed_attrs)
        if unknown_attrs:
            raise ConversionError(
                f"line {line_number}: {component} does not support ALT attribute(s): "
                + ", ".join(unknown_attrs)
            )
        node = AltNode(component, node_id, attrs, line_number=line_number)
        seen_ids.add(node_id)
        if depth == 0:
            roots.append(node)
            stack = [node]
        else:
            if depth > len(stack):
                raise ConversionError(f"line {line_number}: indentation jumps over a parent level")
            stack = stack[:depth]
            if not stack:
                raise ConversionError(f"line {line_number}: node has no parent")
            stack[-1].children.append(node)
            stack.append(node)
    if len(roots) != 1:
        raise ConversionError(f"ALT must contain exactly one root node, got {len(roots)}")
    return AltDocument(roots[0])


def node_box(node: AltNode, intrinsic: bool = True) -> tuple[float | None, float | None]:
    if "size" in node.attrs:
        size = numeric_dimension(node.attrs["size"])
        return size, size
    if "box" in node.attrs:
        width_value, height_value = parse_box(node.attrs["box"])
        width = numeric_dimension(width_value)
        height = numeric_dimension(height_value)
    else:
        width = height = None
    if intrinsic and node.component == "Checkbox":
        height = max(height or 0.0, 48.0)
        width = max(width or 0.0, 36.0)
    return width, height


def validate_layout(document: AltDocument, size: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected = (140.0, 140.0) if size == "2x2" else (300.0, 140.0)
    root_width, root_height = node_box(document.root, intrinsic=False)
    if document.root.component not in {"Row", "Column", "Stack"}:
        issues.append(
            ValidationIssue("error", document.root.node_id, "root must be Row, Column, or Stack")
        )
    if root_width is None or root_height is None:
        issues.append(ValidationIssue("error", document.root.node_id, "root must declare a numeric box"))
    elif (root_width, root_height) != expected:
        issues.append(
            ValidationIssue(
                "error",
                document.root.node_id,
                f"root box {root_width:g}x{root_height:g} does not match {size} canvas {expected[0]:g}x{expected[1]:g}",
            )
        )
    if "pad" not in document.root.attrs:
        issues.append(ValidationIssue("error", document.root.node_id, "root must declare pad=12"))
    if "radius" not in document.root.attrs:
        issues.append(ValidationIssue("error", document.root.node_id, "root must declare radius"))
    if document.root.attrs.get("clip") is not True:
        issues.append(ValidationIssue("error", document.root.node_id, "root must declare clip"))
    if not any(key in document.root.attrs for key in ("bg", "gradient")):
        issues.append(ValidationIssue("error", document.root.node_id, "root must declare bg or gradient"))

    def visit(node: AltNode, parent: AltNode | None = None) -> None:
        width, height = node_box(node, intrinsic=False)
        if node.children and node.component not in CONTAINERS | VIRTUAL_COMPONENTS:
            issues.append(
                ValidationIssue("error", node.node_id, f"{node.component} cannot contain ALT child nodes")
            )
        if node.component == "Checkbox":
            if height is not None and height < 48:
                issues.append(
                    ValidationIssue(
                        "error",
                        node.node_id,
                        f"Checkbox outer height {height:g} is smaller than intrinsic 48vp",
                    )
                )
            if width is not None and width < 36:
                issues.append(
                    ValidationIssue(
                        "error",
                        node.node_id,
                        f"Checkbox width {width:g} cannot contain the fixed 20vp control and 16vp margins/gap",
                    )
                )
            if any(key in node.attrs for key in ("font", "lines", "overflow")):
                issues.append(
                    ValidationIssue(
                        "error",
                        node.node_id,
                        "Checkbox cannot control its internal label font, lines, or overflow through ALT",
                    )
                )
            if "mark" in node.attrs:
                try:
                    mark_size = numeric_dimension(str(node.attrs["mark"]).split("/", 1)[0])
                except (TypeError, ValueError):
                    mark_size = None
                if mark_size is not None and mark_size > 20:
                    issues.append(
                        ValidationIssue(
                            "error",
                            node.node_id,
                            f"Checkbox mark size {mark_size:g} exceeds the fixed 20vp control",
                        )
                    )

        if node.component == "Progress" and str(node.attrs.get("type", "linear")) in RING_PROGRESS_TYPES:
            if width is not None and height is not None and not math.isclose(width, height):
                issues.append(
                    ValidationIssue("error", node.node_id, "ring-like Progress must have equal width and height")
                )

        if node.component == "Button":
            font_size = 16.0
            if "font" in node.attrs:
                font_size = numeric_dimension(str(node.attrs["font"]).split("/", 1)[0]) or font_size
            else:
                issues.append(ValidationIssue("error", node.node_id, "Button must declare font=SIZE/WEIGHT"))
            chars = node.attrs.get("chars")
            if not isinstance(chars, int) or isinstance(chars, bool) or chars < 1:
                issues.append(ValidationIssue("error", node.node_id, "Button chars must be an integer of at least 1"))
            if width is not None and isinstance(chars, int):
                capacity = max(0, int(math.floor((width - 24.0) / font_size)))
                if chars > capacity:
                    issues.append(
                        ValidationIssue(
                            "error",
                            node.node_id,
                            f"Button chars={chars} exceeds box/font capacity {capacity}",
                        )
                    )
            minimum = max(32.0, font_size + 16.0)
            if height is not None and height < minimum:
                issues.append(
                    ValidationIssue(
                        "error",
                        node.node_id,
                        f"Button height {height:g} is smaller than the {minimum:g}vp intrinsic minimum",
                    )
                )

        main = str(node.attrs.get("main", ""))
        if main in {"between", "around", "evenly"} and "gap" in node.attrs:
            issues.append(
                ValidationIssue(
                    "error",
                    node.node_id,
                    f"main={main} cannot be combined with a fixed gap",
                )
            )

        if node.component in {"Row", "Column", "Stack"} and node.children:
            parent_width, parent_height = node_box(node)
            top, right, bottom, left = edge_numbers(node.attrs.get("pad"))
            inner_width = None if parent_width is None else max(0.0, parent_width - left - right)
            inner_height = None if parent_height is None else max(0.0, parent_height - top - bottom)
            child_boxes = [node_box(child) for child in node.children]
            child_margins = [edge_numbers(child.attrs.get("margin")) for child in node.children]
            gap = numeric_dimension(node.attrs.get("gap", 0)) or 0.0
            if node.component == "Row" and inner_width is not None and all(box[0] is not None for box in child_boxes):
                required = sum(
                    (box[0] or 0.0) + margin[1] + margin[3]
                    for box, margin in zip(child_boxes, child_margins)
                ) + gap * max(0, len(child_boxes) - 1)
                if required > inner_width + 0.01:
                    issues.append(
                        ValidationIssue(
                            "error",
                            node.node_id,
                            f"Row requires {required:g}vp horizontally but only {inner_width:g}vp is available",
                        )
                    )
            if node.component == "Row" and inner_height is not None and all(box[1] is not None for box in child_boxes):
                required = max(
                    (box[1] or 0.0) + margin[0] + margin[2]
                    for box, margin in zip(child_boxes, child_margins)
                )
                if required > inner_height + 0.01:
                    issues.append(
                        ValidationIssue(
                            "error",
                            node.node_id,
                            f"Row requires {required:g}vp vertically but only {inner_height:g}vp is available",
                        )
                    )
            if node.component == "Column" and inner_height is not None and all(box[1] is not None for box in child_boxes):
                required = sum(
                    (box[1] or 0.0) + margin[0] + margin[2]
                    for box, margin in zip(child_boxes, child_margins)
                ) + gap * max(0, len(child_boxes) - 1)
                if required > inner_height + 0.01:
                    issues.append(
                        ValidationIssue(
                            "error",
                            node.node_id,
                            f"Column requires {required:g}vp vertically but only {inner_height:g}vp is available",
                        )
                    )
            if node.component == "Column" and inner_width is not None and all(box[0] is not None for box in child_boxes):
                required = max(
                    (box[0] or 0.0) + margin[1] + margin[3]
                    for box, margin in zip(child_boxes, child_margins)
                )
                if required > inner_width + 0.01:
                    issues.append(
                        ValidationIssue(
                            "error",
                            node.node_id,
                            f"Column requires {required:g}vp horizontally but only {inner_width:g}vp is available",
                        )
                    )
            if node.component == "Stack":
                for child, box, margin in zip(node.children, child_boxes, child_margins):
                    child_width = None if box[0] is None else box[0] + margin[1] + margin[3]
                    child_height = None if box[1] is None else box[1] + margin[0] + margin[2]
                    if inner_width is not None and child_width is not None and child_width > inner_width + 0.01:
                        issues.append(
                            ValidationIssue(
                                "error",
                                child.node_id,
                                f"Stack child width {child_width:g} exceeds {node.node_id} inner width {inner_width:g}",
                            )
                        )
                    if inner_height is not None and child_height is not None and child_height > inner_height + 0.01:
                        issues.append(
                            ValidationIssue(
                                "error",
                                child.node_id,
                                f"Stack child height {child_height:g} exceeds {node.node_id} inner height {inner_height:g}",
                            )
                        )
        if node.component == "Repeat":
            if parent is None or parent.component not in {"Row", "Column", "List"}:
                issues.append(
                    ValidationIssue("error", node.node_id, "Repeat parent must be Row, Column, or List")
                )
            if len(node.children) != 1:
                issues.append(
                    ValidationIssue("error", node.node_id, "Repeat must contain exactly one template component")
                )
            visible = node.attrs.get("visible", 1)
            if not isinstance(visible, (int, float)) or visible < 1:
                issues.append(ValidationIssue("error", node.node_id, "Repeat.visible must be at least 1"))
        for child in node.children:
            visit(child, node)

    visit(document.root)
    return issues


def layout_issue_code(message: str) -> str:
    lowered = message.lower()
    if "requires" in lowered and "available" in lowered:
        return "container_overflow"
    if "stack child" in lowered and "exceeds" in lowered:
        return "stack_child_overflow"
    if "checkbox" in lowered and ("intrinsic" in lowered or "fixed" in lowered):
        return "checkbox_intrinsic_overflow"
    if "button" in lowered and "capacity" in lowered:
        return "button_text_overflow"
    if "button height" in lowered and "intrinsic minimum" in lowered:
        return "button_intrinsic_overflow"
    if "progress" in lowered and "equal width and height" in lowered:
        return "progress_aspect_mismatch"
    if "cannot be combined with a fixed gap" in lowered:
        return "conflicting_spacing"
    if lowered.startswith("root "):
        return "invalid_root_layout"
    if "cannot contain alt child nodes" in lowered:
        return "invalid_child_layout"
    if lowered.startswith("repeat"):
        return "invalid_repeat_layout"
    return "layout_constraint"


def build_layout_report(
    case_name: str,
    size: str,
    alt_name: str,
    dsl_name: str,
    document: AltDocument,
    issues: list[ValidationIssue],
) -> str:
    components = {node.node_id: node.component for node in alt_nodes(document)}
    counts = {"error": 0, "warning": 0}
    entries: list[dict[str, Any]] = []
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
        entries.append(
            {
                "code": layout_issue_code(issue.message),
                "severity": issue.severity,
                "nodeId": issue.node_id,
                "component": components.get(issue.node_id),
                "message": issue.message,
            }
        )
    report = {
        "case": case_name,
        "size": size,
        "sourceAlt": alt_name,
        "generatedDsl": dsl_name,
        "status": "issues" if issues else "pass",
        "summary": {
            "total": len(issues),
            "errors": counts.get("error", 0),
            "warnings": counts.get("warning", 0),
        },
        "issues": entries,
    }
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def load_task_spec(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConversionError(f"TaskSpec file does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ConversionError(f"invalid TaskSpec JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ConversionError("TaskSpec must be a JSON object")
    if value.get("size") not in {"2x2", "2x4"}:
        raise ConversionError("TaskSpec.size must be 2x2 or 2x4")
    if not isinstance(value.get("dataModelSchema"), dict):
        raise ConversionError("TaskSpec.dataModelSchema must be an object")
    if not isinstance(value.get("eventCandidates", []), list):
        raise ConversionError("TaskSpec.eventCandidates must be an array")
    if not isinstance(value.get("assetCandidates", []), list):
        raise ConversionError("TaskSpec.assetCandidates must be an array")
    slots = value.get("presentationSlots")
    if slots is not None and not isinstance(slots, dict):
        raise ConversionError("TaskSpec.presentationSlots must be an object when present")
    return value


def sample_data_model(schema: Any) -> Any:
    if isinstance(schema, dict):
        if "sampleValue" in schema:
            return schema["sampleValue"]
        if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
            return [sample_data_model(schema["items"])]
        if isinstance(schema.get("properties"), dict):
            return sample_data_model(schema["properties"])
        result: dict[str, Any] = {}
        for key, child in schema.items():
            if key in {"type", "description"} and "type" in schema:
                continue
            result[key] = sample_data_model(child)
        return result
    if isinstance(schema, list):
        return [sample_data_model(item) for item in schema]
    return schema


def escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def flatten_values(value: Any, pointer: str = "") -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(flatten_values(child, pointer + "/" + escape_pointer_token(str(key))))
    elif isinstance(value, list):
        if value:
            result.extend(flatten_values(value[0], pointer + "/0"))
        else:
            result.append((pointer, value))
    else:
        result.append((pointer or "/", value))
    return result


def flatten_collections(value: Any, pointer: str = "") -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(flatten_collections(child, pointer + "/" + escape_pointer_token(str(key))))
    elif isinstance(value, list):
        result.append(pointer or "/")
        if value:
            result.extend(flatten_collections(value[0], pointer + "/0"))
    return result


def identifier_tokens(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return {token.lower() for token in re.split(r"[^A-Za-z0-9]+", expanded) if token}


def find_best_value(
    node: AltNode,
    values: list[tuple[str, Any]],
    expected: str,
    used_paths: set[str],
) -> str | None:
    node_tokens = identifier_tokens(node.node_id)
    ignored = {"text", "label", "value", "item", "row", "column", "image", "icon", "button"}
    node_tokens -= ignored
    best: tuple[int, str] | None = None
    for pointer, value in values:
        if pointer in used_paths:
            continue
        if expected == "bool" and not isinstance(value, bool):
            continue
        if expected == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            continue
        if expected == "text" and isinstance(value, (dict, list, bool)):
            continue
        path_tokens = identifier_tokens(pointer)
        leaf = pointer.rsplit("/", 1)[-1].lower()
        score = len(node_tokens & path_tokens) * 20
        if leaf in node_tokens:
            score += 50
        if node.node_id.lower().endswith(leaf):
            score += 20
        if best is None or score > best[0]:
            best = (score, pointer)
    if best is None or best[0] < 20:
        return None
    used_paths.add(best[1])
    return best[1]


def source_expression(source: Any, repeat_context: bool = False) -> Any:
    if not isinstance(source, str) or not source:
        return None
    if source.startswith("{{"):
        return source
    if source.startswith("/"):
        return f"{{{{ ${{{source}}} }}}}"
    if repeat_context:
        return f"{{{{ ${{{source}}} }}}}"
    return source


def humanize_id(node_id: str, component: str) -> str:
    lowered = node_id.lower()
    if component == "Button":
        return "查看"
    labels = {
        "title": "标题",
        "status": "状态",
        "time": "时间",
        "date": "日期",
        "value": "数值",
        "support": "信息",
        "caption": "说明",
    }
    for token, label in labels.items():
        if token in lowered:
            return label
    cleaned = re.sub(
        r"_(text|label|value|caption|button|image|icon|row|column|panel|group)$",
        "",
        node_id,
        flags=re.IGNORECASE,
    )
    return cleaned.replace("_", " ") or "信息"


def estimated_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for character in text:
        if character.isspace():
            width += font_size * 0.35
        elif ord(character) > 127:
            width += font_size
        elif character.isalnum():
            width += font_size * 0.6
        else:
            width += font_size * 0.45
    return width


def node_font_size(node: AltNode, fallback: float) -> float:
    if "font" not in node.attrs:
        return fallback
    return numeric_dimension(str(node.attrs["font"]).split("/", 1)[0]) or fallback


class SemanticResolver:
    def __init__(self, task_spec: dict[str, Any]):
        self.task_spec = task_spec
        self.data_model = sample_data_model(task_spec["dataModelSchema"])
        self.values = flatten_values(self.data_model)
        self.collections = flatten_collections(self.data_model)
        self.slots = task_spec.get("presentationSlots", {})
        self.events = task_spec.get("eventCandidates", [])
        self.assets = task_spec.get("assetCandidates", [])
        self.used_paths: set[str] = set()
        self.warnings: list[str] = []

    def slot(self, node_id: str) -> dict[str, Any]:
        value = self.slots.get(node_id, {}) if isinstance(self.slots, dict) else {}
        return value if isinstance(value, dict) else {}

    def text(self, node: AltNode, repeat_context: bool) -> Any:
        slot = self.slot(node.node_id)
        if "value" in slot:
            return slot["value"]
        if "source" in slot:
            return source_expression(slot["source"], repeat_context)
        generic_static_ids = {"title", "title_text", "header_title", "card_title"}
        pointer = None
        if node.node_id.lower() not in generic_static_ids:
            pointer = find_best_value(node, self.values, "text", self.used_paths)
        if pointer:
            self.warnings.append(f"{node.node_id}: matched Text to schema path {pointer} by node ID")
            return source_expression(pointer)
        fallback = humanize_id(node.node_id, node.component)
        self.warnings.append(f"{node.node_id}: no presentation slot; using fallback text {fallback!r}")
        return fallback

    def image(self, node: AltNode) -> str:
        slot = self.slot(node.node_id)
        if isinstance(slot.get("src"), str):
            return slot["src"]
        asset_index = slot.get("assetCandidate")
        if isinstance(asset_index, int) and 0 <= asset_index < len(self.assets):
            source = self.assets[asset_index].get("src")
            if isinstance(source, str) and source:
                return source
        node_tokens = identifier_tokens(node.node_id)
        best: tuple[int, str] | None = None
        for asset in self.assets:
            if not isinstance(asset, dict) or not isinstance(asset.get("src"), str):
                continue
            haystack = str(asset.get("src", "")) + " " + str(asset.get("description", ""))
            score = len(node_tokens & identifier_tokens(haystack)) * 20
            candidate = (score, asset["src"])
            if best is None or candidate[0] > best[0]:
                best = candidate
        if best is None:
            raise ConversionError(f"{node.node_id}: Image has no matching TaskSpec assetCandidate")
        self.warnings.append(f"{node.node_id}: selected asset {best[1]!r} without presentation slot")
        return best[1]

    def progress(self, node: AltNode, repeat_context: bool) -> tuple[Any, Any]:
        slot = self.slot(node.node_id)
        source = slot.get("source")
        if source is None:
            source = find_best_value(node, self.values, "number", self.used_paths)
            if source:
                self.warnings.append(f"{node.node_id}: matched Progress to schema path {source} by node ID")
        value = source_expression(source, repeat_context) if source is not None else 0
        total_source = slot.get("totalSource")
        total = source_expression(total_source, repeat_context) if total_source is not None else slot.get("total", 100)
        return value, total

    def checkbox(self, node: AltNode, repeat_context: bool) -> tuple[str, Any]:
        slot = self.slot(node.node_id)
        label = str(slot.get("label", ""))
        source = slot.get("source")
        if source is None:
            source = find_best_value(node, self.values, "bool", self.used_paths)
            if source:
                self.warnings.append(f"{node.node_id}: matched Checkbox to schema path {source} by node ID")
        selected = source_expression(source, repeat_context) if source is not None else False
        return label, selected

    def event(self, node: AltNode, allow_fallback: bool) -> list[dict[str, Any]] | None:
        slot = self.slot(node.node_id)
        index = slot.get("eventCandidate")
        if isinstance(index, int) and 0 <= index < len(self.events):
            candidate = self.events[index]
        elif allow_fallback and self.events:
            candidate = self.events[0]
            self.warnings.append(f"{node.node_id}: selected first eventCandidate without presentation slot")
        else:
            return None
        if not isinstance(candidate, dict) or not isinstance(candidate.get("call"), str):
            return None
        event: dict[str, Any] = {"call": candidate["call"]}
        if isinstance(candidate.get("args"), dict):
            event["args"] = candidate["args"]
        return [event]

    def repeat_path(self, node: AltNode) -> str:
        slot = self.slot(node.node_id)
        source = slot.get("source")
        if isinstance(source, str) and source.startswith("/"):
            return source
        if self.collections:
            path = self.collections[0]
            self.warnings.append(f"{node.node_id}: selected collection {path} without presentation slot")
            return path
        raise ConversionError(f"{node.node_id}: Repeat requires a collection presentation slot")


def apply_alt_styles(node: AltNode) -> tuple[dict[str, Any], dict[str, Any]]:
    top: dict[str, Any] = {"id": node.node_id, "component": node.component}
    styles: dict[str, Any] = {}
    attrs = node.attrs

    if "size" in attrs:
        size = parse_dimension_token(attrs["size"])
        if size is None:
            raise ConversionError(f"{node.node_id}: invalid size")
        styles["width"] = size
        styles["height"] = size
    elif "box" in attrs:
        width, height = parse_box(attrs["box"])
        if width is not None:
            styles["width"] = width
        if height is not None:
            styles["height"] = height

    if "pad" in attrs:
        styles["padding"] = parse_edge(attrs["pad"])
    if "margin" in attrs:
        styles["margin"] = parse_edge(attrs["margin"])
    if "gap" in attrs:
        if node.component == "List":
            top["space"] = attrs["gap"]
        elif node.component in {"Row", "Column"}:
            top["itemMargin"] = attrs["gap"]
    if "main" in attrs:
        styles["justifyContent"] = MAIN_TO_DSL.get(str(attrs["main"]), attrs["main"])
    if "cross" in attrs:
        styles["alignItems"] = attrs["cross"]
    if "align" in attrs:
        styles["alignContent"] = attrs["align"]
    if "wrap" in attrs:
        top["wrap"] = attrs["wrap"]
    if "grow" in attrs:
        styles["layoutWeight"] = attrs["grow"]
    if "shrink" in attrs:
        styles["flexShrink"] = attrs["shrink"]

    if node.component in {"Text", "Button"} and "font" in attrs:
        parts = str(attrs["font"]).split("/", 1)
        font_size = parse_dimension_token(parts[0])
        if font_size is None:
            raise ConversionError(f"{node.node_id}: invalid font size")
        styles["fontSize"] = font_size
        if len(parts) == 2:
            weight = parse_dimension_token(parts[1])
            styles["fontWeight"] = weight if weight is not None else parts[1]
    if node.component == "Text":
        if "lines" in attrs:
            styles["maxLines"] = attrs["lines"]
        if "overflow" in attrs:
            styles["textOverflow"] = attrs["overflow"]
        if "text" in attrs:
            styles["textAlign"] = attrs["text"]
    elif node.component == "Image":
        if "fit" in attrs:
            styles["objectFit"] = attrs["fit"]
        if "ratio" in attrs:
            styles["aspectRatio"] = attrs["ratio"]
    elif node.component == "Progress":
        if "type" in attrs:
            styles["type"] = attrs["type"]
        if "color" in attrs:
            styles["color"] = attrs["color"]
    elif node.component == "Divider":
        vertical = str(attrs.get("axis", "h")) == "v"
        styles["vertical"] = vertical
        if "len" in attrs:
            styles["height" if vertical else "width"] = attrs["len"]
        if "stroke" in attrs:
            styles["strokeWidth"] = attrs["stroke"]
        if "color" in attrs:
            styles["color"] = attrs["color"]
    elif node.component == "Checkbox":
        if "shape" in attrs:
            styles["shape"] = attrs["shape"]
        if "selected" in attrs:
            styles["selectedColor"] = attrs["selected"]
        if "unselected" in attrs:
            styles["unSelectedColor"] = attrs["unselected"]
        if "mark" in attrs:
            parts = str(attrs["mark"]).split("/")
            if len(parts) != 3:
                raise ConversionError(f"{node.node_id}: mark must use size/strokeWidth/strokeColor")
            mark_size = parse_dimension_token(parts[0])
            mark_width = parse_dimension_token(parts[1])
            styles["mark"] = {
                "size": mark_size if mark_size is not None else parts[0],
                "strokeWidth": mark_width if mark_width is not None else parts[1],
                "strokeColor": parts[2],
            }
    elif node.component == "List":
        if "direction" in attrs:
            styles["listDirection"] = attrs["direction"]
        if "scroll" in attrs:
            styles["scrollBar"] = attrs["scroll"]

    if "radius" in attrs:
        styles["borderRadius"] = attrs["radius"]
    if "bg" in attrs:
        styles["backgroundColor"] = attrs["bg"]
    if "fg" in attrs and node.component in {"Text", "Button"}:
        styles["fontColor"] = attrs["fg"]
    if "gradient" in attrs:
        if not isinstance(attrs["gradient"], dict):
            raise ConversionError(f"{node.node_id}: gradient must be a JSON object")
        styles["linearGradient"] = attrs["gradient"]
    if "border" in attrs:
        parts = str(attrs["border"]).split("/", 1)
        width = parse_dimension_token(parts[0])
        styles["borderWidth"] = width if width is not None else parts[0]
        if len(parts) == 2:
            styles["borderColor"] = parts[1]
    if "shadow" in attrs:
        styles["shadow"] = attrs["shadow"]
    if attrs.get("clip") is True:
        styles["clip"] = True
    if "style" in attrs:
        if not isinstance(attrs["style"], dict):
            raise ConversionError(f"{node.node_id}: style must be a JSON object")
        styles.update(copy.deepcopy(attrs["style"]))
    return top, styles


def alt_to_dsl(
    document: AltDocument,
    task_spec: dict[str, Any],
    strict_layout: bool = True,
    validate_content: bool = True,
) -> tuple[str, list[str]]:
    size = task_spec.get("size")
    if size not in {"2x2", "2x4"}:
        raise ConversionError(f"TaskSpec.size must be 2x2 or 2x4, got {size!r}")
    issues = validate_layout(document, size)
    errors = [issue for issue in issues if issue.severity == "error"]
    if strict_layout and errors:
        detail = "; ".join(f"{issue.node_id}: {issue.message}" for issue in errors)
        raise ConversionError(f"ALT layout validation failed: {detail}")

    resolver = SemanticResolver(task_spec)
    if not strict_layout:
        resolver.warnings.extend(
            f"[{issue.node_id}] {issue.message}" for issue in errors
        )
    components: list[dict[str, Any]] = []

    def compile_node(node: AltNode, repeat_context: bool = False) -> None:
        if node.component == "Repeat":
            for child in node.children:
                compile_node(child, True)
            return
        top, styles = apply_alt_styles(node)
        repeat_children = [child for child in node.children if child.component == "Repeat"]
        direct_children = [child for child in node.children if child.component != "Repeat"]
        if repeat_children and direct_children:
            raise ConversionError(f"{node.node_id}: container cannot mix Repeat and direct children")
        if len(repeat_children) > 1:
            raise ConversionError(f"{node.node_id}: container can contain only one Repeat")
        if repeat_children:
            repeat = repeat_children[0]
            if len(repeat.children) != 1:
                raise ConversionError(f"{repeat.node_id}: Repeat must contain exactly one template")
            top["children"] = {
                "componentId": repeat.children[0].node_id,
                "path": resolver.repeat_path(repeat),
            }
        elif node.component in CONTAINERS:
            top["children"] = [child.node_id for child in direct_children]

        if node.component == "Text":
            top["content"] = resolver.text(node, repeat_context)
        elif node.component == "Image":
            top["src"] = resolver.image(node)
        elif node.component == "Progress":
            top["value"], top["total"] = resolver.progress(node, repeat_context)
        elif node.component == "Button":
            slot = resolver.slot(node.node_id)
            top["label"] = str(slot.get("label", humanize_id(node.node_id, "Button")))
            button_width, _ = node_box(node, intrinsic=False)
            chars = node.attrs.get("chars")
            if validate_content and isinstance(chars, int) and not is_dynamic(top["label"]):
                if len(top["label"]) > chars:
                    raise ConversionError(
                        f"{node.node_id}: Button label {top['label']!r} contains {len(top['label'])} "
                        f"characters but ALT chars={chars}"
                    )
            if validate_content and button_width is not None:
                required_width = estimated_text_width(top["label"], node_font_size(node, 16.0)) + 24.0
                if button_width + 0.01 < required_width:
                    raise ConversionError(
                        f"{node.node_id}: Button width {button_width:g} cannot contain label {top['label']!r}; "
                        f"requires at least {required_width:g}vp"
                    )
            event = resolver.event(node, allow_fallback=True)
            if event:
                top["onClick"] = event
        elif node.component == "Checkbox":
            top["label"], top["select"] = resolver.checkbox(node, repeat_context)
            checkbox_width, _ = node_box(node, intrinsic=False)
            if validate_content and node.attrs.get("protect") is True and checkbox_width is not None and top["label"]:
                required_width = estimated_text_width(top["label"], 16.0) + 36.0
                if checkbox_width + 0.01 < required_width:
                    raise ConversionError(
                        f"{node.node_id}: Checkbox width {checkbox_width:g} cannot contain protected label "
                        f"{top['label']!r}; requires at least {required_width:g}vp"
                    )
            slot = resolver.slot(node.node_id)
            if isinstance(slot.get("group"), str):
                top["group"] = slot["group"]
            event = resolver.event(node, allow_fallback=False)
            if event:
                top["onClick"] = event
        else:
            event = resolver.event(node, allow_fallback=False)
            if event:
                top["onClick"] = event

        if styles:
            top["styles"] = styles
        components.append(top)
        for child in node.children:
            compile_node(child, repeat_context)

    compile_node(document.root)

    width, height = (140, 140) if size == "2x2" else (300, 140)
    radius = 18 if size == "2x2" else 22
    root_component = next((item for item in components if item["id"] == document.root.node_id), None)
    if root_component is None:
        raise ConversionError("compiled root component is missing")
    root_styles = root_component.setdefault("styles", {})
    root_styles["width"] = width
    root_styles["height"] = height
    root_styles.setdefault("padding", 12)
    root_styles.setdefault("borderRadius", radius)
    root_styles.setdefault("clip", True)
    if not any(key in root_styles for key in ("backgroundColor", "linearGradient", "backgroundImage")):
        root_styles["backgroundColor"] = "#FFFFFFFF"
        resolver.warnings.append(f"{document.root.node_id}: root had no surface background; added #FFFFFFFF")

    create = {
        "version": "v0.9",
        "createSurface": {
            "surfaceId": SURFACE_ID,
            "catalogId": CATALOG_ID,
            "width": width,
            "height": height,
        },
    }
    update = {
        "version": "v0.9",
        "updateComponents": {
            "surfaceId": SURFACE_ID,
            "root": document.root.node_id,
            "components": components,
        },
    }
    data = {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": SURFACE_ID,
            "path": "/",
            "value": resolver.data_model,
        },
    }
    text = "\n".join(compact_json(message) for message in (create, update, data)) + "\n"
    return text, resolver.warnings


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-convert A2UI GenUI DSL and ALT+ASC files in dataset Case directories."
    )
    parser.add_argument(
        "-d",
        required=True,
        type=Path,
        metavar="DATASET_DIR",
        help="Dataset directory whose immediate child directories are Cases.",
    )
    parser.add_argument(
        "--dsl_name",
        default=DEFAULT_DSL_NAME,
        help=f"DSL filename inside each Case. Default: {DEFAULT_DSL_NAME}.",
    )
    parser.add_argument(
        "--alt_name",
        default=DEFAULT_ALT_NAME,
        help=f"ALT filename inside each Case. Default: {DEFAULT_ALT_NAME}.",
    )
    parser.add_argument(
        "--asc_name",
        default=DEFAULT_ASC_NAME,
        help=f"ASC semantic companion filename inside each Case. Default: {DEFAULT_ASC_NAME}.",
    )
    parser.add_argument(
        "--layout_report_name",
        default=DEFAULT_LAYOUT_REPORT_NAME,
        help=(
            "JSON layout report filename written inside each Case during t2d. "
            f"Default: {DEFAULT_LAYOUT_REPORT_NAME}."
        ),
    )
    parser.add_argument(
        "--taskspec_name",
        default=DEFAULT_TASKSPEC_NAME,
        help=f"TaskSpec filename inside each Case. Default: {DEFAULT_TASKSPEC_NAME}.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("d2t", "t2d"),
        help="d2t converts DSL to ALT; t2d converts ALT plus TaskSpec to DSL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir = args.d.resolve()
    if not dataset_dir.is_dir():
        LOGGER.error("dataset directory does not exist: %s", dataset_dir)
        return 2
    cases = sorted((path for path in dataset_dir.iterdir() if path.is_dir()), key=lambda path: path.name.lower())
    if not cases:
        LOGGER.error("dataset directory has no Case subdirectories: %s", dataset_dir)
        return 2

    successes = 0
    failures = 0
    LOGGER.info(
        "START mode=%s dataset=%s cases=%d profile=%s",
        args.mode,
        dataset_dir,
        len(cases),
        GENUI_PROFILE,
    )
    for index, case_dir in enumerate(cases, 1):
        prefix = f"[{index}/{len(cases)}] [{case_dir.name}]"
        LOGGER.info("%s START", prefix)
        try:
            dsl_path = case_dir / args.dsl_name
            alt_path = case_dir / args.alt_name
            asc_path = case_dir / args.asc_name
            layout_report_path = case_dir / args.layout_report_name
            task_path = case_dir / args.taskspec_name
            if args.mode == "d2t":
                task_spec = load_task_spec(task_path)
                document, size, diagnostics, orphan_count = dsl_to_alt(dsl_path, task_spec)
                issues = validate_layout(document, size)
                for diagnostic in diagnostics:
                    LOGGER.warning("%s %s", prefix, diagnostic)
                for issue in issues:
                    LOGGER.warning("%s [%s] %s", prefix, issue.node_id, issue.message)
                if orphan_count:
                    raise ConversionError(
                        f"canonical DSL cannot contain {orphan_count} unmounted component(s)"
                    )
                base_text, base_warnings = alt_to_dsl(
                    document,
                    task_spec,
                    strict_layout=False,
                    validate_content=False,
                )
                for warning in base_warnings:
                    LOGGER.warning("%s ASC base: %s", prefix, warning)
                asc_text = build_asc(
                    read_jsonl_messages(dsl_path),
                    document,
                    task_spec,
                )
                atomic_write(alt_path, serialize_alt(document))
                atomic_write(asc_path, asc_text)
                LOGGER.info(
                    "%s DONE dsl=%s alt=%s asc=%s nodes=%d",
                    prefix,
                    dsl_path.name,
                    alt_path.name,
                    asc_path.name,
                    len([line for line in asc_text.splitlines() if line.strip()]),
                )
            else:
                task_spec = load_task_spec(task_path)
                document = parse_alt(alt_path)
                asc = parse_asc(asc_path, document)
                issues = validate_layout(document, task_spec["size"])
                base_text, warnings = alt_to_dsl(
                    document,
                    task_spec,
                    strict_layout=False,
                    validate_content=False,
                )
                dsl_text = apply_asc_to_dsl(base_text, document, task_spec, asc)
                for warning in warnings:
                    LOGGER.warning("%s %s", prefix, warning)
                atomic_write(dsl_path, dsl_text)
                atomic_write(
                    layout_report_path,
                    build_layout_report(
                        case_dir.name,
                        task_spec["size"],
                        alt_path.name,
                        dsl_path.name,
                        document,
                        issues,
                    ),
                )
                LOGGER.info(
                    "%s DONE alt=%s asc=%s dsl=%s layout_report=%s issues=%d",
                    prefix,
                    alt_path.name,
                    asc_path.name,
                    dsl_path.name,
                    layout_report_path.name,
                    len(issues),
                )
            successes += 1
        except Exception as exc:
            failures += 1
            LOGGER.error("%s FAILED %s", prefix, exc)
    LOGGER.info("SUMMARY mode=%s total=%d success=%d failed=%d", args.mode, len(cases), successes, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
