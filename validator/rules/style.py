"""L1 style rules: fontSize scale, spacing scale, textOverflow, gradient, Image."""
from __future__ import annotations

from ..context import COLOR_RE, FONT_SIZES, SPACING, CardContext
from ..result import Severity, Violation
from ..rule import rule


@rule(
    "R-L1-004",
    Severity.ERROR,
    name="fontSize必须在字号表",
    description="styles.fontSize 必须命中受支持字号表 {10,12,14,16,18,20,32,40}。",
    tags=("L1", "style"),
)
def check_font_size(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        styles = c.get("styles")
        if not isinstance(styles, dict):
            continue
        fs = ctx.numeric(styles.get("fontSize"))
        if fs is not None and int(fs) not in FONT_SIZES:
            out.append(Violation(
                rule_id="R-L1-004",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"组件 {cid!r} fontSize {fs:g} 不在字号表 {sorted(FONT_SIZES)} 内",
                location=cid,
            ))
    return out


@rule(
    "R-L1-005",
    Severity.ERROR,
    name="textOverflow禁用截断值",
    description="受保护文本禁止使用 ellipsis / clip / marquee 这类截断/滚动值，避免信息丢失。",
    tags=("L1", "style"),
)
def check_text_overflow(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        styles = c.get("styles")
        if not isinstance(styles, dict):
            continue
        ov = styles.get("textOverflow")
        if ov in {"ellipsis", "clip", "marquee"}:
            out.append(Violation(
                rule_id="R-L1-005",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"组件 {cid!r} textOverflow={ov!r} 不允许",
                location=cid,
            ))
    return out


@rule(
    "R-L1-006",
    Severity.WARN,
    name="padding/margin应使用间距表",
    description="styles.padding 与 styles.margin 应尽量使用间距表 {0,2,4,6,8,10,12,14,16}，偏离时给出告警。",
    tags=("L1", "style"),
)
def check_padding_margin(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        styles = c.get("styles")
        if not isinstance(styles, dict):
            continue
        for key in ("padding", "margin"):
            v = styles.get(key)
            if v is None:
                continue
            for v2 in ctx.padding_tuple(v):
                if v2 not in SPACING:
                    out.append(Violation(
                        rule_id="R-L1-006",
                        rule_name="",
                        description="",
                        severity=Severity.WARN,
                        message=f"组件 {cid!r} {key} 值 {v2:g} 不在间距表 {sorted(SPACING)} 内",
                        location=cid,
                    ))
    return out


@rule(
    "R-L1-007",
    Severity.WARN,
    name="itemMargin/space应使用间距表",
    description="组件级 itemMargin / space 应使用间距表 {0,2,4,6,8,10,12,14,16}。",
    tags=("L1", "style"),
)
def check_item_margin(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for key in ("itemMargin", "space"):
            v = ctx.numeric(c.get(key))
            if v is not None and v not in SPACING:
                out.append(Violation(
                    rule_id="R-L1-007",
                    rule_name="",
                    description="",
                    severity=Severity.WARN,
                    message=f"组件 {cid!r} {key}={v:g} 不在间距表 {sorted(SPACING)} 内",
                    location=cid,
                ))
    return out


@rule(
    "R-L1-008",
    Severity.ERROR,
    name="linearGradient.colors非空",
    description="styles.linearGradient.colors 必须是非空数组。",
    tags=("L1", "style"),
)
def check_gradient_colors_present(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        styles = c.get("styles")
        if not isinstance(styles, dict):
            continue
        grad = styles.get("linearGradient")
        if isinstance(grad, dict):
            colors = grad.get("colors")
            if not isinstance(colors, list) or not colors:
                out.append(Violation(
                    rule_id="R-L1-008",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {cid!r} linearGradient.colors 必须为非空数组",
                    location=cid,
                ))
    return out


@rule(
    "R-L1-009",
    Severity.ERROR,
    name="linearGradient stop结构合法",
    description="每个 linearGradient stop 必须是 [color, offset] 二元数组。",
    tags=("L1", "style"),
)
def check_gradient_stop_shape(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        styles = c.get("styles")
        if not isinstance(styles, dict):
            continue
        grad = styles.get("linearGradient")
        if isinstance(grad, dict):
            for i, stop in enumerate(grad.get("colors", []) or []):
                if not (isinstance(stop, list) and len(stop) == 2 and isinstance(stop[0], str)):
                    out.append(Violation(
                        rule_id="R-L1-009",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} linearGradient stop[{i}] 不是 [color, offset]",
                        location=cid,
                    ))
    return out


@rule(
    "R-L1-010",
    Severity.ERROR,
    name="Image必须有src",
    description="Image 组件必须声明 src，且 src 不能为空。",
    tags=("L1", "style"),
)
def check_image_src(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Image":
            continue
        cid = c.get("id", "<unknown>")
        src = c.get("src")
        if not isinstance(src, str) or not src:
            out.append(Violation(
                rule_id="R-L1-010",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"Image 组件 {cid!r} 必须声明 src",
                location=cid,
            ))
    return out


@rule(
    "R-L1-011",
    Severity.ERROR,
    name="Image必须有显式宽高",
    description="Image 组件 styles.width/height 必须为数值，否则布局无法对齐。",
    tags=("L1", "style"),
)
def check_image_size(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Image":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            out.append(Violation(
                rule_id="R-L1-011",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"Image {cid!r} styles 必须为对象",
                location=cid,
            ))
            continue
        w = ctx.numeric(styles.get("width"))
        h = ctx.numeric(styles.get("height"))
        if w is None or h is None:
            out.append(Violation(
                rule_id="R-L1-011",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"Image {cid!r} 必须有显式 width/height 数值",
                location=cid,
            ))
    return out


@rule(
    "R-L1-012",
    Severity.WARN,
    name="Image objectFit建议contain",
    description="Image 应使用 objectFit=contain 以避免刻意裁切，除非确认需要。",
    tags=("L1", "style"),
)
def check_image_object_fit(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Image":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        if styles.get("objectFit") != "contain":
            out.append(Violation(
                rule_id="R-L1-012",
                rule_name="",
                description="",
                severity=Severity.WARN,
                message=f"Image {cid!r} 建议 objectFit=contain",
                location=cid,
            ))
    return out
