"""A2UI genui DSL validator: framework + ~50 atomic rules."""
from . import cli, config, context, engine, loader, registry, result, rule
from .registry import all_rules, reset, filter_rules, register_rule
from .rule import Rule, RuleMeta, rule as rule_decorator
from .result import Report, Severity, Summary, Violation

__all__ = [
    "Report", "Severity", "Summary", "Violation",
    "Rule", "RuleMeta", "rule_decorator",
    "register_rule", "all_rules", "filter_rules", "reset",
    "cli", "config", "context", "engine", "loader", "registry", "result", "rule",
]
