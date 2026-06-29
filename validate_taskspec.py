#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any


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


def validate_task_spec(spec: dict[str, Any], name: str) -> list[str]:
    errors: list[str] = []

    if spec.get("schema") != "taskspec/v1":
        errors.append(f"{name}: schema must be taskspec/v1")
    if spec.get("rulesVersion") != "harmony-form-rules/v1":
        errors.append(f"{name}: rulesVersion must be harmony-form-rules/v1")

    card = spec.get("card", {})
    card_spec = spec.get("cardSpec", {})
    data_model_value = spec.get("dataModel", {}).get("value", {})
    data_capabilities = spec.get("dataCapabilities", [])

    if card.get("size") != card_spec.get("suggestSize"):
        errors.append(f"{name}: card.size and cardSpec.suggestSize differ")

    requirements = card.get("requirements", [])
    requirement_ids = [item.get("id") for item in requirements]
    if len(set(requirement_ids)) != len(requirement_ids):
        errors.append(f"{name}: duplicate card.requirements.id")

    event_refs = {item.get("eventRef") for item in spec.get("eventBindings", [])}
    asset_refs = {item.get("assetRef") for item in spec.get("assets", []) if item.get("assetRef")}
    capability_paths = {
        path.get("path")
        for capability in data_capabilities
        for path in capability.get("usedOutputPaths", [])
    }

    for requirement in requirements:
        if requirement.get("eventRef") and requirement["eventRef"] not in event_refs:
            errors.append(
                f"{name}: requirement '{requirement.get('id')}' references missing eventRef '{requirement['eventRef']}'"
            )
        if requirement.get("assetRef") and requirement["assetRef"] not in asset_refs:
            errors.append(
                f"{name}: requirement '{requirement.get('id')}' references missing assetRef '{requirement['assetRef']}'"
            )
        if requirement.get("dataPath"):
            local_value = resolve_pointer(data_model_value, requirement["dataPath"])
            if local_value is None and requirement["dataPath"] not in capability_paths:
                errors.append(
                    f"{name}: requirement '{requirement.get('id')}' dataPath '{requirement['dataPath']}' "
                    "is not in dataModel.value or dataCapabilities.usedOutputPaths"
                )

    for asset in spec.get("assets", []):
        if asset.get("bindTo"):
            bound_value = resolve_pointer(data_model_value, asset["bindTo"])
            if bound_value != asset.get("src"):
                errors.append(f"{name}: asset bindTo '{asset['bindTo']}' does not resolve to src")

    data_bindings = card_spec.get("dataBindings")
    if data_capabilities:
        if not isinstance(data_bindings, list) or not data_bindings:
            errors.append(f"{name}: dynamic TaskSpec must contain cardSpec.dataBindings")
        else:
            declared = {
                (
                    capability.get("capabilityId"),
                    json.dumps(capability.get("arguments", {}), ensure_ascii=False, sort_keys=True),
                    capability.get("writeResultTo"),
                )
                for capability in data_capabilities
            }
            write_targets = [binding.get("writeResultTo") for binding in data_bindings]
            if len(set(write_targets)) != len(write_targets):
                errors.append(f"{name}: duplicate cardSpec.dataBindings.writeResultTo")
            for binding in data_bindings:
                key = (
                    binding.get("capabilityId"),
                    json.dumps(binding.get("arguments", {}), ensure_ascii=False, sort_keys=True),
                    binding.get("writeResultTo"),
                )
                if key not in declared:
                    errors.append(f"{name}: cardSpec dataBinding is not declared in dataCapabilities: {binding}")
    elif data_bindings is not None:
        errors.append(f"{name}: static TaskSpec must not contain cardSpec.dataBindings")

    rules = spec.get("rules", {})
    dsl_rules = rules.get("dsl", [])
    if not dsl_rules:
        errors.append(f"{name}: rules.dsl is required")
    if "cardSpec" in rules:
        errors.append(f"{name}: rules.cardSpec is not allowed; small model does not generate CardSpec")
    if not any("genui" in rule and "cardspec" in rule.lower() for rule in dsl_rules):
        errors.append(f"{name}: rules.dsl must state that the model outputs genui and not cardspec")

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
