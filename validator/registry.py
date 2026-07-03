"""Global rule registry."""
from __future__ import annotations

from .rule import Rule

_RULES: list[Rule] = []


def register_rule(r: Rule) -> None:
    for existing in _RULES:
        if existing.rule_id == r.rule_id:
            raise ValueError(f"duplicate rule_id: {r.rule_id}")
    _RULES.append(r)


def all_rules() -> list[Rule]:
    return list(_RULES)


def reset() -> None:
    _RULES.clear()


def filter_rules(disabled_ids: set[str]) -> list[Rule]:
    return [r for r in _RULES if r.rule_id not in disabled_ids]
