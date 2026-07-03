# -*- coding: utf-8 -*-
"""口语化 Query 批量生成器(基于 gen_cases.py 框架,适配手机输入习惯)。

差异点:
- 新 prompt:8-35 字为主,口语+语气词+少量俚语,严禁特殊符号
- 符号校验:re.search(r"[^\\u4e00-\\u9fff0-9a-zA-Z\\s。,，.!?！？\\n]", q)
- 长度校验:8 <= len(q) <= 60(主区间 8-35,过 35 仍可保留)
- 校验失败:重采样一组覆盖配置,新 prompt 再问,直到攒够或达上限
- 过量系数 1.5x(原版 1.25x,因校验会丢一些)

用法: python gen_oral.py --scenario 01-low-power [--count N] [--batch 12]
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
CASES_10K = HERE.parent / "cases-10k"
sys.path.insert(0, str(CASES_10K))
from coverage import MIN_QUOTA, axis_values  # noqa: E402
from scenarios_def import scenario_by_id  # noqa: E402

API_URL = "https://api.minimaxi.com/v1/chat/completions"
API_KEY = ""
MODEL = "MiniMax-M3"

# 允许字符:中文/数字/英文字母/空白/。,，.!?！？\n
ALLOWED_RE = re.compile(r"^[一-龥0-9a-zA-Z\s。,，.!?！？\n]+$")
# 长度区间(主 8-35;>35 但 <=60 仍接受,只是偏离主目标)
LEN_MIN, LEN_MAX = 8, 60
LEN_PRIMARY = 35


def load_env(env_path: Path):
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip()
        os.environ.setdefault(k, v)


def get_api_config(name: str):
    load_env(HERE.parent.parent / ".env")
    prefix = "MINIMAX" if name == "minimax" else "GLM"
    url = os.environ[f"{prefix}_API_URL"]
    key = os.environ[f"{prefix}_API_KEY"]
    model = os.environ[f"{prefix}_MODEL"]
    return url, key, model


# ───────── 口语化 prompt(核心差异) ─────────
ORAL_SYSTEM = (
    "你是一名擅长把产品需求翻译成\"普通用户在手机上快速敲字\"风格的数据构造专家。"
    "产出的 query 必须严格符合手机输入习惯:口语、简短、无任何特殊符号。"
)


def build_oral_user_message(scenario, batch_cfgs):
    """口语化 prompt(无种子,纯靠 prompt 引导 + 覆盖配置)。"""
    cfg_block = "\n".join(
        f"第{i+1}条: {brief_for(cfg)}"
        for i, cfg in enumerate(batch_cfgs)
    )
    return f"""你在手机键盘上快速打字,需要让一个 AI 帮你生成一张 A2UI 服务卡片。
围绕【{scenario['name']}】场景(像:{scenario['desc']})生成 {len(batch_cfgs)} 条完全不同的用户需求。

每条需求必须像普通人在微信/手机键盘上随手敲出来,口述式:

【硬性规则】
- 长度 8-35 个字为主,极偶尔可短到 5 字或长到 50 字
- 像跟朋友说话:可以用「帮我弄个」「搞个」「整个」「给我做个」「能给我整一个吗」
- 语气词可用:啊 / 嘛 / 呢 / 吧 / 哈 / 嗯
- 填充词可用:那个 / 就是 / 然后 / 反正
- 俚语可用但别多(< 10%):yyds / 绝绝子 / 摆烂 / 卷 / 破防 / 上头 / 拿捏
- 可带具体数字:电量 20%、32 天、200 米、8 公里、3 公里
- 允许的标点只有这些:.。?？!！,，(其它全部禁止)
- 严禁出现:括号(中英)、引号(中英)、破折号、省略号、分号、冒号、
  emoji、Markdown 符号(`*_#~`)、竖线、反斜杠、斜杠、等号、加号、at 符号
- 严禁出现:渐变、圆环、环形、圆角、Stack、padding、组件、布局、token、字段
- 不要任何技术术语,不要任何代码块
- 一条 query 一行,格式「序号. 内容」(序号从 1 到 {len(batch_cfgs)})
- 不要空行、不要解释、不要标题
- 严格遵循下方每条的差异化要求,不要雷同

【本批差异化要求】
{cfg_block}

