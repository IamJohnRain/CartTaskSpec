"""Rule config: load JSON file, determine disabled rule_ids."""
from __future__ import annotations

import json
from pathlib import Path

from .registry import all_rules


def load_config(path: Path | None) -> set[str]:
    if path is None:
        return set()
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config root must be a JSON object")
    rules_block = data.get("rules", {})
    if not isinstance(rules_block, dict):
        raise ValueError("config 'rules' must be an object")

    valid_ids = {r.rule_id for r in all_rules()}
    disabled: set[str] = set()
    unknown: list[str] = []
    for rid, cfg in rules_block.items():
        if rid not in valid_ids:
            unknown.append(rid)
            continue
        if not isinstance(cfg, dict):
            raise ValueError(f"config rules['{rid}'] must be an object")
        if not bool(cfg.get("enabled", True)):
            disabled.add(rid)

    if unknown:
        raise ValueError(
            f"config references unknown rule_id(s): {sorted(unknown)}"
        )
    return disabled
