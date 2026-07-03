"""Rule metadata and @rule decorator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .result import Severity


@dataclass(frozen=True)
class RuleMeta:
    rule_id: str
    name: str
    description: str
    severity: Severity
    tags: tuple[str, ...] = ()
    default_enabled: bool = True


@dataclass
class Rule:
    meta: RuleMeta
    func: Callable

    @property
    def rule_id(self) -> str:
        return self.meta.rule_id

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def description(self) -> str:
        return self.meta.description

    @property
    def severity(self) -> Severity:
        return self.meta.severity


def rule(
    rule_id: str,
    severity: Severity,
    name: str,
    description: str,
    tags: tuple[str, ...] | list[str] = (),
    default_enabled: bool = True,
):
    if not rule_id or not isinstance(rule_id, str):
        raise ValueError("rule_id must be a non-empty string")
    if not name or not isinstance(name, str):
        raise ValueError(f"rule {rule_id}: name is required")
    if not description or not isinstance(description, str):
        raise ValueError(f"rule {rule_id}: description is required")
    tags_tuple = tuple(tags) if isinstance(tags, (list, tuple)) else (tags,)
    meta = RuleMeta(
        rule_id=rule_id,
        name=name,
        description=description,
        severity=severity,
        tags=tags_tuple,
        default_enabled=default_enabled,
    )

    def decorator(func: Callable) -> Rule:
        r = Rule(meta=meta, func=func)
        from .registry import register_rule
        register_rule(r)
        return r

    return decorator
