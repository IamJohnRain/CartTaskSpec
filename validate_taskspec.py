#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any


REMOVED_TOP_LEVEL = {
    "assets",
    "card",
    "cardSpec",
    "dataCapabilities",
    "eventBindings",
    "intent",
    "validation",
    "capabilityGap",
    "displayCandidates",
    "rules",
    "rulesVersion",
    "schema",
    "task",
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


def validate_on_click(name: str, candidate_id: str, handlers: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(handlers, list) or not handlers:
        return [f"{name}: eventCandidate '{candidate_id}' must contain non-empty onClick array"]

    for index, handler in enumerate(handlers, start=1):
        if not isinstance(handler, dict):
            errors.append(f"{name}: eventCandidate '{candidate_id}' onClick[{index}] must be an object")
            continue
        call = handler.get("call")
        if call not in EVENT_ARGS:
            errors.append(f"{name}: eventCandidate '{candidate_id}' uses unsupported onClick.call '{call}'")
            continue
        args = handler.get("args", {})
        if not isinstance(args, dict):
            errors.append(f"{name}: eventCandidate '{candidate_id}' onClick[{index}].args must be an object")
            continue
        expected = EVENT_ARGS[call]
        actual = set(args)
        missing = expected - actual
        extra = actual - expected
        if missing:
            errors.append(f"{name}: eventCandidate '{candidate_id}' onClick[{index}] missing args {sorted(missing)}")
        if extra:
            errors.append(f"{name}: eventCandidate '{candidate_id}' onClick[{index}] has unsupported args {sorted(extra)}")
    return errors


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_task_spec(spec: dict[str, Any], name: str) -> list[str]:
    errors: list[str] = []

    for key in sorted(REMOVED_TOP_LEVEL & set(spec)):
        errors.append(f"{name}: top-level '{key}' has been removed from TaskSpec")

    data_model_value = spec.get("dataModel", {}).get("value", {})
    event_candidates = spec.get("eventCandidates", [])
    asset_candidates = spec.get("assetCandidates", [])

    candidate_ids = [
        item.get("id")
        for item in event_candidates
        if isinstance(item, dict)
    ]
    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append(f"{name}: duplicate candidate id")

    if not isinstance(event_candidates, list):
        errors.append(f"{name}: eventCandidates must be an array")
    else:
        for candidate in event_candidates:
            if not isinstance(candidate, dict):
                errors.append(f"{name}: every eventCandidates item must be an object")
                continue
            candidate_id = candidate.get("id", "<unknown>")
            if not has_text(candidate.get("description")):
                errors.append(f"{name}: eventCandidate '{candidate_id}' must contain non-empty description")
            errors.extend(validate_on_click(name, candidate_id, candidate.get("onClick")))
            if "eventRef" in candidate:
                errors.append(f"{name}: eventCandidate '{candidate_id}' uses removed eventRef; inline onClick instead")

    for asset in asset_candidates:
        if not isinstance(asset, dict):
            errors.append(f"{name}: every assetCandidates item must be an object")
            continue
        asset_id = asset.get("assetRef", asset.get("src", "<unknown>"))
        if not has_text(asset.get("description")):
            errors.append(f"{name}: assetCandidate '{asset_id}' must contain non-empty description")
        if asset.get("bindTo"):
            bound_value = resolve_pointer(data_model_value, asset["bindTo"])
            if bound_value != asset.get("src"):
                errors.append(f"{name}: assetCandidate bindTo '{asset['bindTo']}' does not resolve to src")

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
