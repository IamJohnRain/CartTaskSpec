"""L0 protocol rules: line count, version, catalog, surfaceId, size."""
from __future__ import annotations

from ..context import EXPECTED_MESSAGE_KEYS, HEIGHT, WIDTH_2x2, WIDTH_2x4, CardContext
from ..result import Severity, Violation
from ..rule import rule


@rule(
    "R-L0-002",
    Severity.ERROR,
    name="version必须为v0.9",
    description="genui 三行消息的 version 字段必须等于字符串 v0.9，否则协议解析失败。",
    tags=("L0", "protocol"),
)
def check_version(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for i, msg in enumerate(ctx.messages, 1):
        if msg.get("version") != "v0.9":
            out.append(Violation(
                rule_id="R-L0-002",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"line {i} version 必须为 'v0.9'，实际为 {msg.get('version')!r}",
                location=f"line {i}",
            ))
    return out


@rule(
    "R-L0-003",
    Severity.ERROR,
    name="消息结构纯净",
    description="三行消息除 version 外只能各自包含 createSurface / updateComponents / updateDataModel 之一，不能混入多余键。",
    tags=("L0", "protocol"),
)
def check_message_structure(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for i, (msg, expected) in enumerate(zip(ctx.messages, EXPECTED_MESSAGE_KEYS), 1):
        keys = [k for k in msg.keys() if k != "version"]
        if expected not in msg:
            out.append(Violation(
                rule_id="R-L0-003",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"line {i} 缺少 {expected}",
                location=f"line {i}",
            ))
        if len(keys) != 1 or (len(keys) == 1 and keys[0] != expected):
            extra = [k for k in keys if k != expected]
            if extra:
                out.append(Violation(
                    rule_id="R-L0-003",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"line {i} 包含多余键 {extra!r}，只允许 {expected!r}",
                    location=f"line {i}",
                ))
    return out


@rule(
    "R-L0-004",
    Severity.ERROR,
    name="catalogId必须为extended",
    description="createSurface.catalogId 必须等于 'ohos.a2ui.extended.catalog'，否则 Form 渲染层不识别。",
    tags=("L0", "protocol"),
)
def check_catalog(ctx: CardContext) -> list[Violation]:
    actual = ctx.create_surface.get("catalogId")
    if actual != "ohos.a2ui.extended.catalog":
        return [Violation(
            rule_id="R-L0-004",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=f"createSurface.catalogId 必须为 'ohos.a2ui.extended.catalog'，实际为 {actual!r}",
            location="line 1",
        )]
    return []


@rule(
    "R-L0-005",
    Severity.ERROR,
    name="surfaceId一致性",
    description="三行消息的 surfaceId 必须完全相等，否则卡片无法正确关联渲染。",
    tags=("L0", "protocol"),
)
def check_surface_id(ctx: CardContext) -> list[Violation]:
    ids = [
        ctx.create_surface.get("surfaceId"),
        ctx.update_components.get("surfaceId"),
        ctx.update_data_model.get("surfaceId"),
    ]
    non_null = [i for i in ids if i is not None]
    if len(set(non_null)) > 1:
        return [Violation(
            rule_id="R-L0-005",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=(
                f"surfaceId 不一致：createSurface={ids[0]!r}, "
                f"updateComponents={ids[1]!r}, updateDataModel={ids[2]!r}"
            ),
            location="surfaceId",
        )]
    return []


@rule(
    "R-L0-006",
    Severity.ERROR,
    name="createSurface尺寸合规",
    description="createSurface.width/height 必须等于卡片尺寸对应值（2x2→140x140，2x4→300x140），其它尺寸一律不接受。",
    tags=("L0", "protocol"),
)
def check_surface_dimensions(ctx: CardContext) -> list[Violation]:
    w, h = ctx.create_surface.get("width"), ctx.create_surface.get("height")
    if w not in (WIDTH_2x2, WIDTH_2x4) or h != HEIGHT:
        return [Violation(
            rule_id="R-L0-006",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=(
                f"createSurface 尺寸必须为 140x140(2x2) 或 300x140(2x4)，"
                f"实际为 {w}x{h}"
            ),
            location="createSurface",
        )]
    return []


@rule(
    "R-L0-007",
    Severity.ERROR,
    name="components必须为数组",
    description="updateComponents.components 必须是 JSON 数组，否则组件树无法解析。",
    tags=("L0", "protocol"),
)
def check_components_is_list(ctx: CardContext) -> list[Violation]:
    comps = ctx.update_components.get("components")
    if not isinstance(comps, list):
        return [Violation(
            rule_id="R-L0-007",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=f"updateComponents.components 必须为数组，实际类型 {type(comps).__name__}",
            location="updateComponents",
        )]
    return []


@rule(
    "R-L0-019",
    Severity.ERROR,
    name="模板children键合法",
    description="模板 children 对象只允许包含 componentId 与 path 两个键。",
    tags=("L0", "protocol"),
)
def check_template_children_keys(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        children = c.get("children")
        if isinstance(children, dict):
            extra = set(children.keys()) - {"componentId", "path"}
            if extra:
                out.append(Violation(
                    rule_id="R-L0-019",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {c.get('id')!r} 模板 children 含非法键 {sorted(extra)!r}",
                    location=c.get("id"),
                ))
    return out


@rule(
    "R-L0-020",
    Severity.ERROR,
    name="模板componentId存在",
    description="模板 children.componentId 必须引用已声明的组件 id。",
    tags=("L0", "protocol"),
)
def check_template_component_id(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        children = c.get("children")
        if isinstance(children, dict):
            cid_target = children.get("componentId")
            if isinstance(cid_target, str) and cid_target not in ctx.by_id:
                out.append(Violation(
                    rule_id="R-L0-020",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {c.get('id')!r} 模板 componentId={cid_target!r} 不存在",
                    location=c.get("id"),
                ))
    return out


@rule(
    "R-L0-021",
    Severity.ERROR,
    name="模板path必须为绝对指针",
    description="模板 children.path 必须是字符串且以 / 开头（绝对 JSON Pointer）。",
    tags=("L0", "protocol"),
)
def check_template_path(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        children = c.get("children")
        if isinstance(children, dict):
            p = children.get("path")
            if not isinstance(p, str) or not p.startswith("/"):
                out.append(Violation(
                    rule_id="R-L0-021",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {c.get('id')!r} 模板 path 必须是绝对 JSON Pointer，实际 {p!r}",
                    location=c.get("id"),
                ))
    return out
