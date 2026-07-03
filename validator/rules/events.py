"""L0 event rules: onClick capability and args validation."""
from __future__ import annotations

from ..context import EVENT_CAPABILITIES, CardContext
from ..result import Severity, Violation
from ..rule import rule


@rule(
    "R-L0-022",
    Severity.ERROR,
    name="onClick必须为数组",
    description="组件的 onClick 字段必须是数组形式（支持多 handler 串联）。",
    tags=("L0", "events"),
)
def check_onclick_is_list(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        if "onClick" in c:
            oc = c.get("onClick")
            if not isinstance(oc, list):
                out.append(Violation(
                    rule_id="R-L0-022",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {cid!r} onClick 必须为数组",
                    location=cid,
                ))
    return out


@rule(
    "R-L0-023",
    Severity.ERROR,
    name="onClick handler必须为对象",
    description="onClick 数组中的每一项必须是 JSON 对象。",
    tags=("L0", "events"),
)
def check_onclick_handler_is_object(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        oc = c.get("onClick")
        if isinstance(oc, list):
            for i, h in enumerate(oc, 1):
                if not isinstance(h, dict):
                    out.append(Violation(
                        rule_id="R-L0-023",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} onClick[{i}] 必须为对象，实际 {type(h).__name__}",
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-024",
    Severity.ERROR,
    name="事件能力必须已知",
    description="onClick handler 的 call 必须是已知事件能力：clickToCallPhone / clickToDeeplink / clickToIntent。",
    tags=("L0", "events"),
)
def check_event_capability(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        oc = c.get("onClick")
        if isinstance(oc, list):
            for i, h in enumerate(oc, 1):
                if not isinstance(h, dict):
                    continue
                call = h.get("call")
                if call not in EVENT_CAPABILITIES:
                    out.append(Violation(
                        rule_id="R-L0-024",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} onClick[{i}] 未知事件能力 {call!r}",
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-025",
    Severity.ERROR,
    name="事件args必须为对象",
    description="onClick handler 的 args 必须是 JSON 对象。",
    tags=("L0", "events"),
)
def check_event_args_type(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        oc = c.get("onClick")
        if isinstance(oc, list):
            for i, h in enumerate(oc, 1):
                if not isinstance(h, dict) or h.get("call") not in EVENT_CAPABILITIES:
                    continue
                args = h.get("args")
                if not isinstance(args, dict):
                    out.append(Violation(
                        rule_id="R-L0-025",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} onClick[{i}] args 必须为对象",
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-026",
    Severity.ERROR,
    name="事件args多余字段",
    description="onClick handler 的 args 不能包含该事件能力之外的字段。",
    tags=("L0", "events"),
)
def check_event_args_extra(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        oc = c.get("onClick")
        if isinstance(oc, list):
            for i, h in enumerate(oc, 1):
                if not isinstance(h, dict) or h.get("call") not in EVENT_CAPABILITIES:
                    continue
                args = h.get("args")
                if not isinstance(args, dict):
                    continue
                extra = set(args.keys()) - EVENT_CAPABILITIES[h["call"]]
                if extra:
                    out.append(Violation(
                        rule_id="R-L0-026",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=(
                            f"组件 {cid!r} onClick[{i}] {h['call']} 不支持的 args 字段 {sorted(extra)!r}"
                        ),
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-027",
    Severity.ERROR,
    name="事件args缺失必要字段",
    description="onClick handler 的 args 必须包含该事件能力要求的全部字段。",
    tags=("L0", "events"),
)
def check_event_args_missing(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        oc = c.get("onClick")
        if isinstance(oc, list):
            for i, h in enumerate(oc, 1):
                if not isinstance(h, dict) or h.get("call") not in EVENT_CAPABILITIES:
                    continue
                args = h.get("args")
                if not isinstance(args, dict):
                    continue
                missing = EVENT_CAPABILITIES[h["call"]] - set(args.keys())
                if missing:
                    out.append(Violation(
                        rule_id="R-L0-027",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=(
                            f"组件 {cid!r} onClick[{i}] {h['call']} 缺失 args 字段 {sorted(missing)!r}"
                        ),
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-028",
    Severity.ERROR,
    name="clickToCallPhone args唯一",
    description="clickToCallPhone 的 args 只能包含 phoneNumber 一个字段。",
    tags=("L0", "events"),
)
def check_call_phone_strict(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        oc = c.get("onClick")
        if isinstance(oc, list):
            for i, h in enumerate(oc, 1):
                if not isinstance(h, dict) or h.get("call") != "clickToCallPhone":
                    continue
                args = h.get("args")
                if isinstance(args, dict) and set(args.keys()) != {"phoneNumber"}:
                    out.append(Violation(
                        rule_id="R-L0-028",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=(
                            f"组件 {cid!r} onClick[{i}] clickToCallPhone args 只能为 {{'phoneNumber': ...}}"
                        ),
                        location=cid,
                    ))
    return out
