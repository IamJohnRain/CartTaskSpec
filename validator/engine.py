"""Validation engine: auto-discover rules and run them over a CardContext."""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from . import rules as _rules_pkg
from .context import CardContext
from .registry import all_rules, filter_rules
from .result import Report, Severity, Summary, Violation


def discover_rules() -> None:
    for _, modname, _ in pkgutil.iter_modules(_rules_pkg.__path__):
        importlib.import_module(f".{modname}", package=_rules_pkg.__name__)


def collect_token_colors(color_file: Path | None) -> tuple[set[str], str]:
    if color_file is None or not color_file.exists():
        return set(), ""
    import re
    text = color_file.read_text(encoding="utf-8")
    colors = {c.upper() for c in re.findall(r"#[0-9a-fA-F]{6,8}", text)}
    return colors, str(color_file)


def run(ctx: CardContext, disabled_ids: set[str]) -> Report:
    enabled = filter_rules(disabled_ids)
    violations: list[Violation] = []

    for r in enabled:
        try:
            results = r.func(ctx)
        except Exception as e:
            violations.append(Violation(
                rule_id=r.rule_id,
                rule_name=r.name,
                description=r.description,
                severity=Severity.ERROR,
                message=f"rule crashed: {type(e).__name__}: {e}",
                location="<engine>",
            ))
            continue
        if not results:
            continue
        for v in results:
            if not v.rule_name:
                v.rule_name = r.name
            if not v.description:
                v.description = r.description
            violations.append(v)

    summary = Summary(
        error=sum(1 for v in violations if v.severity == Severity.ERROR),
        warn=sum(1 for v in violations if v.severity == Severity.WARN),
        info=sum(1 for v in violations if v.severity == Severity.INFO),
        enabled=len(enabled),
        disabled=len(disabled_ids),
    )
    passed = summary.error == 0 and summary.warn == 0
    return Report(passed=passed, violations=violations, summary=summary)
