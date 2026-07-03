"""L2 content rules: duplicate text detection."""
from __future__ import annotations

from ..context import CardContext
from ..result import Severity, Violation
from ..rule import rule


def _gather_visible_texts(ctx: CardContext) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        if c.get("component") == "Text":
            t = ctx.content_to_string(c.get("content"))
            if t:
                out.append((cid, t))
        elif c.get("component") == "Button":
            t = ctx.content_to_string(c.get("label"))
            if t:
                out.append((cid, t))
    return out


@rule(
    "R-L2-004",
    Severity.ERROR,
    name="可见文本字面重复",
    description="同一卡片内 Text / Button 显示文本（去空白与标点后）不得完全相同，否则信息职责冲突。",
    tags=("L2", "content"),
)
def check_text_literal_duplicate(ctx: CardContext) -> list[Violation]:
    texts = _gather_visible_texts(ctx)
    seen: dict[str, str] = {}
    out: list[Violation] = []
    for cid, text in texts:
        norm = ctx.normalize_text(text)
        if len(norm) < 2:
            continue
        if norm in seen:
            out.append(Violation(
                rule_id="R-L2-004",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=(
                    f"组件 {cid!r} 与 {seen[norm]!r} 显示文本完全重复：{text!r}"
                ),
                location=cid,
            ))
        else:
            seen[norm] = cid
    return out


@rule(
    "R-L2-005",
    Severity.WARN,
    name="可见文本可能语义重复",
    description="两个可见文本归一化后存在包含关系，可能为同义/聚合重复，需人工复核。",
    tags=("L2", "content"),
)
def check_text_semantic_duplicate(ctx: CardContext) -> list[Violation]:
    texts = _gather_visible_texts(ctx)
    out: list[Violation] = []
    norms = [(cid, ctx.normalize_text(t)) for cid, t in texts]
    for i, (cid, t) in enumerate(norms):
        for j, (oid, o) in enumerate(norms):
            if j <= i:
                continue
            if len(t) < 3 or len(o) < 3 or t == o:
                continue
            if t in o or o in t:
                out.append(Violation(
                    rule_id="R-L2-005",
                    rule_name="",
                    description="",
                    severity=Severity.WARN,
                    message=(
                        f"组件 {cid!r} 与 {oid!r} 文本可能语义重复（{t!r} / {o!r}）"
                    ),
                    location=cid,
                ))
    return out


@rule(
    "R-L2-006",
    Severity.WARN,
    name="Button与Text并排基线告警",
    description="Button 与小号 Text 在同一 Row 并排时，若父 Row padding 上下相等且 Button 未设 margin.top，可能视觉基线偏高。",
    tags=("L2", "content"),
)
def check_button_text_baseline(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        if c.get("component") != "Row":
            continue
        cid = c.get("id", "<unknown>")
        children = c.get("children")
        if not isinstance(children, list) or not children:
            continue
        child_components = []
        for ch_id in children:
            if isinstance(ch_id, str) and ch_id in ctx.by_id:
                child_components.append(ctx.by_id[ch_id])
        direct_buttons = [k for k in child_components if k.get("component") == "Button"]
        if not direct_buttons:
            continue
        has_text_peer = any(
            k.get("component") != "Button" and k.get("component") in {"Text", "Column"}
            for k in child_components
        )
        if not has_text_peer:
            continue
        for btn in direct_buttons:
            styles = btn.get("styles", {})
            if not isinstance(styles, dict):
                continue
            margin = styles.get("margin")
            margin_top = ctx.numeric(margin.get("top")) if isinstance(margin, dict) else None
            pt, _, pb, _ = ctx.padding_tuple(c.get("styles", {}).get("padding"))
            if margin_top is None and pt == pb:
                out.append(Violation(
                    rule_id="R-L2-006",
                    rule_name="",
                    description="",
                    severity=Severity.WARN,
                    message=(
                        f"Row {cid!r} 中 Button {btn.get('id')!r} 与文本并排，"
                        f"父 padding 上下对称且 Button 未设 margin.top，基线可能偏高"
                    ),
                    location=cid,
                ))
    return out
