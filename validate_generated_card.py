#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


ALLOWED_COMPONENTS = {
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
EXPR_POINTER_RE = re.compile(r"\$\{([^}]+)\}")
DATA_MODEL_RE = re.compile(r"\$__dataModel((?:\.[A-Za-z_][A-Za-z0-9_]*)*)")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assistant_content(response: dict) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("response is not a chat-completions response with choices[0].message.content") from exc


def extract_fence(content: str, language: str) -> str:
    pattern = re.compile(rf"```{re.escape(language)}\s*\n(.*?)\n```", re.DOTALL)
    match = pattern.search(content)
    if not match:
        raise ValueError(f"missing ```{language}``` code block")
    return match.group(1).strip()


def resolve_pointer(root, pointer: str):
    if pointer == "":
        return root
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    current = root
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def data_model_suffix_to_pointer(suffix: str) -> str:
    if not suffix:
        return "/"
    return "/" + "/".join(part for part in suffix.split(".") if part)


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def event_key(event):
    if not isinstance(event, dict):
        return None
    args = event.get("args", {})
    if not isinstance(args, dict):
        return None
    return json.dumps(
        {
            "call": event.get("call"),
            "args": args,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def validate_genui(genui_text: str, expected_spec: dict) -> list[str]:
    errors: list[str] = []
    lines = [line.strip() for line in genui_text.splitlines() if line.strip()]
    if len(lines) != 3:
        errors.append(f"genui must contain exactly 3 JSONL lines, got {len(lines)}")
        return errors

    messages = []
    for index, line in enumerate(lines, start=1):
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                errors.append(f"genui line {index} is not a JSON object")
            messages.append(message)
        except json.JSONDecodeError as exc:
            errors.append(f"genui line {index} is not valid JSON: {exc}")
            return errors

    expected_keys = ["createSurface", "updateComponents", "updateDataModel"]
    for index, (message, key) in enumerate(zip(messages, expected_keys), start=1):
        if message.get("version") != "v0.9":
            errors.append(f"genui line {index} must have version v0.9")
        if key not in message:
            errors.append(f"genui line {index} must contain '{key}' object")

    if errors:
        return errors

    create_surface = messages[0]["createSurface"]
    update_components = messages[1]["updateComponents"]
    update_data_model = messages[2]["updateDataModel"]

    if create_surface.get("catalogId") != "ohos.a2ui.extended.catalog":
        errors.append("createSurface.catalogId must be ohos.a2ui.extended.catalog")
    if "theme" in create_surface:
        errors.append("createSurface must not contain theme")

    surface_id = create_surface.get("surfaceId")
    if not surface_id:
        errors.append("createSurface.surfaceId is required")
    if update_components.get("surfaceId") != surface_id:
        errors.append("updateComponents.surfaceId must match createSurface.surfaceId")
    if update_data_model.get("surfaceId") != surface_id:
        errors.append("updateDataModel.surfaceId must match createSurface.surfaceId")
    if update_data_model.get("path") != "/":
        errors.append('updateDataModel.path must be "/"')

    if update_data_model.get("value") != expected_spec.get("dataModel", {}).get("value"):
        errors.append("updateDataModel.value must exactly equal TaskSpec dataModel.value")
    data_model_value = update_data_model.get("value", {})
    allowed_events = {
        event_key(candidate)
        for candidate in expected_spec.get("eventCandidates", [])
        if event_key(candidate) is not None
    }

    components = update_components.get("components")
    if not isinstance(components, list) or not components:
        errors.append("updateComponents.components must be a non-empty array")
        return errors

    component_ids = []
    for component in components:
        if not isinstance(component, dict):
            errors.append("every component must be a JSON object")
            continue
        component_id = component.get("id")
        component_type = component.get("component")
        if not component_id:
            errors.append("every component must have id")
        else:
            component_ids.append(component_id)
        if component_type not in ALLOWED_COMPONENTS:
            errors.append(f"component '{component_id}' uses unsupported component type '{component_type}'")
        children = component.get("children")
        if isinstance(children, list):
            for child_id in children:
                if not isinstance(child_id, str):
                    errors.append(f"component '{component_id}' children list must contain id strings")
        elif isinstance(children, dict):
            if set(children.keys()) != {"componentId", "path"}:
                errors.append(f"component '{component_id}' template children must only contain componentId and path")
        elif children is not None:
            errors.append(f"component '{component_id}' children must be an id array or template object")

    duplicate_ids = {item for item in component_ids if component_ids.count(item) > 1}
    if duplicate_ids:
        errors.append(f"duplicate component id(s): {', '.join(sorted(duplicate_ids))}")

    component_id_set = set(component_ids)
    if "root" not in component_id_set:
        errors.append("components must include id 'root'")

    for component in components:
        component_id = component.get("id")
        children = component.get("children")
        if isinstance(children, list):
            for child_id in children:
                if isinstance(child_id, str) and child_id not in component_id_set:
                    errors.append(f"component '{component_id}' references missing child '{child_id}'")
        elif isinstance(children, dict):
            template_id = children.get("componentId")
            if template_id not in component_id_set:
                errors.append(f"component '{component_id}' references missing template '{template_id}'")

    expected_size = expected_spec["target"]["size"]
    root = next((component for component in components if component.get("id") == "root"), {})
    styles = root.get("styles", {})
    expected_width = 140 if expected_size == "2x2" else 300
    if styles.get("width") != expected_width or styles.get("height") != 140:
        errors.append(f"root styles width/height must be {expected_width}x140")
    expected_radius = 18 if expected_size == "2x2" else 22
    if styles.get("borderRadius") != expected_radius or styles.get("clip") is not True:
        errors.append(f"root must use borderRadius {expected_radius} and clip true")

    for component in components:
        component_id = component.get("id", "<unknown>")
        on_click = component.get("onClick")
        if on_click is not None:
            if not isinstance(on_click, list):
                errors.append(f"component '{component_id}' onClick must be an array")
            else:
                for index, handler in enumerate(on_click, start=1):
                    key = event_key(handler)
                    if key is None:
                        errors.append(f"component '{component_id}' onClick[{index}] must contain call and object args")
                    elif key not in allowed_events:
                        errors.append(f"component '{component_id}' onClick[{index}] is not declared in TaskSpec eventCandidates")
        for value in walk(component):
            if isinstance(value, dict) and set(value.keys()) == {"path"}:
                pointer = value.get("path")
                if isinstance(pointer, str) and pointer.startswith("/") and resolve_pointer(data_model_value, pointer) is None:
                    errors.append(f"component '{component_id}' binding path '{pointer}' is missing in DataModel")
            if isinstance(value, str) and "{{" in value:
                for pointer in EXPR_POINTER_RE.findall(value):
                    if pointer.startswith("/") and resolve_pointer(data_model_value, pointer) is None:
                        errors.append(f"component '{component_id}' expression path '{pointer}' is missing in DataModel")
                for suffix in DATA_MODEL_RE.findall(value):
                    pointer = data_model_suffix_to_pointer(suffix)
                    if resolve_pointer(data_model_value, pointer) is None:
                        errors.append(f"component '{component_id}' expression path '{pointer}' is missing in DataModel")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate A2UI-model-generated genui output.")
    parser.add_argument("--response", required=True, type=Path, help="Chat-completions response JSON.")
    parser.add_argument("--spec", required=True, type=Path, help="Original TaskSpec JSON.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Directory for extracted model output.")
    parser.add_argument("--name", required=True, help="Artifact basename.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    response = load_json(args.response)
    expected_spec = load_json(args.spec)
    content = assistant_content(response)

    content_path = args.out_dir / f"{args.name}.model-output.md"
    genui_path = args.out_dir / f"{args.name}.genui.jsonl"
    report_path = args.out_dir / f"{args.name}.validation.json"

    content_path.write_text(content, encoding="utf-8")

    report = {
        "name": args.name,
        "valid": False,
        "artifacts": {
            "modelOutput": str(content_path),
            "genui": str(genui_path),
        },
        "errors": [],
    }

    try:
        if re.search(r"```cardspec\s*\n", content, re.DOTALL):
            report["errors"].append("model output must not contain a cardspec code block")
        genui_text = extract_fence(content, "genui")
        genui_path.write_text(genui_text + "\n", encoding="utf-8")

        report["errors"].extend(validate_genui(genui_text, expected_spec))
    except Exception as exc:
        report["errors"].append(str(exc))

    report["valid"] = len(report["errors"]) == 0
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