请直接输出 {len(batch_cfgs)} 条 query:"""


def brief_for(cfg):
    """口语化版 brief(去掉抽象词,改用动作描述)。"""
    parts = []
    ax = cfg
    # 组件
    if ax.get("component") == "Progress":
        parts.append("要看到数据比例")
    elif ax.get("component") == "Button":
        parts.append("有一个按钮让我点")
    elif ax.get("component") == "List":
        parts.append("列一串同类的东西")
    elif ax.get("component") == "Stack":
        parts.append("文字叠在背景图上那种")
    elif ax.get("component") == "Checkbox":
        parts.append("有几项可以打勾选")
    elif ax.get("component") == "Image":
        parts.append("主体是个图")
    # 绑定
    if ax.get("binding") == "formatString":
        parts.append("显示一行带数字的话")
    elif ax.get("binding") == "expression":
        parts.append("有个数字会变")
    # 点击
    c = ax.get("click", "none")
    if c == "clickToCallPhone":
        parts.append("点一下能打电话")
    elif c == "intent_navigate":
        parts.append("点一下能导航去某地")
    elif c and c.startswith("deeplink_"):
        parts.append("点一下能跳到应用里")
    elif c and c.startswith("intent_"):
        parts.append("点一下能进入系统某个操作")
    # 数据
    if ax.get("data") == "calendar":
        parts.append("能从日历读日程")
    elif ax.get("data") == "weather":
        parts.append("能读天气")
    # 状态
    if ax.get("status") == "warning":
        parts.append("看到提醒说我快不行了")
    elif ax.get("status") == "alert":
        parts.append("看到红色那种危险提示")
    elif ax.get("status") == "confirm":
        parts.append("看到已经完成/已连接")
    return "、".join(parts) or "自由发挥"


# ───────── 通用 API 调用(复制自 gen_cases)─────────
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
    return out[:expected]


# ───────── 覆盖配置采样(同 gen_cases)─────────
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


# ───────── 校验:符号 + 长度 ─────────
def validate(q):
    """返回 (ok, reason)。"""
    if not q or len(q) < LEN_MIN:
        return False, f"len<{LEN_MIN}"
    if len(q) > LEN_MAX:
        return False, f"len>{LEN_MAX}"
    if not ALLOWED_RE.match(q):
        return False, "forbidden char"
    return True, "ok"


def main():
    global API_URL, API_KEY, API_MODEL, CURRENT_API
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--api", choices=["minimax", "glm"], default="minimax")
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    API_URL, API_KEY, API_MODEL = get_api_config(args.api)
    CURRENT_API = args.api
    print(f"[{args.scenario}] 使用 API: {args.api} ({API_MODEL})", flush=True)

    scenario = scenario_by_id(args.scenario)
    count = args.count or scenario["quota"]
    over = int(count * 1.5)
    out_dir = HERE / "scenarios" / scenario["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "cases.jsonl"

    existing = 0
    if out_file.is_file():
        with out_file.open("r", encoding="utf-8") as fin:
            existing = sum(1 for _ in fin if _.strip())
        if existing >= over:
            print(f"[{scenario['id']}] 已存在 {existing} 条 >= 目标 {over},跳过。",
                  flush=True)
            return
        print(f"[{scenario['id']}] 已存在 {existing} 条,继续追加到 {over}",
              flush=True)

    produced = existing
    rejected = 0
    batch_no = 0
    max_retries_per_batch = 4  # 单批最多 4 轮补采
    with out_file.open("a", encoding="utf-8") as fout:
        while produced < over:
            need = min(args.batch, over - produced)
            accepted_this_round = 0
            for retry in range(max_retries_per_batch):
                if accepted_this_round >= need:
                    break
                n = need - accepted_this_round
                batch_cfgs = [sample_config(scenario) for _ in range(n)]
                user_msg = build_oral_user_message(scenario, batch_cfgs)
                batch_no += 1
                try:
                    content = call_api(ORAL_SYSTEM, user_msg,
                                       timeout=args.timeout)
                except Exception as e:  # noqa: BLE001
                    print(f"[{scenario['id']}] batch {batch_no} 失败: {e}",
                          file=sys.stderr)
                    time.sleep(1)
                    continue
                queries = parse_queries(content, n)
                for i, q in enumerate(queries):
                    ok, reason = validate(q)
                    if not ok:
                        rejected += 1
                        if rejected <= 30:
                            print(f"  [reject] {reason}: {q[:40]}",
                                  file=sys.stderr)
                        continue
                    rec = {
                        "scenario": scenario["id"],
                        "scenario_name": scenario["name"],
                        "query": q,
                        "axes": batch_cfgs[i] if i < len(batch_cfgs) else batch_cfgs[-1],
                    }
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    produced += 1
                    accepted_this_round += 1
                print(f"[{scenario['id']}] batch {batch_no}: "
                      f"+{accepted_this_round} (累计 {produced}/{over}, 拒 {rejected})",
                      flush=True)
                time.sleep(0.3)
            if accepted_this_round == 0:
                # 4 轮都没产出任何合格 query,放弃
                print(f"[{scenario['id']}] 连续失败,停止补采,共 {produced}",
                      file=sys.stderr)
                break

    print(f"[{scenario['id']}] 完成,共 {produced} 条, 拒绝 {rejected} 条 -> {out_file}")


if __name__ == "__main__":
    raise SystemExit(main())
