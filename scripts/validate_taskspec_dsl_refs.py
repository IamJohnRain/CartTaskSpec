#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


EVENT_FUNCTIONS: dict[str, dict[str, Any]] = {
    "clickToCallPhone": {
        "parameters": {"phoneNumber": {"type": "string"}},
        "required": ["phoneNumber"],
    },
    "clickToDeeplink": {
        "parameters": {
            "bundleName": {"type": "string"},
            "abilityName": {"type": "string"},
            "uri": {"type": "string"},
        },
        "required": [],
    },
    "clickToIntent": {
        "parameters": {
            "intentName": {"type": "string"},
            "params": {"type": "object"},
        },
        "required": ["intentName", "params"],
        "supportedIntents": {
            "ViewCalendarEvent": {
                "params": {"entityId": {"type": "string"}},
                "required": ["entityId"],
            },
            "StartNavigate": {
                "params": {
                    "dstLocation": {"type": "object"},
                    "trafficpe": {"type": "string", "enum": ["Drive", "Walk", "Cycle", "Bus"]},
                },
                "required": ["dstLocation", "trafficpe"],
            },
            "SetSettingSwitch": {
                "params": {
                    "appBundleName": {"const": "com.huawei.hmos.settings"},
                    "itemName": {"const": "battery_saving_mode"},
                    "switchFlag": {"type": "number", "enum": [0, 1]},
                },
                "required": ["appBundleName", "itemName", "switchFlag"],
            },
        },
    },
}

