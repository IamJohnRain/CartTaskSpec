"""L1 layout rules: root size, Row/Column budget, bottom anchor."""
from __future__ import annotations

from ..context import CardContext
from ..result import Severity, Violation
from ..rule import rule


@rule(
    "R-L1-001",
    Severity.ERROR,
    name="root宽高匹配尺寸",
    description="root 组件 styles.width/height 必须等于卡片尺寸对应值。",
    tags=("L1", "layout"),
)
def check_root_size(ctx: CardContext) -> list[Violation]:
    root = ctx.by_id.get(ctx.root_id)
    if not root:
        return []
    styles = root.get("styles", {})
    if not isinstance(styles, dict):
        return []
    w = ctx.numeric(styles.get("width"))
    h = ctx.numeric(styles.get("height"))
    expected = (140, 140) if ctx.size == "2x2" else (300, 140)
    if w != expected[0] or h != expected[1]:
        return [Violation(
            rule_id="R-L1-001",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=f"root 宽高必须为 {expected[0]}x{expected[1]}，实际 {w}x{h}",
            location=ctx.root_id,
        )]
    return []


@rule(
    "R-L1-002",
    Severity.ERROR,
    name="root圆角与clip合规",
    description="root 必须使用尺寸对应圆角（2x2→18，2x4→22）并开启 clip。",
    tags=("L1", "layout"),
)
def check_root_radius_clip(ctx: CardContext) -> list[Violation]:
    root = ctx.by_id.get(ctx.root_id)
    if not root:
        return []
    styles = root.get("styles", {})
    if not isinstance(styles, dict):
        return []
    expected_r = 18 if ctx.size == "2x2" else 22
    radius = ctx.numeric(styles.get("borderRadius"))
    clip = styles.get("clip")
    if radius != expected_r or clip is not True:
        return [Violation(
            rule_id="R-L1-002",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=f"root 必须 borderRadius={expected_r} 且 clip=true，实际 radius={radius!r} clip={clip!r}",
            location=ctx.root_id,
        )]
    return []


@rule(
    "R-L1-003",
    Severity.WARN,
    name="root padding建议12",
    description="root 默认安全区 padding 应为 12，偏离时给出告警。",
    tags=("L1", "layout"),
)
def check_root_padding(ctx: CardContext) -> list[Violation]:
    root = ctx.by_id.get(ctx.root_id)
    if not root:
        return []
    styles = root.get("styles", {})
    if not isinstance(styles, dict):
        return []
    pad = ctx.padding_tuple(styles.get("padding"))
    if pad != (12, 12, 12, 12):
        return [Violation(
            rule_id="R-L1-003",
            rule_name="",
            description="",
            severity=Severity.WARN,
            message=f"root padding 应为 (12,12,12,12)，实际 {pad}",
            location=ctx.root_id,
        )]
    return []


