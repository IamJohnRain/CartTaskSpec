#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any


RULES_VERSION = "harmony-form-datamodel-first-rules/v1"
REMOVED_TOP_LEVEL = {
    "cardSpec",
    "dataCapabilities",
    "eventBindings",
    "validation",
    "capabilityGap",
    "rules",
}
EVENT_ARGS = {
    "clickToCallPhone": {"phonenumber"},
    "clickToDeeplink": {"bundleName", "abilityName", "uri"},
    "clickToIntent": {"intentName", "params"},
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def resolve_pointer(root: Any, pointer: str) -> Any:
    if pointer == "":
        return root
    if not pointer.startswith("/"):
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


def validate_on_click(name: str, requirement_id: str, handlers: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(handlers, list) or not handlers:
        return [f"{name}: action requirement '{requirement_id}' must contain non-empty onClick array"]

    for index, handler in enumerate(handlers, start=1):
        if not isinstance(handler, dict):
            errors.append(f"{name}: requirement '{requirement_id}' onClick[{index}] must be an object")
            continue
        call = handler.get("call")
        if call not in EVENT_ARGS:
            errors.append(f"{name}: requirement '{requirement_id}' uses unsupported onClick.call '{call}'")
            continue
        args = handler.get("args", {})
        if not isinstance(args, dict):
            errors.append(f"{name}: requirement '{requirement_id}' onClick[{index}].args must be an object")
            continue
        expected = EVENT_ARGS[call]
        actual = set(args)
        missing = expected - actual
        extra = actual - expected
        if missing:
            errors.append(f"{name}: requirement '{requirement_id}' onClick[{index}] missing args {sorted(missing)}")
        if extra:
            errors.append(f"{name}: requirement '{requirement_id}' onClick[{index}] has unsupported args {sorted(extra)}")
    return errors


def validate_task_spec(spec: dict[str, Any], name: str) -> list[str]:
    errors: list[str] = []

    if spec.get("schema") != "taskspec/v1":
        errors.append(f"{name}: schema must be taskspec/v1")
    if spec.get("rulesVersion") != RULES_VERSION:
        errors.append(f"{name}: rulesVersion must be {RULES_VERSION}")

    for key in sorted(REMOVED_TOP_LEVEL & set(spec)):
        errors.append(f"{name}: top-level '{key}' has been removed from TaskSpec")

    card = spec.get("card", {})
    data_model_value = spec.get("dataModel", {}).get("value", {})

    requirements = card.get("requirements", [])
    if not isinstance(requirements, list) or not requirements:
        errors.append(f"{name}: card.requirements must be a non-empty array")
        return errors

    requirement_ids = [item.get("id") for item in requirements if isinstance(item, dict)]
    if len(set(requirement_ids)) != len(requirement_ids):
        errors.append(f"{name}: duplicate card.requirements.id")

    asset_refs = {item.get("assetRef") for item in spec.get("assets", []) if item.get("assetRef")}

    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append(f"{name}: every card.requirements item must be an object")
            continue
        requirement_id = requirement.get("id", "<unknown>")
        requirement_type = requirement.get("type")

        if requirement.get("assetRef") and requirement["assetRef"] not in asset_refs:
            errors.append(
                f"{name}: requirement '{requirement_id}' references missing assetRef '{requirement['assetRef']}'"
            )

        if requirement.get("dataPath"):
            local_value = resolve_pointer(data_model_value, requirement["dataPath"])
            if local_value is None:
                errors.append(
                    f"{name}: requirement '{requirement_id}' dataPath '{requirement['dataPath']}' "
                    "is not present in dataModel.value"
                )

        if requirement_type == "action":
            errors.extend(validate_on_click(name, requirement_id, requirement.get("onClick")))
        elif "onClick" in requirement:
            errors.append(f"{name}: requirement '{requirement_id}' can only contain onClick when type is action")

        if "eventRef" in requirement:
            errors.append(f"{name}: requirement '{requirement_id}' uses removed eventRef; inline onClick instead")

    for asset in spec.get("assets", []):
        if asset.get("bindTo"):
            bound_value = resolve_pointer(data_model_value, asset["bindTo"])
            if bound_value != asset.get("src"):
                errors.append(f"{name}: asset bindTo '{asset['bindTo']}' does not resolve to src")

    return errors


def iter_input_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.glob("*.taskspec.json"))
    return [path]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate TaskSpec JSON files.")
    parser.add_argument("path", type=Path, help="A TaskSpec file or directory containing *.taskspec.json files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = iter_input_files(args.path)
    if not files:
        print(f"No *.taskspec.json files found in {args.path}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in files:
        try:
            errors.extend(validate_task_spec(load_json(path), path.name))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"TaskSpec validation passed: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
