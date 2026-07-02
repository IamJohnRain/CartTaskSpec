# -*- coding: utf-8 -*-
"""单场景 Query 批量生成器。
用法: python gen_cases.py --scenario 01-low-power [--count N] [--batch 12]
调用 GLM(glm-5.2) 按「覆盖配置」生成自然中文 query,写入 scenarios/<id>/cases.jsonl。

设计:
- 每条 query 携带一组覆盖配置(11 个轴的取值),引导模型产出能命中该能力分支的需求。
- 覆盖配置采样:场景亲和权重(0.6) + 全局配额分布(0.4),保证冷门组件/事件也能覆盖。
- 产出 cases.jsonl,每行 {scenario, query, axes:{...}}。
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from coverage import MIN_QUOTA, axis_values  # noqa: E402
from scenarios_def import scenario_by_id  # noqa: E402

API_URL = "https://api.minimaxi.com/v1/chat/completions"
API_KEY = ""
MODEL = "MiniMax-M3"


def load_env(env_path: Path):
    """手动解析 .env(不依赖 python-dotenv)。"""
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip()
        # 不覆盖已有环境变量(便于 CI/系统 env 覆盖)
        os.environ.setdefault(k, v)


def get_api_config(name: str):
    """name: 'minimax' or 'glm'."""
    load_env(HERE.parent.parent / ".env")
    prefix = "MINIMAX" if name == "minimax" else "GLM"
    url = os.environ[f"{prefix}_API_URL"]
    key = os.environ[f"{prefix}_API_KEY"]
    model = os.environ[f"{prefix}_MODEL"]
    return url, key, model

SEED_FILE = HERE.parent.parent / "100Cases.txt"

# 场景 id → 种子关键词(匹配 100Cases.txt 的 ## 标题)
SEED_MAP = {
    "01-low-power": "低电模式", "02-earphone-music": "耳机音乐",
    "03-anti-addiction": "防沉迷", "04-focus": "专注模式",
    "05-agenda": "议程提醒", "06-memory-clean": "内存清理",
    "07-sports-event": "赛事提醒", "08-sleep": "睡眠卡片",
    "09-weather-care": "天气关怀", "10-rainy-taxi": "雨天打车",
}

# 轴值 → 自然语言引导(给模型的可执行提示)
BRIEF = {
    "component": {
        "Text": "以文字信息为主(标题/数值/状态)",
        "Image": "需要图标或语义图片作为视觉主体",
        "Divider": "信息需要分组,用分隔线区分区块",
        "Progress": "需要一个进度/比例/环形可视化",
        "Button": "需要一个明确的点击按钮作为主动作",
        "Checkbox": "需要勾选项/可勾选的任务或选项",
        "Row": "需要左右并排排列信息",
        "Column": "需要纵向堆叠信息",
        "List": "需要一个列表展示多项同类数据",
        "Stack": "视觉需要叠加图层(如背景+前景文字、环形进度中心叠数字)",
    },
    "binding": {
        "expression": "含一个动态数据值的展示(如电量、步数、比分)",
        "path": "需要双向绑定或对象绑定的交互项(如勾选状态)",
        "formatString": "包含'固定文字+一个动态数值'的拼接(如'距离比赛还有32天','剩余47%')",
        "literal": "以固定静态文案为主",
    },
    "click": {
        "none": "主要是展示型卡片,不强求点击",
        "clickToCallPhone": "需要一键拨打电话的动作",
        "deeplink_settings": "需要跳转到系统设置(省电/存储/应用时长等)",
        "deeplink_weather": "需要跳转到天气应用",
        "deeplink_clock": "需要跳转到闹钟/时钟应用",
        "deeplink_music": "需要跳转到音乐应用歌单",
        "deeplink_health": "需要跳转到运动健康应用",
        "intent_calendar": "需要查看或进入某个日程事件",
        "intent_navigate": "需要触发地图导航到某个地点",
        "intent_setting_switch": "需要切换某个系统开关(省电模式/勿扰等)",
    },
    "data": {
        "static": "用静态示例数据即可",
        "calendar": "需要读取日历日程数据",
        "weather": "需要读取天气数据",
    },
    "surface": {
        "plain": "简洁素净的卡片表面", "tinted-surface": "带浅色调底色的表面",
        "colored-root": "整卡使用主题色背景", "split-surface": "分区不同底色",
        "image-derived": "由图片延伸出的视觉风格", "dark-stage": "深色舞台风格",
        "soft-material": "柔和材质/磨砂质感",
    },
    "composition": {
        "hero-top": "上方放主视觉/大号信息", "hero-left": "左侧放主视觉",
        "split-action": "左右分区:信息区+动作区", "paper-panel": "卡片内嵌面板块",
        "meter-focus": "以仪表盘/环形数据为焦点", "ambient-root": "整体氛围背景",
    },
    "status": {
        "none": "无需特殊状态色",
        "confirm": "出现完成/达成/已连接/可用的正向状态",
        "warning": "出现需注意/临近阈值/待处理的风险状态",
        "alert": "出现失败/危险/超限/取消的告警状态",
    },
    "gradient": {
        "none": "不需要渐变",
        "ambient-band": "适合环境氛围渐变(天气/睡眠/音乐场景)",
        "temporal-band": "适合时间/夜晚/倒计时相关的渐变",
        "action-fill": "适合运动/清理/导航/紧迫动作相关的渐变",
    },
    "asset": {
        "none": "不用图片,纯文字与色块", "glyph": "用文字字符做图标",
        "icon": "可用语义图标(仅限该场景素材库内的图标)",
    },
    "template": {
        "none": "不需要列表循环",
        "row": "需要横向重复排列多项",
        "column": "需要纵向重复排列多项",
        "list": "需要一个可滚动的重复列表",
    },
}


def load_seeds():
    """解析 100Cases.txt 的 ## 段,返回 {关键词: [query...]}"""
    text = SEED_FILE.read_text(encoding="utf-8")
    seeds = {}
    cur, buf = None, []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("##"):
            if cur:
                seeds[cur] = [x for x in buf if x]
            cur = s.lstrip("#").strip()
            buf = []
        elif s:
            buf.append(s)
    if cur:
        seeds[cur] = [x for x in buf if x]
    return seeds


