"""L0 binding rules: expression, native binding, formatString path existence."""
from __future__ import annotations

import re

from ..context import INTERP_RE, CardContext
from ..result import Severity, Violation
from ..rule import rule


@rule(
    "R-L0-029",
    Severity.ERROR,
    name="表达式必须完整{{...}}",
    description="字符串值若含 {{ 或 }}，必须构成完整 {{ ... }} 表达式；不允许半截表达式。",
    tags=("L0", "bindings"),
)
def check_expression_complete(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if isinstance(value, str) and ("{{" in value or "}}" in value):
                if ctx.expression_body(value) is None:
                    out.append(Violation(
                        rule_id="R-L0-029",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} 路径 {path} 的表达式不是完整 {{ ... }}",
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-030",
    Severity.ERROR,
    name="表达式路径在DataModel缺失",
    description="{{ ... }} 内引用的所有绝对 JSON Pointer 路径必须在 updateDataModel.value 中存在。",
    tags=("L0", "bindings"),
)
def check_expression_path(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if isinstance(value, str):
                for ptr in ctx.expression_pointers(value):
                    if not ctx.resolve_pointer(ctx.data_model, ptr):
                        out.append(Violation(
                            rule_id="R-L0-030",
                            rule_name="",
                            description="",
                            severity=Severity.ERROR,
                            message=(
                                f"组件 {cid!r} 路径 {path} 表达式引用的路径 {ptr!r} 在 DataModel 中缺失"
                            ),
                            location=cid,
                        ))
    return out


@rule(
    "R-L0-031",
    Severity.ERROR,
    name="原生{path}绑定缺失",
    description="原生绑定 {path: '/...'} 中的路径必须在 updateDataModel.value 中存在。",
    tags=("L0", "bindings"),
)
def check_native_binding(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if isinstance(value, dict) and set(value.keys()) == {"path"}:
                ptr = value.get("path")
                if isinstance(ptr, str) and ptr.startswith("/") and not ctx.resolve_pointer(ctx.data_model, ptr):
                    out.append(Violation(
                        rule_id="R-L0-031",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} 路径 {path} 原生绑定 {ptr!r} 在 DataModel 中缺失",
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-032",
    Severity.ERROR,
    name="formatString参数类型",
    description="formatString 调用的 args.value 必须是字符串模板。",
    tags=("L0", "bindings"),
)
def check_format_string_value_type(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if isinstance(value, dict) and value.get("call") == "formatString":
                tmpl = value.get("args", {}).get("value")
                if not isinstance(tmpl, str):
                    out.append(Violation(
                        rule_id="R-L0-032",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} 路径 {path} formatString args.value 必须为字符串",
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-033",
    Severity.ERROR,
    name="formatString路径缺失",
    description="formatString 模板中 ${...} 引用的路径必须在 updateDataModel.value 中存在。",
    tags=("L0", "bindings"),
)
def check_format_string_paths(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if isinstance(value, dict) and value.get("call") == "formatString":
                tmpl = value.get("args", {}).get("value")
                if not isinstance(tmpl, str):
                    continue
                for ptr in INTERP_RE.findall(tmpl):
                    if ptr.startswith("/") and not ctx.resolve_pointer(ctx.data_model, ptr):
                        out.append(Violation(
                            rule_id="R-L0-033",
                            rule_name="",
                            description="",
                            severity=Severity.ERROR,
                            message=f"组件 {cid!r} formatString 路径 {ptr!r} 在 DataModel 中缺失",
                            location=cid,
                        ))
    return out
