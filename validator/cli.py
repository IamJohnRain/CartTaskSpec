"""CLI: python -m validator <file.jsonl> [-c config.json]"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import engine, loader
from .config import load_config
from .context import CardContext


def _color_token_candidates() -> list[Path]:
    repo = Path(__file__).resolve().parent.parent
    return [
        repo / ".agents/skills/harmony-card-generation-datamodel-first/reference/design/color-token-system.md",
        Path.cwd() / ".agents/skills/harmony-card-generation-datamodel-first/reference/design/color-token-system.md",
    ]


def _collect_token_colors() -> tuple[set[str], str]:
    for c in _color_token_candidates():
        if c.exists():
            text = c.read_text(encoding="utf-8")
            colors = {color.upper() for color in re.findall(r"#[0-9a-fA-F]{6,8}", text)}
            return colors, str(c)
    return set(), ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate A2UI genui DSL.")
    p.add_argument("file", type=Path, help="Path to genui .jsonl file.")
    p.add_argument("-c", "--config", type=Path, default=None,
                   help="Rule config JSON file (optional).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    engine.discover_rules()

    try:
        disabled = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    try:
        messages = loader.load_genui(args.file)
    except (ValueError, FileNotFoundError) as e:
        print(f"load error: {e}", file=sys.stderr)
        return 2

    token_colors, token_source = _collect_token_colors()
    ctx = CardContext.from_messages(messages, token_colors=token_colors,
                                    token_color_source=token_source)

    report = engine.run(ctx, disabled)

    print(report.to_json())
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