def weighted_choice(weights):
    items = list(weights.items())
    total = sum(w for _, w in items)
    if total <= 0:
        items = [(k, 1) for k, _ in items]
        total = len(items)
    r = random.random() * total
    upto = 0
    for k, w in items:
        upto += w
        if upto >= r:
            return k
    return items[-1][0]


def sample_config(scenario):
    """为单条 query 采样一组覆盖配置。"""
    aff = scenario.get("affinity", {})
    cfg = {}
    for axis in ["size", "component", "binding", "click", "data", "surface",
                 "composition", "status", "gradient", "asset", "template"]:
        vals = axis_values(axis)
        weights = {}
        aff_axis = aff.get(axis, {})
        quota_axis = MIN_QUOTA.get(axis, {})
        qsum = sum(quota_axis.get(v, 0) for v in vals) or 1
        for v in vals:
            aw = aff_axis.get(v, 0)
            qw = quota_axis.get(v, 1) / qsum * len(vals)
            weights[v] = aw * 0.6 + qw * 0.4 + 0.05
        cfg[axis] = weighted_choice(weights)
    return cfg


def config_to_brief(cfg):
    parts = []
    for axis, v in cfg.items():
        if axis in BRIEF and v in BRIEF[axis]:
            parts.append(BRIEF[axis][v])
    return "；".join(parts)


def build_user_message(scenario, seeds, batch_cfgs):
    seed_lines = seeds[:6] if seeds else []
    seed_block = "\n".join(f"- {s}" for s in seed_lines) if seed_lines else "(无现成种子,自由发挥)"
    cfg_block = "\n".join(
        f"第{i+1}条要求: {config_to_brief(cfg)}"
        for i, cfg in enumerate(batch_cfgs)
    )
    return f"""你是 HarmonyOS A2UI 服务卡片的真实用户,正在向卡片生成助手提需求。
请围绕【{scenario['name']}】场景(如:{scenario['desc']})生成 {len(batch_cfgs)} 条不同的用户 Query。

参考已有同类 Query 的口吻与详略:
{seed_block}

本批每条 Query 的差异化要求(逐条对应,务必让该 Query 自然体现出对应特征):
{cfg_block}

硬性要求:
1. 每条 Query 一行,格式「序号. 内容」,序号从1到{len(batch_cfgs)},不要空行、不要解释、不要标题。
2. 详略要均衡:约1/3一句话极简、约1/3两三句中等、约1/3一段较详细(带人物痛点/布局想法/迭代抱怨)。
3. 口吻要像真实用户口语,可带情绪、带具体数字(电量%、天数、时间)、带场景细节。
4. 11个场景(query里可点名图标)以外的扩展场景,不要提具体图片素材,只描述数据、布局和动作。
5. 不要出现 DSL、JSON、技术术语(如 expression/path/Stack),只写自然需求。
6. 严格覆盖差异化要求里列出的特征,不要雷同,不要重复参考 Query 原句。
7. 禁止输出任何与上述{len(batch_cfgs)}条无关的内容。

请直接输出 {len(batch_cfgs)} 条 Query:"""


