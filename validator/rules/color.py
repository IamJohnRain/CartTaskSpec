"""L2 color rules: format and token presence."""
from __future__ import annotations

from ..context import COLOR_KEYS, COLOR_RE, CardContext
from ..result import Severity, Violation
from ..rule import rule


def _is_color_field(key: str) -> bool:
    return key.endswith("Color") or key in COLOR_KEYS


@rule(
    "R-L2-001",
    Severity.ERROR,
    name="颜色格式合规",
    description="颜色值必须匹配 #RRGGBB 或 #AARRGGBB。",
    tags=("L2", "color"),
)
def check_color_format(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if not isinstance(value, str):
                continue
            key = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if not _is_color_field(key):
                continue
            if not COLOR_RE.fullmatch(value):
                out.append(Violation(
                    rule_id="R-L2-001",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {cid!r} 颜色 {value!r} 不符合 #RRGGBB / #AARRGGBB",
                    location=cid,
                ))
    return out


@rule(
    "R-L2-002",
    Severity.ERROR,
    name="颜色未在token色板",
    description="所有颜色值必须在 color-token-system.md 列出的色板中；找不到时阻断。",
    tags=("L2", "color"),
)
def check_color_in_token(ctx: CardContext) -> list[Violation]:
    if not ctx.token_colors:
        return []
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if not isinstance(value, str):
                continue
            key = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if not _is_color_field(key):
                continue
            if not COLOR_RE.fullmatch(value):
                continue
            if value.upper() not in ctx.token_colors:
                out.append(Violation(
                    rule_id="R-L2-002",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=(
                        f"组件 {cid!r} 颜色 {value!r} 不在 token 色板（来源 {ctx.token_color_source or '内置'}）中"
                    ),
                    location=cid,
                ))
    return out


@rule(
    "R-L2-003",
    Severity.ERROR,
    name="渐变stop颜色未在token色板",
    description="linearGradient stop 中的颜色必须在 token 色板中。",
    tags=("L2", "color"),
)
def check_gradient_color_in_token(ctx: CardContext) -> list[Violation]:
    if not ctx.token_colors:
        return []
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        grad = styles.get("linearGradient")
        if not isinstance(grad, dict):
            continue
        for i, stop in enumerate(grad.get("colors", []) or []):
            if not (isinstance(stop, list) and len(stop) == 2 and isinstance(stop[0], str)):
                continue
            color = stop[0]
            if not COLOR_RE.fullmatch(color):
                continue
            if color.upper() not in ctx.token_colors:
                out.append(Violation(
                    rule_id="R-L2-003",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=(
                        f"组件 {cid!r} 渐变 stop[{i}] 颜色 {color!r} 不在 token 色板中"
                    ),
                    location=cid,
                ))
    return out