FORBIDDEN_EVENT_FIELDS = {"description", "eventRef", "id", "label", "note", "onClick", "required"}
GENUI_FENCE_RE = re.compile(r"```genui\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
EXPR_RE = re.compile(r"^\s*\{\{\s*(.*?)\s*\}\}\s*$", re.DOTALL)
INTERP_RE = re.compile(r"^\$\{([^}]+)\}$")
DATA_MODEL_RE = re.compile(r"^\$__dataModel((?:\.[A-Za-z_][A-Za-z0-9_]*)*)$")
STRING_LITERAL_RE = re.compile(r"^'([^']*)'$|^\"([^\"]*)\"$")


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def read_pointer(root: Any, pointer: str) -> Any:
    if pointer == "/":
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


def schema_value_at(schema: Any, pointer: str) -> Any:
    value = read_pointer(schema, pointer)
    if isinstance(value, dict) and "sampleValue" in value:
        return value.get("sampleValue")
    return value


def data_model_suffix_to_pointer(suffix: str) -> str | None:
    if suffix == "":
        return "/"
    parts = [part for part in suffix.split(".") if part]
    if not parts:
        return "/"
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def canonical_event(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    call = value.get("call")
    args = value.get("args", {})
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    return json.dumps({"call": call, "args": args}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def resolve_value(value: Any, data_model_schema: Any) -> Any:
    if isinstance(value, str):
        expr = EXPR_RE.fullmatch(value)
        if not expr:
            return value
        body = expr.group(1).strip()
        literal = STRING_LITERAL_RE.fullmatch(body)
        if literal:
            return literal.group(1) if literal.group(1) is not None else literal.group(2)
        interp = INTERP_RE.fullmatch(body)
        if interp and interp.group(1).startswith("/"):
            resolved = schema_value_at(data_model_schema, interp.group(1))
            return resolved if resolved is not None else value
        data_model = DATA_MODEL_RE.fullmatch(body)
        if data_model:
            pointer = data_model_suffix_to_pointer(data_model.group(1))
            resolved = schema_value_at(data_model_schema, pointer) if pointer else None
            return resolved if resolved is not None else value
        return value
    if isinstance(value, dict):
        return {key: resolve_value(child, data_model_schema) for key, child in value.items()}
    if isinstance(value, list):
        return [resolve_value(child, data_model_schema) for child in value]
    return value


def canonical_event_with_schema(value: Any, data_model_schema: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    call = value.get("call")
    args = value.get("args", {})
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    return canonical_event({"call": call, "args": resolve_value(args, data_model_schema)})


def parse_genui(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8-sig")
    match = GENUI_FENCE_RE.search(text)
    if match:
        text = match.group(1)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    messages: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"dsl: line {index} is not valid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"dsl: line {index} must be a JSON object")
            continue
        messages.append(value)
    return messages, errors


def get_components(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for message in messages:
        update = message.get("updateComponents")
        if isinstance(update, dict) and isinstance(update.get("components"), list):
            return [component for component in update["components"] if isinstance(component, dict)]
    return []


def find_asset_value(value: Any, data_model_schema: Any) -> tuple[str | None, str | None]:
    if isinstance(value, str):
        expr = EXPR_RE.fullmatch(value)
        if not expr:
            return value, None
        body = expr.group(1).strip()
        literal = STRING_LITERAL_RE.fullmatch(body)
        if literal:
            return literal.group(1) if literal.group(1) is not None else literal.group(2), None
        interp = INTERP_RE.fullmatch(body)
        if interp and interp.group(1).startswith("/"):
            resolved = schema_value_at(data_model_schema, interp.group(1))
            return resolved if isinstance(resolved, str) else None, interp.group(1)
        data_model = DATA_MODEL_RE.fullmatch(body)
        if data_model:
            pointer = data_model_suffix_to_pointer(data_model.group(1))
            resolved = schema_value_at(data_model_schema, pointer) if pointer else None
            return resolved if isinstance(resolved, str) else None, pointer
        return None, None
    if isinstance(value, dict) and set(value.keys()) == {"path"}:
        pointer = value.get("path")
        resolved = schema_value_at(data_model_schema, pointer) if isinstance(pointer, str) else None
        return resolved if isinstance(resolved, str) else None, pointer if isinstance(pointer, str) else None
    return None, None


def validate_event_candidate(candidate: Any, index: int) -> list[str]:
    errors: list[str] = []
    location = f"taskspec: eventCandidates[{index}]"
    if not isinstance(candidate, dict):
        return [f"{location} must be an object"]
    for field in sorted(FORBIDDEN_EVENT_FIELDS & set(candidate.keys())):
        errors.append(f"{location}.{field} is not allowed by TaskSpec.md")
    call = candidate.get("call")
    if call not in EVENT_FUNCTIONS:
        errors.append(f"{location}.call uses unsupported event capability {call!r}")
        return errors
    args = candidate.get("args", {})
    if not isinstance(args, dict):
        errors.append(f"{location}.args must be an object")
        return errors
    spec = EVENT_FUNCTIONS[call]
    allowed = set(spec.get("parameters", {}).keys())
    required = set(spec.get("required", []))
    extra = sorted(set(args.keys()) - allowed)
    missing = sorted(required - set(args.keys()))
    if extra:
        errors.append(f"{location}.args has unsupported field(s): {extra}")
    if missing:
        errors.append(f"{location}.args is missing required field(s): {missing}")
    if call == "clickToIntent":
        errors.extend(validate_intent_args(args, location))
    return errors


def validate_intent_args(args: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    spec = EVENT_FUNCTIONS["clickToIntent"]
    intent = args.get("intentName")
    supported = spec.get("supportedIntents", {})
    if intent not in supported:
        errors.append(f"{location}.args.intentName is unsupported: {intent!r}")
        return errors
    params = args.get("params")
    if not isinstance(params, dict):
        errors.append(f"{location}.args.params must be an object")
        return errors
    target = supported[intent]
    allowed = set(target.get("params", {}).keys())
    required = set(target.get("required", []))
    extra = sorted(set(params.keys()) - allowed)
    missing = sorted(required - set(params.keys()))
    if extra:
        errors.append(f"{location}.args.params has unsupported field(s): {extra}")
    if missing:
        errors.append(f"{location}.args.params is missing required field(s): {missing}")
    return errors


def validate_taskspec(spec: dict[str, Any]) -> tuple[set[str], set[str], list[str]]:
    errors: list[str] = []
    if "dataModel" in spec:
        errors.append("taskspec: dataModel is not allowed; use dataModelSchema")
    data_model_schema = spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        errors.append("taskspec: dataModelSchema must be an object")

    event_candidates = spec.get("eventCandidates")
    if not isinstance(event_candidates, list):
        errors.append("taskspec: eventCandidates must be an array")
        event_candidates = []
    allowed_events: set[str] = set()
    for index, candidate in enumerate(event_candidates):
        errors.extend(validate_event_candidate(candidate, index))
        key = canonical_event(candidate)
        if key is not None:
            allowed_events.add(key)

    asset_candidates = spec.get("assetCandidates")
    if not isinstance(asset_candidates, list):
        errors.append("taskspec: assetCandidates must be an array")
        asset_candidates = []
    allowed_assets: set[str] = set()
    for index, asset in enumerate(asset_candidates):
        location = f"taskspec: assetCandidates[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{location} must be an object")
            continue
        src = asset.get("src")
        if not isinstance(src, str) or not src.strip():
            errors.append(f"{location}.src must be a non-empty string")
        else:
            allowed_assets.add(src)
        description = asset.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(f"{location}.description must be a non-empty string")
        bind_to = asset.get("bindTo")
        if bind_to is not None:
            resolved = schema_value_at(data_model_schema, bind_to) if isinstance(data_model_schema, dict) else None
            if not isinstance(bind_to, str) or not bind_to.startswith("/"):
                errors.append(f"{location}.bindTo must be a JSON Pointer")
            elif resolved != src:
                errors.append(f"{location}.bindTo does not resolve to src in dataModelSchema")
    return allowed_events, allowed_assets, errors


def validate_dsl_refs(
    messages: list[dict[str, Any]],
    data_model_schema: dict[str, Any],
    allowed_events: set[str],
    allowed_assets: set[str],
) -> list[str]:
    errors: list[str] = []
    components = get_components(messages)
    if not components:
        return ["dsl: updateComponents.components must be present to validate events and assets"]

    for component in components:
        component_id = component.get("id", "<unknown>")
        on_click = component.get("onClick")
        if on_click is not None:
            if not isinstance(on_click, list):
                errors.append(f"dsl: component {component_id!r} onClick must be an array")
            else:
                for index, handler in enumerate(on_click):
                    key = canonical_event_with_schema(handler, data_model_schema)
                    if key is None:
                        errors.append(f"dsl: component {component_id!r} onClick[{index}] must contain call and object args")
                    elif key not in allowed_events:
                        errors.append(f"dsl: component {component_id!r} onClick[{index}] is not declared in TaskSpec.eventCandidates")

        if component.get("component") == "Image":
            check_asset_ref(
                component.get("src"),
                f"dsl: component {component_id!r} Image.src",
                data_model_schema,
                allowed_assets,
                errors,
            )
        styles = component.get("styles")
        if isinstance(styles, dict) and "backgroundImage" in styles:
            check_asset_ref(
                styles.get("backgroundImage"),
                f"dsl: component {component_id!r} styles.backgroundImage",
                data_model_schema,
                allowed_assets,
                errors,
            )
    return errors


def check_asset_ref(
    value: Any,
    location: str,
    data_model_schema: dict[str, Any],
    allowed_assets: set[str],
    errors: list[str],
) -> None:
    resolved, pointer = find_asset_value(value, data_model_schema)
    if resolved is None:
        suffix = f" via {pointer}" if pointer else ""
        errors.append(f"{location} cannot be resolved to a TaskSpec assetCandidate{suffix}")
        return
    if resolved not in allowed_assets:
        errors.append(f"{location} uses undeclared asset {resolved!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate only TaskSpec/DSL asset and event references.",
    )
    parser.add_argument("--taskspec", required=True, type=Path, help="TaskSpec JSON using dataModelSchema.")
    parser.add_argument("--dsl", required=True, type=Path, help="genui JSONL file or markdown with a genui fence.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    try:
        spec = load_json_object(args.taskspec)
    except Exception as exc:
        errors.append(f"taskspec: {exc}")
        spec = {}
    try:
        messages, dsl_errors = parse_genui(args.dsl)
        errors.extend(dsl_errors)
    except Exception as exc:
        errors.append(f"dsl: {exc}")
        messages = []

    allowed_events, allowed_assets, task_errors = validate_taskspec(spec)
    errors.extend(task_errors)
    data_model_schema = spec.get("dataModelSchema") if isinstance(spec.get("dataModelSchema"), dict) else {}
    if messages:
        errors.extend(validate_dsl_refs(messages, data_model_schema, allowed_events, allowed_assets))

    report = {
        "valid": not errors,
        "taskspec": str(args.taskspec),
        "dsl": str(args.dsl),
        "errors": errors,
    }
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif errors:
        for error in errors:
            print(error, file=sys.stderr)
    else:
        print("TaskSpec/DSL asset and event reference validation passed")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
