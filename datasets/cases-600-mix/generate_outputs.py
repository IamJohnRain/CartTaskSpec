#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


BASE = Path(__file__).resolve().parent
INPUT = BASE / "600Cases.tagged.jsonl"

PALETTE = {
    "none": ("#FFF7F8FA", "#FF0A59F7", "#E5000000", "#99000000", "#FFFFFFFF"),
    "confirm": ("#FFF3FAF6", "#FF008A4A", "#E5000000", "#99000000", "#FFFFFFFF"),
    "warning": ("#FFFFF7E8", "#FFD76000", "#E5000000", "#9A4B00", "#FFFFFFFF"),
    "alert": ("#FFFFF1F0", "#FFC73426", "#E5000000", "#99000000", "#FFFFFFFF"),
}

SCENARIO_DATA = {
    "01-low-power": ("battery", "当前电量", "18%", "电量偏低", "建议开启省电"),
    "02-earphone-music": ("device", "Free Clip 2", "47% / 95%", "已连接", "打开歌单"),
    "03-anti-addiction": ("usage", "屏幕时间", "3.5h", "接近上限", "去设置"),
    "04-focus": ("focus", "专注中", "25分", "免打扰开启", "打开时钟"),
    "05-agenda": ("agenda", "下一场会议", "10:30", "产品评审", "看日程"),
    "06-memory-clean": ("storage", "可用空间", "24%", "建议清理", "去存储"),
    "07-sports-event": ("match", "比赛提醒", "19:30", "赛前准备", "查看"),
    "08-sleep": ("sleep", "睡眠得分", "82", "深睡 2h10m", "详情"),
    "09-weather-care": ("weather", "爸妈天气", "12度", "注意保暖", "打电话"),
    "10-rainy-taxi": ("taxi", "雨天出行", "8分钟", "建议提前叫车", "导航"),
    "11-fitness": ("fitness", "今日步数", "8260", "已达 82%", "运动"),
    "12-finance": ("finance", "本月已花", "¥3245", "剩余 35%", "记一笔"),
    "13-health-reminder": ("medicine", "用药提醒", "20:30", "晚饭后服用", "设闹钟"),
    "14-commute": ("commute", "通勤路况", "36分钟", "拥堵偏高", "导航"),
    "15-smart-home": ("home", "客厅设备", "24度", "灯光已开", "去设置"),
    "16-travel-ticket": ("trip", "行程提醒", "明日 08:20", "提前值机", "看日程"),
    "17-queue": ("queue", "当前叫号", "A128", "前方 6 桌", "联系店家"),
    "18-carpool": ("carpool", "拼车匹配", "2人", "18:10 出发", "导航"),
    "19-photo-album": ("album", "相册清理", "126张", "重复照片", "处理"),
    "20-notif-aggregate": ("notice", "重要通知", "5条", "2条待处理", "查看"),
    "21-stocks": ("stocks", "持仓盈亏", "+2.8%", "今日上涨", "行情"),
    "22-express": ("express", "快递状态", "3件", "1件待取", "查看"),
    "23-countdown": ("countdown", "考试倒计时", "12天", "复习冲刺", "日程"),
    "24-todo": ("todo", "待办进度", "3/5", "还有 2 项", "提醒"),
    "25-reading": ("reading", "阅读进度", "68%", "今晚继续", "听书"),
    "26-group-buy": ("groupbuy", "拼单进度", "¥48", "差 ¥12 起送", "凑单"),
    "27-utility-bill": ("bill", "本月电费", "¥86", "3天后到期", "缴费"),
    "28-veggie-price": ("veggie", "今日菜价", "¥3.8/斤", "比昨日低", "比价"),
    "29-elderly-care": ("care", "健康日报", "95", "风险偏高", "立即呼救"),
    "30-pet-feeder": ("pet", "余粮", "23%", "下次 19:00", "立即补喂"),
}


def safe_name(text):
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", text.strip())
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "case"


def read_cases():
    rows = []
    with INPUT.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                item = json.loads(line)
                item["_line"] = i
                rows.append(item)
    return rows


