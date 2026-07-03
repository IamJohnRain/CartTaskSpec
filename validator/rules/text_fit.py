"""L1 text fit rules: Text content width, Button label width and height."""
from __future__ import annotations

from ..context import CardContext
from ..result import Severity, Violation
from ..rule import rule


@rule(
    "R-L1-013",
    Severity.ERROR,
    name="Text文本宽度合规",
    description="Text 内容经宽度估算后不得超过 styles.width × maxLines。",
    tags=("L1", "text-fit"),
)
def check_text_fit(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Text":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        text = ctx.content_to_string(c.get("content"))
        if text is None:
            continue
        font = ctx.numeric(styles.get("fontSize")) or 14
        w = ctx.numeric(styles.get("width"))
        max_lines = int(ctx.numeric(styles.get("maxLines")) or 1)
        if w is not None:
            estimate = ctx.estimate_text_width(text, font)
            if estimate > w * max_lines:
                out.append(Violation(
                    rule_id="R-L1-013",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=(
                        f"Text {cid!r} 内容 {text!r} 估算宽度 {estimate:.1f} "
                        f"超过 {w:g} x {max_lines} 行"
                    ),
                    location=cid,
                ))
    return out


@rule(
    "R-L1-014",
    Severity.ERROR,
    name="Button可点击高度",
    description="Button 高度必须 ≥ 24vp，否则热区不足。",
    tags=("L1", "text-fit"),
)
def check_button_height(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Button":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        h = ctx.numeric(styles.get("height"))
        if h is not None and h < 24:
            out.append(Violation(
                rule_id="R-L1-014",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"Button {cid!r} 高度 {h:g} 低于 24",
                location=cid,
            ))
    return out


@rule(
    "R-L1-015",
    Severity.ERROR,
    name="Button label宽度合规",
    description="Button label 估算宽度 + 16vp 内边距不得超过 styles.width。",
    tags=("L1", "text-fit"),
)
def check_button_label_fit(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Button":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        label = ctx.content_to_string(c.get("label"))
        if label is None:
            continue
        font = ctx.numeric(styles.get("fontSize")) or 14
        w = ctx.numeric(styles.get("width"))
        if w is not None:
            estimate = ctx.estimate_text_width(label, font) + 16
            if estimate > w:
                out.append(Violation(
                    rule_id="R-L1-015",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=(
                        f"Button {cid!r} label {label!r} 估算宽度 {estimate:.1f} 超过 {w:g}"
                    ),
                    location=cid,
                ))
    return out
