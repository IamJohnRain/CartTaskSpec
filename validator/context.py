"""CardContext: parsed DSL + helpers for rules."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


WIDTH_2x2 = 140
WIDTH_2x4 = 300
HEIGHT = 140

COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
INTERP_RE = re.compile(r"\$\{([^}]+)\}")
DATA_MODEL_PATH_RE = re.compile(
    r"\$__dataModel((?:\.[A-Za-z_][A-Za-z0-9_]*|\[(?:\d+|'[^']+'|\"[^\"]+\")\])*)"
)
SUFFIX_TOKEN_RE = re.compile(
    r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+|'[^']+'|\"[^\"]+\")\]"
)
EXPR_BODY_RE = re.compile(r"\s*\{\{\s*(.*?)\s*\}\}\s*", re.DOTALL)
INTERP_FULL_RE = re.compile(r"\$\{([^}]+)\}")
DATA_MODEL_FULL_RE = re.compile(
    r"\$__dataModel((?:\.[A-Za-z_][A-Za-z0-9_]*|\[(?:\d+|'[^']+'|\"[^\"]+\")\])*)"
)
LITERAL_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")
NUMERIC_RE = re.compile(r"(-?\d+(?:\.\d+)?)(?:vp|fp|px)?")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


FONT_SIZES = {10, 12, 14, 16, 18, 20, 32, 40}
SPACING = {0, 2, 4, 6, 8, 10, 12, 14, 16}
ALLOWED_COMPONENTS = {
    "Text", "Image", "Divider", "Progress", "Button",
    "Checkbox", "Row", "Column", "List", "Stack",
}
BANNED_COMPONENTS = {
    "TextInput", "Toggle", "Radio", "CheckboxGroup", "Select",
    "NavContainer", "Tabs", "TabContent", "Web", "Grid", "If",
}
BANNED_KEYS = {"theme", "action"}
COLOR_KEYS = {
    "color", "backgroundColor", "borderColor", "fontColor",
}
EVENT_CAPABILITIES = {
    "clickToCallPhone": {"phoneNumber"},
    "clickToDeeplink": {"bundleName", "abilityName", "uri"},
    "clickToIntent": {"intentName", "params"},
}
EXPECTED_MESSAGE_KEYS = ["createSurface", "updateComponents", "updateDataModel"]


@dataclass
class CardContext:
    messages: list[dict] = field(default_factory=list)
    create_surface: dict = field(default_factory=dict)
    update_components: dict = field(default_factory=dict)
    update_data_model: dict = field(default_factory=dict)
    components: list[dict] = field(default_factory=list)
    by_id: dict[str, dict] = field(default_factory=dict)
    root_id: str = ""
    data_model: Any = None
    size: str = ""
    token_colors: set[str] = field(default_factory=set)
    token_color_source: str = ""

    @classmethod
    def from_messages(
        cls,
        messages: list[dict],
        token_colors: set[str] | None = None,
        token_color_source: str = "",
    ) -> "CardContext":
        if len(messages) < 3:
            return cls(messages=list(messages), token_colors=token_colors or set())
        create = messages[0].get("createSurface", {})
        update = messages[1].get("updateComponents", {})
        data = messages[2].get("updateDataModel", {})
        if not isinstance(create, dict) or not isinstance(update, dict) or not isinstance(data, dict):
            return cls(messages=list(messages), token_colors=token_colors or set())

        raw_components = update.get("components", [])
        components: list[dict] = []
        by_id: dict[str, dict] = {}
        if isinstance(raw_components, list):
            for c in raw_components:
                if isinstance(c, dict):
                    components.append(c)
                    cid = c.get("id")
                    if isinstance(cid, str) and cid:
                        by_id[cid] = c

        data_model = data.get("value")
        width = create.get("width")
        size = infer_size(width)

        root_id_val = update.get("root", "")
        return cls(
            messages=list(messages),
            create_surface=create,
            update_components=update,
            update_data_model=data,
            components=components,
            by_id=by_id,
            root_id=root_id_val if isinstance(root_id_val, str) else "",
            data_model=data_model,
            size=size,
            token_colors=set(token_colors or set()),
            token_color_source=token_color_source,
        )

    def walk(self, value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
        yield path, value
        if isinstance(value, dict):
            for k, v in value.items():
                yield from self.walk(v, f"{path}.{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from self.walk(v, f"{path}[{i}]")

    def resolve_pointer(self, data: Any, pointer: str) -> bool:
        return self._read_pointer(data, pointer) is not None or pointer == "/"

    def read_pointer(self, data: Any, pointer: str) -> Any:
        return self._read_pointer(data, pointer)

    def _read_pointer(self, data: Any, pointer: str) -> Any:
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            return None
        current = data
        if pointer == "/":
            return current
        for part in pointer.strip("/").split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                return None
        return current

    def expression_body(self, value: str) -> str | None:
        m = EXPR_BODY_RE.fullmatch(value)
        return m.group(1) if m else None

    def suffix_to_pointer(self, suffix: str) -> str | None:
        parts: list[str] = []
        pos = 0
        for m in SUFFIX_TOKEN_RE.finditer(suffix):
            if m.start() != pos:
                return None
            pos = m.end()
            tok = m.group(1) if m.group(1) is not None else m.group(2)
            if tok is None:
                return None
            if (tok.startswith("'") and tok.endswith("'")) or (tok.startswith('"') and tok.endswith('"')):
                tok = tok[1:-1]
            parts.append(tok.replace("~", "~0").replace("/", "~1"))
        if pos != len(suffix):
            return None
        return "/" + "/".join(parts) if parts else "/"

    def expression_pointers(self, value: str) -> list[str]:
        body = self.expression_body(value)
        if body is None:
            return []
        pointers: list[str] = []
        for p in INTERP_RE.findall(body):
            if p.startswith("/"):
                pointers.append(p)
        for m in DATA_MODEL_PATH_RE.finditer(body):
            ptr = self.suffix_to_pointer(m.group(1))
            if ptr is not None:
                pointers.append(ptr)
        return list(dict.fromkeys(pointers))

    def numeric(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            m = NUMERIC_RE.fullmatch(value.strip())
            if m:
                return float(m.group(1))
        return None

    def padding_tuple(self, value: Any) -> tuple[float, float, float, float]:
        if value is None:
            return 0, 0, 0, 0
        n = self.numeric(value)
        if n is not None:
            return n, n, n, n
        if isinstance(value, dict):
            top = self.numeric(value.get("top")) or 0
            right = self.numeric(value.get("right")) or 0
            bottom = self.numeric(value.get("bottom")) or 0
            left = self.numeric(value.get("left")) or 0
            return top, right, bottom, left
        return 0, 0, 0, 0

    def estimate_text_width(self, text: str, font_size: float) -> float:
        width = 0.0
        for ch in text:
            if CJK_RE.match(ch):
                width += font_size
            elif ch.isspace():
                width += 0.35 * font_size
            elif ch in ".,;:!?'\"°%/|":
                width += 0.4 * font_size
            else:
                width += 0.6 * font_size
        return width

    def content_to_string(self, value: Any) -> str | None:
        if isinstance(value, str):
            body = self.expression_body(value)
            if body is not None:
                body = body.strip()
                interp = INTERP_FULL_RE.fullmatch(body)
                if interp and interp.group(1).startswith("/"):
                    v = self._read_pointer(self.data_model, interp.group(1))
                    return "" if v is None else str(v)
                mp = DATA_MODEL_FULL_RE.fullmatch(body)
                if mp:
                    ptr = self.suffix_to_pointer(mp.group(1))
                    if ptr is not None:
                        v = self._read_pointer(self.data_model, ptr)
                        return "" if v is None else str(v)
                lit = LITERAL_RE.fullmatch(body)
                if lit:
                    return lit.group(1) if lit.group(1) is not None else lit.group(2)
                return None
            return value
        if isinstance(value, dict):
            if set(value.keys()) == {"path"}:
                v = self._read_pointer(self.data_model, value.get("path"))
                return "" if v is None else str(v)
            if value.get("call") == "formatString":
                tmpl = value.get("args", {}).get("value")
                if isinstance(tmpl, str):
                    def repl(m: re.Match) -> str:
                        v = self._read_pointer(self.data_model, m.group(1))
                        return "" if v is None else str(v)
                    return INTERP_RE.sub(repl, tmpl)
        return None

    def normalize_text(self, text: str) -> str:
        t = re.sub(r"\s+", "", text)
        t = re.sub(r"[：:，,。.!！?？|/\\-]", "", t)
        return t


def infer_size(width: int | float | None) -> str:
    if width == WIDTH_2x2:
        return "2x2"
    if width == WIDTH_2x4:
        return "2x4"
    if width is None:
        return ""
    return f"{width}x{HEIGHT}"
