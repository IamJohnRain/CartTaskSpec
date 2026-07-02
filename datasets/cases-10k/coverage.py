# -*- coding: utf-8 -*-
"""A2UI 卡片 Query 覆盖矩阵定义。
编码自 harmony-card-generation-datamodel-first skill 的 15 维能力清单。
每个轴有明确枚举值与全局下限配额(merge 后必须满足)。
"""

# ───────── 尺寸 ─────────
SIZE = ["2x2", "2x4"]

# ───────── 组件(10 种合法组件) ─────────
COMPONENTS = [
    "Text", "Image", "Divider", "Progress", "Button", "Checkbox",
    "Row", "Column", "List", "Stack",
]

# ───────── 绑定方式(4 种) ─────────
BINDING = ["expression", "path", "formatString", "literal"]

# ───────── 点击事件(call 类型) ─────────
CLICK = [
    "none",
    "clickToCallPhone",
    "deeplink_settings", "deeplink_weather", "deeplink_clock",
    "deeplink_music", "deeplink_health",
    "intent_calendar", "intent_navigate", "intent_setting_switch",
]

# ───────── 数据能力 ─────────
DATA = ["static", "calendar", "weather"]

# ───────── 表面策略(7) ─────────
SURFACE = [
    "plain", "tinted-surface", "colored-root", "split-surface",
    "image-derived", "dark-stage", "soft-material",
]

# ───────── 构图原型(6) ─────────
COMPOSITION = [
    "hero-top", "hero-left", "split-action", "paper-panel",
    "meter-focus", "ambient-root",
]

# ───────── 状态色 ─────────
STATUS = ["none", "confirm", "warning", "alert"]

# ───────── 渐变 band ─────────
GRADIENT = ["none", "ambient-band", "temporal-band", "action-fill"]

# ───────── 素材策略 ─────────
ASSET = ["none", "glyph", "icon"]

# ───────── 模板循环 ─────────
TEMPLATE = ["none", "row", "column", "list"]

# ───────── 每个轴枚举值的「全局下限配额」(merge 后必须达到) ─────────
# 这些是硬下限;实际产出会超过(每条 query 命中多个轴)。
MIN_QUOTA = {
    "size": {"2x2": 4500, "2x4": 4500},
    "component": {  # 每条 query 打 1 个主组件标签
        "Text": 700, "Image": 700, "Progress": 900, "Button": 900,
        "Row": 700, "Column": 700, "Divider": 400,
        "Checkbox": 350, "List": 400, "Stack": 450,
    },
    "binding": {
        "expression": 2500, "path": 1500, "formatString": 1500, "literal": 2000,
    },
    "click": {
        "none": 1200,
        "clickToCallPhone": 700,
        "deeplink_settings": 350, "deeplink_weather": 350, "deeplink_clock": 350,
        "deeplink_music": 350, "deeplink_health": 350,
        "intent_calendar": 350, "intent_navigate": 350, "intent_setting_switch": 350,
    },
    "data": {"static": 4000, "calendar": 2500, "weather": 2500},
    "surface": {s: 400 for s in SURFACE},
    "composition": {c: 500 for c in COMPOSITION},
    "status": {"none": 3000, "confirm": 1000, "warning": 1000, "alert": 1000},
    "gradient": {"none": 3500, "ambient-band": 1500, "temporal-band": 1500, "action-fill": 1500},
    "asset": {"none": 1500, "glyph": 2000, "icon": 3500},
    "template": {"none": 6000, "row": 450, "column": 450, "list": 450},
}

AXES = [
    "size", "component", "binding", "click", "data",
    "surface", "composition", "status", "gradient", "asset", "template",
]


def axis_values(axis):
    return {
        "size": SIZE, "component": COMPONENTS, "binding": BINDING,
        "click": CLICK, "data": DATA, "surface": SURFACE,
        "composition": COMPOSITION, "status": STATUS, "gradient": GRADIENT,
        "asset": ASSET, "template": TEMPLATE,
    }[axis]