def _row_child_width_check(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Row":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        children = c.get("children")
        if not isinstance(children, list) or not children:
            continue
        w = ctx.numeric(styles.get("width"))
        if w is None:
            continue
        pad_l, _, _, pad_r = ctx.padding_tuple(styles.get("padding"))
        gap = ctx.numeric(c.get("itemMargin")) or 0
        used = pad_l + pad_r + gap * max(0, len(children) - 1)
        unknown = False
        for ch_id in children:
            if not isinstance(ch_id, str) or ch_id not in ctx.by_id:
                continue
            cw = ctx.numeric(ctx.by_id[ch_id].get("styles", {}).get("width"))
            if cw is None:
                unknown = True
            else:
                used += cw
        if not unknown and used > w:
            out.append(Violation(
                rule_id="R-L1-016",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"Row {cid!r} 子项占宽 {used:g} 超出父容器 {w:g}",
                location=cid,
            ))
    return out


def _row_child_height_check(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Row":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        children = c.get("children")
        if not isinstance(children, list) or not children:
            continue
        h = ctx.numeric(styles.get("height"))
        if h is None:
            continue
        pad_t, _, pad_b, _ = ctx.padding_tuple(styles.get("padding"))
        inner = h - pad_t - pad_b
        for ch_id in children:
            if not isinstance(ch_id, str) or ch_id not in ctx.by_id:
                continue
            ch = ctx.by_id[ch_id]
            ch_h = ctx.numeric(ch.get("styles", {}).get("height"))
            if ch_h is not None and ch_h > inner:
                out.append(Violation(
                    rule_id="R-L1-017",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"Row {cid!r} 子项 {ch_id!r} 高度 {ch_h:g} 超过内高 {inner:g}",
                    location=cid,
                ))
    return out


def _column_child_height_check(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Column":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        children = c.get("children")
        if not isinstance(children, list) or not children:
            continue
        h = ctx.numeric(styles.get("height"))
        if h is None:
            continue
        pad_t, _, pad_b, _ = ctx.padding_tuple(styles.get("padding"))
        gap = ctx.numeric(c.get("itemMargin")) or 0
        used = pad_t + pad_b + gap * max(0, len(children) - 1)
        unknown = False
        for ch_id in children:
            if not isinstance(ch_id, str) or ch_id not in ctx.by_id:
                continue
            ch_h = ctx.numeric(ctx.by_id[ch_id].get("styles", {}).get("height"))
            if ch_h is None:
                unknown = True
            else:
                used += ch_h
        if not unknown and used > h:
            out.append(Violation(
                rule_id="R-L1-018",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"Column {cid!r} 子项占高 {used:g} 超出父容器 {h:g}",
                location=cid,
            ))
    return out


def _column_child_width_check(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Column":
            continue
        cid = c.get("id", "<unknown>")
        styles = c.get("styles", {})
        if not isinstance(styles, dict):
            continue
        children = c.get("children")
        if not isinstance(children, list) or not children:
            continue
        w = ctx.numeric(styles.get("width"))
        if w is None:
            continue
        pad_l, _, _, pad_r = ctx.padding_tuple(styles.get("padding"))
        inner = w - pad_l - pad_r
        for ch_id in children:
            if not isinstance(ch_id, str) or ch_id not in ctx.by_id:
                continue
            ch = ctx.by_id[ch_id]
            ch_w = ctx.numeric(ch.get("styles", {}).get("width"))
            if ch_w is not None and ch_w > inner:
                out.append(Violation(
                    rule_id="R-L1-019",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"Column {cid!r} 子项 {ch_id!r} 宽度 {ch_w:g} 超过内宽 {inner:g}",
                    location=cid,
                ))
    return out


@rule(
    "R-L1-016",
    Severity.ERROR,
    name="Row子项宽度预算",
    description="Row 父容器宽 = 子项宽 + 子项 margin + 父 padding + itemMargin*间隔数，溢出时阻断。",
    tags=("L1", "layout"),
)
def check_row_width(ctx: CardContext) -> list[Violation]:
    return _row_child_width_check(ctx)


@rule(
    "R-L1-017",
    Severity.ERROR,
    name="Row子项高度合规",
    description="Row 子项高度不得超过父容器内高。",
    tags=("L1", "layout"),
)
def check_row_height(ctx: CardContext) -> list[Violation]:
    return _row_child_height_check(ctx)


@rule(
    "R-L1-018",
    Severity.ERROR,
    name="Column子项高度预算",
    description="Column 父容器高 = 子项高 + 父 padding + itemMargin*间隔数，溢出时阻断。",
    tags=("L1", "layout"),
)
def check_column_height(ctx: CardContext) -> list[Violation]:
    return _column_child_height_check(ctx)


@rule(
    "R-L1-019",
    Severity.ERROR,
    name="Column子项宽度合规",
    description="Column 子项宽度不得超过父容器内宽。",
    tags=("L1", "layout"),
)
def check_column_width(ctx: CardContext) -> list[Violation]:
    return _column_child_width_check(ctx)


@rule(
    "R-L1-020",
    Severity.ERROR,
    name="root Column底部间距合规",
    description="root 为 Column 时，最后一段到 root 底部的间距应 ≤ 16；过小（<8）时给出告警。",
    tags=("L1", "layout"),
)
def check_root_bottom_anchor(ctx: CardContext) -> list[Violation]:
    root = ctx.by_id.get(ctx.root_id)
    if not root or root.get("component") != "Column":
        return []
    styles = root.get("styles", {})
    if not isinstance(styles, dict):
        return []
    h = ctx.numeric(styles.get("height"))
    children = root.get("children")
    if h is None or not isinstance(children, list) or not children:
        return []
    pad_t, _, pad_b, _ = ctx.padding_tuple(styles.get("padding"))
    gap = ctx.numeric(root.get("itemMargin")) or 0
    used = pad_t + pad_b + gap * max(0, len(children) - 1)
    unknown = False
    for ch_id in children:
        if not isinstance(ch_id, str) or ch_id not in ctx.by_id:
            continue
        ch_h = ctx.numeric(ctx.by_id[ch_id].get("styles", {}).get("height"))
        if ch_h is None:
            unknown = True
        else:
            used += ch_h
    if unknown:
        return []
    bottom_gap = h - used + pad_b
    if bottom_gap > 16:
        return [Violation(
            rule_id="R-L1-020",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=f"root 底间距 {bottom_gap:g} 超过 16",
            location=ctx.root_id,
        )]
    if bottom_gap < 8:
        return [Violation(
            rule_id="R-L1-020",
            rule_name="",
            description="",
            severity=Severity.WARN,
            message=f"root 底间距 {bottom_gap:g} 过小，建议 8-14",
            location=ctx.root_id,
        )]
    return []
