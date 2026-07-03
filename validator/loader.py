"""Load genui DSL from .jsonl file."""
from __future__ import annotations

import json
from pathlib import Path


WIDTH_2x2 = 140
WIDTH_2x4 = 300
HEIGHT = 140


def infer_size(width: int | float | None) -> str:
    if width == WIDTH_2x2:
        return "2x2"
    if width == WIDTH_2x4:
        return "2x4"
    if width is None:
        return ""
    return f"{width}x{HEIGHT}"


def load_genui(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"DSL file not found: {path}")
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 3:
        raise ValueError(
            f"genui must contain exactly 3 JSONL lines, got {len(lines)}"
        )
    messages: list[dict] = []
    for i, line in enumerate(lines, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"genui line {i} is invalid JSON: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError(f"genui line {i} must be a JSON object")
        messages.append(obj)
    return messages
