"""Validation result types: Severity, Violation, Report."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Severity(Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


@dataclass
class Violation:
    rule_id: str
    rule_name: str
    description: str
    severity: Severity
    message: str
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "description": self.description,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
        }


@dataclass
class Summary:
    error: int = 0
    warn: int = 0
    info: int = 0
    enabled: int = 0
    disabled: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class Report:
    passed: bool
    violations: list[Violation]
    summary: Summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "summary": self.summary.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
