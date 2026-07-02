# -*- coding: utf-8 -*-
"""场景定义:11 原场景 + 19 扩展场景。
每个场景含:配额 quota、自然能力亲和 affinity(对该场景更自然的轴值加权)。
affinity 中列出的轴值会被加权采样;未列出的轴按全局配额分布均匀采样。
"""

SCENARIOS = [
    # ───────── 原 11 场景(有素材库支持,query 可点名图标) ─────────
    {
        "id": "01-low-power", "name": "低电模式", "quota": 420,
        "desc": "电量监控、省电模式、充电宝导航、设备状态",
        "affinity": {
            "component": {"Progress": 3, "Stack": 2, "Text": 2, "Button": 2},
            "click": {"intent_setting_switch": 4, "deeplink_settings": 3, "intent_navigate": 2},
            "status": {"warning": 3, "alert": 2, "none": 1},
            "gradient": {"action-fill": 2, "temporal-band": 1},
            "surface": {"colored-root": 2, "dark-stage": 2},
            "asset": {"icon": 3},
        },
    },
    {
        "id": "02-earphone-music", "name": "耳机音乐", "quota": 420,
        "desc": "耳机电量、播控、歌单入口、连接触发、歌词",
        "affinity": {
            "component": {"Image": 3, "Button": 3, "Row": 2, "Progress": 2},
            "click": {"deeplink_music": 5, "none": 1},
            "gradient": {"ambient-band": 3},
            "surface": {"soft-material": 3, "image-derived": 2},
            "composition": {"hero-left": 3, "split-action": 2},
            "asset": {"icon": 3},
        },
    },
    {
        "id": "03-anti-addiction", "name": "防沉迷", "quota": 380,
        "desc": "应用使用时长、锁屏、儿童管控、时段限制",
        "affinity": {
            "component": {"Progress": 3, "Checkbox": 2, "Column": 2},
            "click": {"deeplink_settings": 4, "intent_setting_switch": 3},
            "status": {"warning": 3, "alert": 2},
            "binding": {"expression": 2, "formatString": 2},
            "asset": {"icon": 2},
        },
    },
    {
        "id": "04-focus", "name": "专注模式", "quota": 380,
        "desc": "番茄钟、免打扰、白噪音、专注统计",
        "affinity": {
            "component": {"Progress": 3, "Text": 3, "Column": 2},
            "click": {"intent_setting_switch": 4, "deeplink_clock": 2},
            "status": {"none": 2, "confirm": 1},
            "gradient": {"temporal-band": 2},
            "composition": {"meter-focus": 3},
            "asset": {"glyph": 2},
        },
    },
    {
        "id": "05-agenda", "name": "议程提醒", "quota": 420,
        "desc": "会议日程、楼层房间、入会、议程时间轴",
        "affinity": {
            "component": {"List": 4, "Text": 3, "Divider": 2, "Column": 2},
            "click": {"intent_calendar": 5, "deeplink_clock": 2},
            "data": {"calendar": 4},
            "template": {"list": 4, "column": 2},
            "status": {"warning": 1, "none": 2},
            "asset": {"icon": 2},
        },
    },
    {
        "id": "06-memory-clean", "name": "内存清理", "quota": 380,
        "desc": "存储空间、一键清理、缓存扫描、设备电量",
        "affinity": {
            "component": {"Progress": 4, "Button": 3, "Ring": 0},
            "click": {"deeplink_settings": 3, "intent_setting_switch": 2},
            "status": {"warning": 2, "alert": 1},
            "gradient": {"action-fill": 2},
            "composition": {"meter-focus": 3, "split-action": 2},
            "asset": {"icon": 2},
        },
    },
    {
        "id": "07-sports-event", "name": "赛事提醒", "quota": 380,
        "desc": "赛事倒计时、比分、控球射门数据、联赛",
        "affinity": {
            "component": {"Text": 3, "Row": 3, "Stack": 2, "List": 2},
            "click": {"deeplink_health": 4, "intent_calendar": 2},
            "status": {"warning": 2, "confirm": 1, "alert": 1},
            "gradient": {"temporal-band": 2, "ambient-band": 1},
            "surface": {"dark-stage": 2, "colored-root": 2},
            "composition": {"hero-left": 2, "split-action": 2},
            "asset": {"icon": 2},
        },
    },
    {
        "id": "08-sleep", "name": "睡眠卡片", "quota": 400,
        "desc": "睡眠报告、深睡浅睡、打分、改善建议、手环",
        "affinity": {
            "component": {"Progress": 3, "Stack": 3, "Column": 2, "List": 2},
            "click": {"deeplink_clock": 4, "deeplink_health": 2},
            "status": {"warning": 2, "alert": 1},
            "gradient": {"ambient-band": 3, "temporal-band": 2},
            "surface": {"dark-stage": 4},
            "composition": {"meter-focus": 2, "ambient-root": 3},
            "asset": {"icon": 2},
        },
    },
    {
        "id": "09-weather-care", "name": "天气关怀", "quota": 420,
        "desc": "父母关怀、温感冒指数、一键拨号、降温提醒",
        "affinity": {
            "component": {"Text": 3, "Image": 2, "Button": 2, "Stack": 2},
            "click": {"clickToCallPhone": 5, "deeplink_weather": 3},
            "data": {"weather": 4},
            "status": {"warning": 2, "alert": 1},
            "gradient": {"ambient-band": 2},
            "surface": {"image-derived": 2, "colored-root": 2},
            "asset": {"icon": 3},
        },
    },
    {
        "id": "10-rainy-taxi", "name": "雨天打车", "quota": 400,
        "desc": "雨天叫车、多平台、排队等待、定位拨号",
        "affinity": {
            "component": {"Text": 3, "Row": 2, "Progress": 2, "Button": 2},
            "click": {"clickToCallPhone": 3, "intent_navigate": 4, "deeplink_weather": 2},
            "data": {"weather": 2},
            "status": {"warning": 2, "alert": 1},
            "gradient": {"ambient-band": 1},
            "asset": {"icon": 2},
        },
    },
    # ───────── 扩展 19 场景(asset-light,query 不提图片素材) ─────────
    {
        "id": "11-fitness", "name": "运动健身", "quota": 340,
        "desc": "步数、卡路里、跑步、运动目标达标",
        "affinity": {
            "component": {"Progress": 4, "Text": 3, "Column": 2},
            "click": {"deeplink_health": 5},
            "status": {"confirm": 3, "warning": 1},
            "gradient": {"action-fill": 2},
            "composition": {"meter-focus": 3, "hero-top": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "12-finance", "name": "记账理财", "quota": 320,
        "desc": "月度预算、支出分类、记账、余额",
        "affinity": {
            "component": {"Progress": 3, "Text": 3, "Divider": 2, "List": 2},
            "binding": {"expression": 2, "formatString": 2},
            "template": {"list": 2, "column": 2},
            "status": {"warning": 2, "alert": 1},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "13-health-reminder", "name": "喝水吃药提醒", "quota": 320,
        "desc": "每日饮水、服药打卡、用药提醒",
        "affinity": {
            "component": {"Progress": 3, "Checkbox": 4, "Column": 2},
            "click": {"deeplink_clock": 3},
            "status": {"warning": 2, "confirm": 2},
            "binding": {"path": 2, "formatString": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "14-commute", "name": "通勤导航", "quota": 320,
        "desc": "路况、通行时间、拥堵、事故、导航",
        "affinity": {
            "component": {"Row": 3, "Progress": 2, "Text": 3, "Divider": 2},
            "click": {"intent_navigate": 5},
            "status": {"alert": 3, "warning": 2},
            "gradient": {"action-fill": 2},
            "composition": {"split-action": 2, "hero-left": 2},
            "asset": {"glyph": 2},
        },
    },
    {
        "id": "15-smart-home", "name": "智能家居", "quota": 320,
        "desc": "灯光、空调温控、窗帘、大按钮控制",
        "affinity": {
            "component": {"Button": 5, "Row": 3, "Column": 2, "Checkbox": 2},
            "click": {"intent_setting_switch": 4, "deeplink_settings": 2},
            "status": {"confirm": 3, "none": 1},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "16-travel-ticket", "name": "票务行程", "quota": 320,
        "desc": "航班火车、登机牌、行程倒计时",
        "affinity": {
            "component": {"Text": 3, "Divider": 3, "Column": 2, "List": 2},
            "click": {"intent_calendar": 3, "none": 1},
            "data": {"calendar": 2},
            "status": {"warning": 2, "alert": 1},
            "gradient": {"temporal-band": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "17-queue", "name": "排队叫号", "quota": 300,
        "desc": "餐厅排队、医院叫号、取号提醒",
        "affinity": {
            "component": {"Text": 4, "Progress": 2, "Stack": 2},
            "click": {"clickToCallPhone": 3, "none": 1},
            "status": {"warning": 2, "confirm": 1},
            "composition": {"meter-focus": 2, "hero-top": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "18-carpool", "name": "拼车出行", "quota": 300,
        "desc": "上下班拼车、顺路匹配、费用分摊",
        "affinity": {
            "component": {"Row": 3, "Text": 3, "Divider": 2, "List": 2},
            "click": {"intent_navigate": 4},
            "status": {"confirm": 2, "warning": 1},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "19-photo-album", "name": "相册管理", "quota": 300,
        "desc": "清理重复照片、人脸分组、旅行相册",
        "affinity": {
            "component": {"Image": 4, "Checkbox": 3, "List": 2, "Grid": 0},
            "click": {"none": 2, "intent_setting_switch": 1},
            "status": {"warning": 2, "alert": 1},
            "asset": {"glyph": 2},
        },
    },
    {
        "id": "20-notif-aggregate", "name": "通知聚合", "quota": 320,
        "desc": "钉钉群消息、作业通知、工作消息聚合",
        "affinity": {
            "component": {"List": 5, "Text": 3, "Divider": 2, "Column": 2},
            "template": {"list": 4, "column": 2},
            "status": {"warning": 3, "alert": 2},
            "binding": {"expression": 2, "path": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "21-stocks", "name": "股票基金", "quota": 320,
        "desc": "持仓、涨跌幅、盈亏汇总、行情",
        "affinity": {
            "component": {"List": 4, "Text": 3, "Divider": 3, "Row": 2},
            "template": {"list": 3, "row": 2},
            "status": {"confirm": 3, "alert": 3, "warning": 2},
            "binding": {"expression": 3, "formatString": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "22-express", "name": "快递物流", "quota": 320,
        "desc": "多包裹、物流状态、预计送达、取件",
        "affinity": {
            "component": {"List": 4, "Text": 3, "Divider": 2, "Progress": 2},
            "template": {"list": 4},
            "status": {"confirm": 2, "warning": 1},
            "binding": {"path": 2, "formatString": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "23-countdown", "name": "倒计时纪念日", "quota": 320,
        "desc": "考试倒计时、纪念日、生日、重要日期",
        "affinity": {
            "component": {"Stack": 4, "Text": 3, "Progress": 2},
            "data": {"calendar": 3},
            "status": {"none": 2, "confirm": 1},
            "gradient": {"temporal-band": 3, "ambient-band": 1},
            "surface": {"dark-stage": 2, "colored-root": 2},
            "composition": {"hero-top": 3, "meter-focus": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "24-todo", "name": "待办清单", "quota": 340,
        "desc": "任务勾选、清单、完成进度、提醒",
        "affinity": {
            "component": {"Checkbox": 6, "List": 4, "Column": 2, "Progress": 2},
            "binding": {"path": 3},  # Checkbox 双向绑定走 path 兜底
            "template": {"list": 4, "column": 2},
            "click": {"none": 3, "deeplink_clock": 2},
            "status": {"confirm": 3, "warning": 1},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "25-reading", "name": "阅读听书", "quota": 280,
        "desc": "阅读进度、听书、书架、时长统计",
        "affinity": {
            "component": {"Progress": 4, "List": 2, "Text": 3},
            "click": {"deeplink_music": 3, "none": 1},
            "status": {"confirm": 2, "none": 2},
            "binding": {"formatString": 2, "path": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "26-group-buy", "name": "拼单团购", "quota": 300,
        "desc": "奶茶拼单、起送凑单、口味选择",
        "affinity": {
            "component": {"Checkbox": 4, "List": 3, "Text": 2, "Divider": 2},
            "template": {"list": 3},
            "status": {"warning": 2, "confirm": 1},
            "binding": {"expression": 2, "path": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "27-utility-bill", "name": "水电缴费", "quota": 300,
        "desc": "电费水费燃气费、账单、一键缴费",
        "affinity": {
            "component": {"Text": 3, "Divider": 3, "Button": 3, "Column": 2},
            "status": {"warning": 3, "alert": 2},
            "binding": {"formatString": 3, "expression": 2},
            "asset": {"glyph": 3},
        },
    },
    {
        "id": "28-veggie-price", "name": "菜价比价", "quota": 280,
        "desc": "菜价识别、均价对比、便宜推荐",
        "affinity": {
            "component": {"Row": 3, "List": 2, "Text": 3, "Divider": 2},
            "status": {"warning": 2, "confirm": 1},
            "binding": {"expression": 2, "formatString": 2},
            "asset": {"glyph": 2},
        },
    },
    {
        "id": "29-elderly-care", "name": "老人关怀看护", "quota": 320,
        "desc": "摔倒检测、摄像头、视频通话、健康",
        "affinity": {
            "component": {"Image": 3, "Button": 3, "Text": 2, "Stack": 2},
            "click": {"clickToCallPhone": 5, "deeplink_health": 2},
            "status": {"alert": 4, "warning": 3},
            "surface": {"image-derived": 2, "dark-stage": 1},
            "asset": {"glyph": 2},
        },
    },
    {
        "id": "30-pet-feeder", "name": "宠物喂食", "quota": 280,
        "desc": "自动喂食器、出粮提醒、余粮、补喂",
        "affinity": {
            "component": {"Progress": 3, "Text": 3, "Button": 2, "Column": 2},
            "status": {"warning": 3, "alert": 2, "confirm": 1},
            "binding": {"formatString": 2, "path": 2},
            "asset": {"glyph": 3},
        },
    },
]


def scenario_by_id(sid):
    for s in SCENARIOS:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def total_quota():
    return sum(s["quota"] for s in SCENARIOS)
