"""L0 component rules: id, type, banned keys, banned events, children refs."""
from __future__ import annotations

from ..context import (
    ALLOWED_COMPONENTS, BANNED_COMPONENTS, BANNED_KEYS, CardContext,
)
from ..result import Severity, Violation
from ..rule import rule


@rule(
    "R-L0-008",
    Severity.ERROR,
    name="组件id非空",
    description="每个组件必须具有非空字符串 id，用于在 children / root / 模板中引用。",
    tags=("L0", "components"),
)
def check_component_id_nonempty(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id")
        if not isinstance(cid, str) or not cid:
            out.append(Violation(
                rule_id="R-L0-008",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"组件缺少非空字符串 id：{c!r}",
                location="<unknown>",
            ))
    return out


@rule(
    "R-L0-009",
    Severity.ERROR,
    name="组件id唯一",
    description="同一卡片内组件 id 必须唯一，重复会导致引用歧义。",
    tags=("L0", "components"),
)
def check_component_id_unique(ctx: CardContext) -> list[Violation]:
    seen: dict[str, int] = {}
    for c in ctx.components:
        cid = c.get("id")
        if isinstance(cid, str) and cid:
            seen[cid] = seen.get(cid, 0) + 1
    dups = sorted([k for k, v in seen.items() if v > 1])
    if dups:
        return [Violation(
            rule_id="R-L0-009",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=f"重复的组件 id：{dups}",
            location=",".join(dups),
        )]
    return []


@rule(
    "R-L0-010",
    Severity.ERROR,
    name="root引用存在",
    description="updateComponents.root 必须引用一个已声明的组件 id。",
    tags=("L0", "components"),
)
def check_root_exists(ctx: CardContext) -> list[Violation]:
    rid = ctx.root_id
    if not rid or rid not in ctx.by_id:
        return [Violation(
            rule_id="R-L0-010",
            rule_name="",
            description="",
            severity=Severity.ERROR,
            message=f"updateComponents.root={rid!r} 不在已声明组件中",
            location="updateComponents",
        )]
    return []


@rule(
    "R-L0-011",
    Severity.ERROR,
    name="禁用组件类型",
    description="Form 卡片禁止使用 TextInput/Toggle/Radio/CheckboxGroup/Select/NavContainer/Tabs/TabContent/Web/Grid/If 等组件。",
    tags=("L0", "components"),
)
def check_banned_components(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        ctype = c.get("component")
        if isinstance(ctype, str) and ctype in BANNED_COMPONENTS:
            out.append(Violation(
                rule_id="R-L0-011",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"组件 {c.get('id')!r} 禁用了组件类型 {ctype!r}",
                location=c.get("id"),
            ))
    return out


@rule(
    "R-L0-012",
    Severity.ERROR,
    name="不支持的组件类型",
    description="组件 component 字段必须是受支持集合之一（Text/Image/Divider/Progress/Button/Checkbox/Row/Column/List/Stack）。",
    tags=("L0", "components"),
)
def check_unknown_components(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        ctype = c.get("component")
        if isinstance(ctype, str) and ctype not in ALLOWED_COMPONENTS and ctype not in BANNED_COMPONENTS:
            out.append(Violation(
                rule_id="R-L0-012",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"组件 {c.get('id')!r} 使用了不支持的类型 {ctype!r}",
                location=c.get("id"),
            ))
    return out


@rule(
    "R-L0-013",
    Severity.ERROR,
    name="禁用键",
    description="禁止使用 theme / action / onAppear / onChange / onSelect / onReachStart / onReachEnd 等键。",
    tags=("L0", "components"),
)
def check_banned_keys(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, _ in ctx.walk(c):
            key = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if key in BANNED_KEYS:
                out.append(Violation(
                    rule_id="R-L0-013",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {cid!r} 含禁用键 {key!r}（路径 {path}）",
                    location=cid,
                ))
    return out


@rule(
    "R-L0-014",
    Severity.ERROR,
    name="仅允许onClick事件",
    description="DSL 只允许 onClick 一种事件；其它 on* 事件一律禁止。",
    tags=("L0", "components"),
)
def check_event_keys(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, _ in ctx.walk(c):
            key = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if key.startswith("on") and key != "onClick":
                out.append(Violation(
                    rule_id="R-L0-014",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {cid!r} 含非允许事件 {key!r}，仅允许 onClick",
                    location=cid,
                ))
    return out


@rule(
    "R-L0-015",
    Severity.ERROR,
    name="禁止网络URL",
    description="所有字符串值禁止以 http:// 或 https:// 开头，禁止引入网络资源。",
    tags=("L0", "components"),
)
def check_no_network_url(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
                out.append(Violation(
                    rule_id="R-L0-015",
                    rule_name="",
                    description="",
                    severity=Severity.ERROR,
                    message=f"组件 {cid!r} 路径 {path} 含网络 URL {value!r}",
                    location=cid,
                ))
    return out


@rule(
    "R-L0-016",
    Severity.ERROR,
    name="禁止SVG",
    description="禁止使用 SVG（包括 data:image/svg+xml 内联或 .svg 链接）。",
    tags=("L0", "components"),
)
def check_no_svg(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        for path, value in ctx.walk(c):
            if isinstance(value, str):
                low = value.lower()
                if "data:image/svg" in low or low.endswith(".svg"):
                    out.append(Violation(
                        rule_id="R-L0-016",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} 路径 {path} 含 SVG 资源",
                        location=cid,
                    ))
    return out


@rule(
    "R-L0-017",
    Severity.ERROR,
    name="children必须为数组或模板对象",
    description="children 字段必须是 id 字符串数组，或 {componentId, path} 模板对象；其它类型一律非法。",
    tags=("L0", "components"),
)
def check_children_type(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        children = c.get("children")
        if children is None:
            continue
        if isinstance(children, list):
            for ch in children:
                if not isinstance(ch, str):
                    out.append(Violation(
                        rule_id="R-L0-017",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} children 列表中含非字符串项 {ch!r}",
                        location=cid,
                    ))
        elif isinstance(children, dict):
            pass
        else:
            out.append(Violation(
                rule_id="R-L0-017",
                rule_name="",
                description="",
                severity=Severity.ERROR,
                message=f"组件 {cid!r} children 类型非法：{type(children).__name__}",
                location=cid,
            ))
    return out


@rule(
    "R-L0-018",
    Severity.ERROR,
    name="子组件id必须存在",
    description="children 列表中的每个 id 字符串必须引用一个已声明的组件。",
    tags=("L0", "components"),
)
def check_children_exist(ctx: CardContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.components:
        cid = c.get("id", "<unknown>")
        children = c.get("children")
        if isinstance(children, list):
            for ch in children:
                if isinstance(ch, str) and ch not in ctx.by_id:
                    out.append(Violation(
                        rule_id="R-L0-018",
                        rule_name="",
                        description="",
                        severity=Severity.ERROR,
                        message=f"组件 {cid!r} 引用了不存在的子组件 {ch!r}",
                        location=cid,
                    ))
    return out