def event_for(click, scenario, query):
    if click == "none":
        return []
    if click == "clickToCallPhone":
        phone = re.search(r"1[3-9]\d{9}", query)
        return [{"call": "clickToCallPhone", "args": {"phoneNumber": phone.group(0) if phone else "15012345678"}}]
    if click == "deeplink_music":
        return [{"call": "clickToDeeplink", "args": {"bundleName": "", "abilityName": "", "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}]
    if click == "deeplink_health":
        uri = "huaweischeme://healthapp/router/sleepDetail" if scenario == "08-sleep" else "huaweischeme://healthapp/home/sport?sportType=2"
        return [{"call": "clickToDeeplink", "args": {"bundleName": "", "abilityName": "", "uri": uri}}]
    if click == "deeplink_weather":
        return [{"call": "clickToDeeplink", "args": {"bundleName": "", "abilityName": "", "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="}}]
    if click == "deeplink_clock":
        return [{"call": "clickToDeeplink", "args": {"bundleName": "com.huawei.hmos.clock", "abilityName": "com.huawei.hmos.clock.phone", "uri": ""}}]
    if click == "intent_calendar":
        return [{"call": "clickToIntent", "args": {"intentName": "ViewCalendarEvent", "params": {"entityId": "event_001"}}}]
    if click == "intent_navigate":
        return [{"call": "clickToIntent", "args": {"intentName": "StartNavigate", "params": {"dstLocation": {"latitude": "22.5431", "longitude": "114.0579"}, "trafficpe": "Drive"}}}]
    if click == "intent_setting_switch":
        return [{"call": "clickToIntent", "args": {"intentName": "SetSettingSwitch", "params": {"appBundleName": "com.huawei.hmos.settings", "itemName": "battery_saving_mode", "switchFlag": 0}}}]
    if click == "deeplink_settings":
        uri = "storage_settings" if scenario == "06-memory-clean" else "battery" if scenario == "01-low-power" else "parent_control" if scenario == "03-anti-addiction" else "intelligent_scene_entry"
        return [{"call": "clickToDeeplink", "args": {"bundleName": "com.huawei.hmos.settings", "abilityName": "com.huawei.hmos.settings.MainAbility", "uri": uri}}]
    return []


def build_model(row):
    key, title, primary, secondary, cta = SCENARIO_DATA[row["scenario"]]
    status = row["axes"].get("status", "none")
    value = {
        key: {
            "title": title,
            "primaryText": primary,
            "secondaryText": secondary,
            "ctaText": cta,
            "statusText": {"none": "正常", "confirm": "已完成", "warning": "提醒", "alert": "告警"}.get(status, "正常"),
            "progress": 82 if status == "confirm" else 67 if status == "none" else 35 if status == "warning" else 18,
        }
    }
    if row["axes"].get("template") in {"list", "column", "row"} or row["axes"].get("data") in {"calendar", "weather"}:
        value[key]["items"] = [
            {"label": "当前", "value": primary},
            {"label": "提醒", "value": secondary},
            {"label": "状态", "value": value[key]["statusText"]},
        ]
    return key, value


def task_spec(row):
    key, value = build_model(row)
    size = row["axes"].get("size", "2x2")
    return {
        "userQuery": row["query"],
        "size": size if size in {"2x2", "2x4"} else "2x2",
        "eventCandidates": event_for(row["axes"].get("click", "none"), row["scenario"], row["query"]),
        "dataModel": {"value": value},
        "assetCandidates": [],
    }, key


def text(id_, content, xw, h, fs, color, weight=500, align=None):
    styles = {"width": xw, "height": h, "fontSize": fs, "fontWeight": weight, "fontColor": color, "maxLines": 1, "textOverflow": "none"}
    if align:
        styles["textAlign"] = align
    return {"id": id_, "component": "Text", "content": content, "styles": styles}


def button(label, event, width, color):
    comp = {"id": "action_button", "component": "Button", "label": label, "styles": {"width": width, "height": 32, "borderRadius": 16, "backgroundColor": color, "fontSize": 14, "fontWeight": 500, "fontColor": "#FFFFFFFF"}}
    if event:
        comp["onClick"] = [event]
    return comp


def genui(spec, key, row, idx):
    size = spec["size"]
    width = 140 if size == "2x2" else 300
    radius = 18 if size == "2x2" else 22
    status = row["axes"].get("status", "none")
    bg, accent, fg, muted, on_accent = PALETTE.get(status, PALETTE["none"])
    surface_id = f"case_{idx:03d}_{safe_name(row['scenario'])}"
    data = spec["dataModel"]["value"][key]
    event = spec["eventCandidates"][0] if spec["eventCandidates"] else None

    create = {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": "ohos.a2ui.extended.catalog", "width": width, "height": 140}}

    if size == "2x4":
        components = [
            {"id": "root", "component": "Row", "children": ["metric_panel", "info_col"], "itemMargin": 12, "wrap": "noWrap", "styles": {"width": 300, "height": 140, "padding": 12, "borderRadius": radius, "clip": True, "backgroundColor": bg, "justifyContent": "start", "alignItems": "center"}},
            {"id": "metric_panel", "component": "Column", "children": ["status_text", "primary_text", "progress_bar"], "itemMargin": 8, "styles": {"width": 112, "height": 116, "padding": 10, "borderRadius": 16, "backgroundColor": "#FFFFFFFF", "justifyContent": "center", "alignItems": "center"}},
            text("status_text", f"{{{{ $__dataModel.{key}.statusText }}}}", 92, 18, 12, muted, 500, "center"),
            text("primary_text", f"{{{{ $__dataModel.{key}.primaryText }}}}", 92, 32, 20, accent, 700, "center"),
            {"id": "progress_bar", "component": "Progress", "value": f"{{{{ $__dataModel.{key}.progress }}}}", "total": 100, "styles": {"width": 92, "height": 8, "type": "linear", "color": accent, "backgroundColor": "#19000000", "borderRadius": 4}},
            {"id": "info_col", "component": "Column", "children": ["title_text", "secondary_text", "detail_text"] + (["action_button"] if event else []), "itemMargin": 8, "styles": {"width": 152, "height": 116, "justifyContent": "center", "alignItems": "start"}},
            text("title_text", f"{{{{ $__dataModel.{key}.title }}}}", 152, 22, 18, fg, 700),
            text("secondary_text", f"{{{{ $__dataModel.{key}.secondaryText }}}}", 152, 18, 14, muted, 500),
            text("detail_text", "数据已同步", 152, 16, 12, muted, 400),
        ]
        if event:
            components.append(button(f"{{{{ $__dataModel.{key}.ctaText }}}}", event, 112, accent))
    else:
        children = ["title_text", "primary_text", "secondary_text", "progress_bar"]
        if event:
            children.append("action_button")
        components = [
            {"id": "root", "component": "Column", "children": children, "itemMargin": 8, "styles": {"width": 140, "height": 140, "padding": 12, "borderRadius": radius, "clip": True, "backgroundColor": bg, "justifyContent": "center", "alignItems": "start"}},
            text("title_text", f"{{{{ $__dataModel.{key}.title }}}}", 116, 20, 16, fg, 700),
            text("primary_text", f"{{{{ $__dataModel.{key}.primaryText }}}}", 116, 30, 20, accent, 700),
            text("secondary_text", f"{{{{ $__dataModel.{key}.secondaryText }}}}", 116, 18, 12, muted, 500),
            {"id": "progress_bar", "component": "Progress", "value": f"{{{{ $__dataModel.{key}.progress }}}}", "total": 100, "styles": {"width": 116, "height": 8, "type": "linear", "color": accent, "backgroundColor": "#19000000", "borderRadius": 4}},
        ]
        if event:
            components.append(button(f"{{{{ $__dataModel.{key}.ctaText }}}}", event, 96, accent))

    update = {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "root": "root", "components": components}}
    model = {"version": "v0.9", "updateDataModel": {"surfaceId": surface_id, "path": "/", "value": spec["dataModel"]["value"]}}
    return "\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in (create, update, model)) + "\n"


def validate(spec, dsl, cardspec):
    lines = [json.loads(line) for line in dsl.splitlines() if line.strip()]
    assert len(lines) == 3
    assert "createSurface" in lines[0] and "updateComponents" in lines[1] and "updateDataModel" in lines[2]
    assert lines[2]["updateDataModel"]["value"] == spec["dataModel"]["value"]
    assert cardspec["suggestSize"] == spec["size"]
    root = next(c for c in lines[1]["updateComponents"]["components"] if c["id"] == "root")
    assert root["styles"]["width"] == (140 if spec["size"] == "2x2" else 300)
    assert root["styles"]["height"] == 140


def write_case(row):
    idx = row["_line"]
    case_dir = BASE / f"Case-{idx:03d}-{safe_name(row['scenario'])}"
    case_dir.mkdir(parents=True, exist_ok=True)
    spec, key = task_spec(row)
    cardspec = {"suggestSize": spec["size"]}
    dsl = genui(spec, key, row, idx)
    validate(spec, dsl, cardspec)
    (case_dir / "query.txt").write_text(row["query"] + "\n", encoding="utf-8")
    (case_dir / "task.taskSpec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (case_dir / "card.cardspec.json").write_text(json.dumps(cardspec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (case_dir / "card.dsl.jsonl").write_text(dsl, encoding="utf-8")
    return str(case_dir.relative_to(BASE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=10**9)
    args = parser.parse_args()
    rows = [r for r in read_cases() if args.start <= r["_line"] <= args.end]
    for row in rows:
        print(write_case(row))
    print(f"generated={len(rows)} start={args.start} end={args.end}")


if __name__ == "__main__":
    main()