def call_api(system_msg, user_msg, retries=3, timeout=90):
    payload = {
        "model": API_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.95,
    }
    if CURRENT_API == "glm":
        payload["thinking"] = {"type": "disabled"}
    last_err = None
    for attempt in range(retries):
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(payload, f, ensure_ascii=False)
                payload_path = f.name
            try:
                result = subprocess.run(
                    ["curl", "-s", "--max-time", str(timeout), API_URL,
                     "-H", f"Authorization: Bearer {API_KEY}",
                     "-H", "Content-Type: application/json",
                     "--data-binary", f"@{payload_path}"],
                    capture_output=True, encoding="utf-8",
                )
            finally:
                try:
                    os.unlink(payload_path)
                except OSError:
                    pass
            if result.returncode != 0:
                last_err = f"curl exit {result.returncode}: {result.stderr[:300]}"
                time.sleep(2 * (attempt + 1))
                continue
            data = json.loads(result.stdout)
            if "error" in data:
                last_err = f"api error: {str(data['error'])[:300]}"
                time.sleep(2 * (attempt + 1))
                continue
            content = data["choices"][0]["message"]["content"]
            # minimax 等模型可能返回 <think>...</think> 思考块,剥离开头
            content = re.sub(r"^\s*<think>.*?</think>\s*", "", content,
                             flags=re.DOTALL)
            return content
        except Exception as e:  # noqa: BLE001
            last_err = str(e)[:300]
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"API call failed after {retries} retries: {last_err}")


LINE_RE = re.compile(r"^\s*(\d+)[.、)\]:：\s]+(.+)$")


def parse_queries(content, expected):
    out = []
    for line in content.splitlines():
        line = line.strip().lstrip("-•*").strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if m:
            out.append(m.group(2).strip())
        elif len(line) >= 8 and not line.startswith(("第", "请", "硬性", "参考")):
            out.append(line)
    return out[:expected]


def main():
    global API_URL, API_KEY, API_MODEL, CURRENT_API
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--api", choices=["minimax", "glm"], default="minimax",
                    help="LLM 后端选择:minimax(默认) 或 glm")
    ap.add_argument("--timeout", type=int, default=90,
                    help="单次 API 调用 curl 超时秒数")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    API_URL, API_KEY, API_MODEL = get_api_config(args.api)
    CURRENT_API = args.api
    print(f"[{args.scenario}] 使用 API: {args.api} ({API_MODEL})", flush=True)

    scenario = scenario_by_id(args.scenario)
    count = args.count or scenario["quota"]
    over = int(count * 1.25)  # 超量产出,供 merge 去重 + 配额选择
    out_dir = HERE / "scenarios" / scenario["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "cases.jsonl"

    seeds_all = load_seeds()
    kw = SEED_MAP.get(scenario["id"])
    seeds = seeds_all.get(kw, []) if kw else []

    SYSTEM = "你是一名擅长把抽象的产品能力要求转化为真实、自然、多样的用户口语需求的数据构造专家。"

    # 追加模式:如已存在 cases.jsonl,先统计现有行数,只补到 over。
    existing = 0
    if out_file.is_file():
        with out_file.open("r", encoding="utf-8") as fin:
            existing = sum(1 for _ in fin if _.strip())
        if existing >= over:
            print(f"[{scenario['id']}] 已存在 {existing} 条 >= 目标 {over},跳过。",
                  flush=True)
            return
        print(f"[{scenario['id']}] 已存在 {existing} 条,继续追加到 {over}", flush=True)
    produced = existing
    batch_no = 0
    with out_file.open("a", encoding="utf-8") as fout:
        while produced < over:
            n = min(args.batch, over - produced)
            batch_cfgs = [sample_config(scenario) for _ in range(n)]
            user_msg = build_user_message(scenario, seeds, batch_cfgs)
            batch_no += 1
            try:
                content = call_api(SYSTEM, user_msg, timeout=args.timeout)
            except Exception as e:  # noqa: BLE001
                print(f"[{scenario['id']}] batch {batch_no} 失败: {e}", file=sys.stderr)
                time.sleep(1)
                continue
            queries = parse_queries(content, n)
            for i, q in enumerate(queries):
                if len(q) < 6:
                    continue
                rec = {
                    "scenario": scenario["id"],
                    "scenario_name": scenario["name"],
                    "query": q,
                    "axes": batch_cfgs[i] if i < len(batch_cfgs) else batch_cfgs[-1],
                }
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                produced += 1
            print(f"[{scenario['id']}] batch {batch_no}: +{len(queries)} "
                  f"(累计 {produced}/{over})", flush=True)
            time.sleep(0.3)

    print(f"[{scenario['id']}] 完成,共 {produced} 条 -> {out_file}")


if __name__ == "__main__":
    raise SystemExit(main())
