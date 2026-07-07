#!/usr/bin/env python3
"""为每个数据集 case 目录生成 VLM 评分请求体 (score.request.json)，
默认并并发调用 MiniMax chat/completions 评分 API（凭据从 .env 读取）。

评分维度（加权总分 0-10）：
  - 指令遵从 InstructionAdherence   权重 0.4
  - 样式美观 Aesthetic               权重 0.2
  - 排版布局 Layout（堆叠/文字截断） 权重 0.4

请求体顶层为 {"messages":[system, user(多模态)], "response_format": json_object}。
不写 model/temperature 等模型参数，调用 API 时由脚本注入 .env 中的 MINIMAX_MODEL。

示例：
  # 默认：生成请求体 + 调用 API 评分 + 提取改进 DSL 到 -vN 目录
  python scripts/build_score_requests.py -d datasets/cases-600-mix
  python scripts/build_score_requests.py -d datasets/cases-600-mix -c Case-007-01-low-power-007
  python scripts/build_score_requests.py -d datasets/cases-600-mix -n 5 -j 5

  # 只生成请求体，不调用 API
  python scripts/build_score_requests.py -d datasets/cases-600-mix --disable-call-api

  # 全量评分，并发 10，覆盖已有结果
  python scripts/build_score_requests.py -d datasets/cases-600-mix -j 10 --overwrite

  # 调试单个 case（单线程，便于看清日志）
  python scripts/build_score_requests.py -d datasets/cases-600-mix -c Case-007-01-low-power-007 -j 1
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

log = logging.getLogger("score")

# --------------------------------------------------------------------------- #
# 文件名约定（每个 case 目录）
# --------------------------------------------------------------------------- #
QUERY_NAME = "query.txt"
TASKSPEC_NAME = "task.taskSpec.json"
DSL_NAME = "card.dsl.jsonl"
PNG_NAME = "card.dsl.png"
OUTPUT_NAME = "score.request.json"
SCORE_RESULT_NAME = "score.result.json"
CARDSPEC_NAME = "card.cardspec.json"

CASE_REQUIRED_FILES = (QUERY_NAME, TASKSPEC_NAME, DSL_NAME, PNG_NAME)

# 改进版 case 目录需要从原 case 复制过来的伴随文件
VERSION_COPY_FILES = (CARDSPEC_NAME, QUERY_NAME, TASKSPEC_NAME)

# --------------------------------------------------------------------------- #
# 评分 system prompt
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """你是 HarmonyOS A2UI Form 服务卡片的资深评审专家。你将收到一个 case 的：用户原始指令、TaskSpec 契约、模型生成的 3 行 genui DSL（card.dsl.jsonl）、以及该 DSL 的实际渲染截图。你的任务是对该卡片进行三维加权打分（0-10）、给出中文打分理由，并产出一份改进后的 3 行 DSL。

你的评审依据是协议 .agents/skills/harmony-card-generation-datamodel-first 与 TaskSpec 协议。下文给出关键约束，必须严格据此判断。

=== 一、尺寸与 root shell（硬约束） ===
- size 只能是 2x2 或 2x4。
- 2x2：createSurface/root width:140、height:140，root borderRadius:18，clip:true，默认 padding:12，内容区约 116x116。
- 2x4：createSurface/root width:300、height:140，root borderRadius:22，clip:true，默认 padding:12，内容区约 276x116。
- createSurface.catalogId 必须是 "ohos.a2ui.extended.catalog"；每行 version 必须是 "v0.9"。
- updateDataModel.path 必须是 "/"，value 必须原样等于 TaskSpec.dataModel.value。

=== 二、组件与协议范围（硬约束） ===
- 只允许 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
- 用 Text.content / Image.src / Button.label；禁止 Text.text / Image.url / Button.action。
- 禁止 TextInput、Toggle、Radio、CheckboxGroup、Select、NavContainer、Tabs、TabContent、Web、Grid、If、theme、非 onClick 事件、网络图、SVG、emoji、占位图。
- components 是扁平组件数组；children 只能是组件 id 数组（模板循环才允许 {"componentId":"...","path":"/..."}）。

=== 三、数据绑定、事件、素材（硬约束） ===
- 展示值优先用完整表达式 {{ ... }} 读取 DataModel，路径必须能从 TaskSpec.dataModel.value 推导。
- onClick[].call 与 onClick[].args 必须原样来自 TaskSpec.eventCandidates，不得发明新事件或新参数。
- Image.src / backgroundImage 只能来自 TaskSpec.assetCandidates 或用户明确提供的本地/资源路径。

=== 四、布局预算公式（必须据此检测堆叠/溢出/文字截断） ===
对每个 Row/Column，按下式计算并比较：
  - Row 横向占用 = 父 padding.left + 父 padding.right + itemMargin * (子项数 - 1) + Σ(子项 width + 子项 margin.left + 子项 margin.right)
  - Column 纵向占用 = 父 padding.top + 父 padding.bottom + itemMargin * (子项数 - 1) + Σ(子项 height + 子项 margin.top + 子项 margin.bottom)
  - 当「占用 > 父容器 width/height」时判定为溢出（会导致子项被挤压、重叠、裁剪）。
  - 子项无 width/height 时按估算：文本宽度 ≈ Σ 字符宽度，中文 ≈ fontSize，英文/数字 ≈ 0.6*fontSize，空格/标点 ≈ 0.4*fontSize。
  - 受保护文本（标题、状态、CTA、主指标、用户明确要求字段）不得依赖 ellipsis/clip/marquee 隐藏；放不下应缩字、删弱信息或换尺寸。
  - Stack 叠层不得覆盖受保护文本/CTA/点击元素/进度主值；背景在底层，信息在上层。
  - Button/可点击视觉元素热区 ≥ 24vp，理想接近 40vp。
  - 底部动作区外框底边到卡片底边：2x2 通常 8-12vp、不得 >16vp；2x4 通常 10-14vp、不得 >16vp。
  - 字号阶梯：10/12/14/16/18/20/32/40；间距阶梯：4/8/12/16（微调 2/6/10/14）。同一卡片只保留一个最强字重。

=== 五、评分维度（每项 0-10，给分到小数点后 1 位） ===

D1 指令遵从（权重 0.4）：是否满足 userQuery 的明确诉求。
  - 信息是否齐全：用户明确点名要显示的字段/对象是否都体现了。
  - 事件是否落实：userQuery 要求的动作是否转换成 onClick，且 call/args 原样来自 eventCandidates。
  - 素材是否正确：assetCandidates 是否按语义正确使用（背景/图标/插图）。
  - 尺寸与协议：size/root shell/catalogId/version/updateDataModel 等硬约束是否满足。
  - 评分基准：10=全部精准落实且无多余；7-8=主要诉求满足、有轻微瑕疵；4-6=有遗漏或轻微违反协议；1-3=关键诉求缺失或协议违规；0=与指令几乎无关。

D2 样式美观（权重 0.2）：视觉质量。
  - 配色来源是否合法、和谐（渐变 stop/颜色 token），前景文字在背景上是否清晰可读。
  - 字号/字重/间距是否在阶梯上，层级是否清晰，是否只有一个最强字重。
  - 留白与密度是否合理（无明显空洞、无过密），对齐是否统一。
  - 评分基准：10=优秀、克制、专业；7-8=良好；4-6=可用但有明显土气或不统一；1-3=丑陋或不可读；0=无法入目。

D3 排版布局（权重 0.4）：堆叠、溢出、文字截断（核心排查项）。
  - 用上面公式逐一核算每个 Row/Column 是否溢出；任一溢出即扣重分。
  - 检查 Stack 层叠是否遮盖关键文本/CTA/进度值。
  - 检查受保护文本是否会被截断（结合渲染截图佐证）。
  - 检查按钮热区、底部锚定、左右边界共享。
  - 评分基准：10=全部预算成立、无任何堆叠/截断；7-8=基本成立、个别小瑕疵；4-6=存在溢出或局部截断；1-3=多处堆叠/文字被裁/CTA 不可用；0=布局崩溃。

加权总分 = D1*0.4 + D2*0.2 + D3*0.4（保留 1 位小数）。

=== 六、输出格式（严格 JSON，禁止任何解释性前后缀） ===
只输出一个 JSON 对象，schema 如下（所有 reason/issue 字段用中文）：
{
  "case_id": "字符串，原样回填",
  "scores": {
    "instruction": {"score": 0-10 数字, "weight": 0.4},
    "aesthetic":   {"score": 0-10 数字, "weight": 0.2},
    "layout":      {"score": 0-10 数字, "weight": 0.4}
  },
  "weighted_total": 0-10 数字,
  "reasons": {
    "instruction": "中文，具体说明指令落实情况与扣分点",
    "aesthetic": "中文，具体说明美观问题与扣分点",
    "layout": "中文，必须引用预算计算结果，例如 'content Column 子项占高 126 > 可用 116，溢出 10'"
  },
  "issues": ["中文具体问题清单，逐条列出"],
  "improved_dsl": [
    "第1行 JSON 字符串：createSurface",
    "第2行 JSON 字符串：updateComponents",
    "第3行 JSON 字符串：updateDataModel"
  ]
}
要求：
- improved_dsl 必须恰好 3 个字符串元素，每个是合法 JSON 行，整体是合法 JSONL；不得包含 markdown 代码块标记。
- 若原 DSL 已无问题，improved_dsl 可以与原 DSL 相同，但不得低于原水平。
- 不要输出 JSON 以外的任何内容。"""


# --------------------------------------------------------------------------- #
# 读取各文件
# --------------------------------------------------------------------------- #
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _read_taskspec_pretty(path: Path) -> str:
    """读取 task.taskSpec.json 并以 2 空格缩进美化输出，保证模型可读。"""
    obj = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _read_dsl_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s:
            lines.append(s)
    return lines


def _encode_image(path: Path) -> str:
    raw = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


# --------------------------------------------------------------------------- #
# 构造请求
# --------------------------------------------------------------------------- #
def build_user_text(case_id: str, query: str, taskspec_pretty: str, dsl_lines: list[str]) -> str:
    dsl_block = "\n".join(dsl_lines) if dsl_lines else "(无)"
    return (
        f"请对以下 case 进行三维加权评分。\n\n"
        f"=== case_id ===\n{case_id}\n\n"
        f"=== 用户原始指令 (query.txt) ===\n{query}\n\n"
        f"=== TaskSpec 契约 (task.taskSpec.json) ===\n{taskspec_pretty}\n\n"
        f"=== 待评审 DSL (card.dsl.jsonl，共 {len(dsl_lines)} 行) ===\n{dsl_block}\n\n"
        f"=== 渲染截图 ===\n请结合随附的 card.dsl.png 渲染截图，并按 system 中给出的布局预算公式"
        f"对每个 Row/Column 做数值核算，综合视觉与数值给出分数。\n\n"
        f"输出要求：严格按 system 中规定的 JSON schema 输出单个 JSON 对象，"
        f"reasons.layout 必须引用具体预算计算结果，improved_dsl 为 3 行合法 JSONL。"
    )


def build_request(case_id: str, query: str, taskspec_pretty: str,
                  dsl_lines: list[str], image_data_url: str | None) -> dict:
    user_text = build_user_text(case_id, query, taskspec_pretty, dsl_lines)

    if image_data_url:
        user_content: list[dict] = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
    else:
        user_content = user_text

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def find_case_dirs(dataset: Path) -> list[Path]:
    return sorted(
        d for d in dataset.iterdir()
        if d.is_dir() and all((d / f).is_file() for f in CASE_REQUIRED_FILES)
    )


def process_case(case_dir: Path, output_name: str, no_image: bool, overwrite: bool) -> str:
    out_path = case_dir / output_name
    if out_path.exists() and not overwrite:
        return "skip_exists"

    try:
        query = _read_text(case_dir / QUERY_NAME)
        taskspec_pretty = _read_taskspec_pretty(case_dir / TASKSPEC_NAME)
        dsl_lines = _read_dsl_lines(case_dir / DSL_NAME)
    except Exception as e:  # noqa: BLE001
        return f"skip_read_error:{e!r}"

    image_data_url: str | None = None
    if not no_image:
        try:
            image_data_url = _encode_image(case_dir / PNG_NAME)
        except Exception as e:  # noqa: BLE001
            return f"skip_image_error:{e!r}"

    request = build_request(
        case_id=case_dir.name,
        query=query,
        taskspec_pretty=taskspec_pretty,
        dsl_lines=dsl_lines,
        image_data_url=image_data_url,
    )

    out_path.write_text(
        json.dumps(request, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return "ok"


# --------------------------------------------------------------------------- #
# .env 与 MiniMax API 配置
# --------------------------------------------------------------------------- #
def _parse_env(path: Path) -> dict:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def load_minimax_config(env_path: Path | None = None) -> dict:
    """从仓库根目录 .env 读取 MiniMax 凭据（已存在的系统环境变量优先）。"""
    resolved = env_path or (Path(__file__).resolve().parents[1] / ".env")
    env = _parse_env(resolved)
    url = os.environ.get("MINIMAX_API_URL") or env.get("MINIMAX_API_URL")
    key = os.environ.get("MINIMAX_API_KEY") or env.get("MINIMAX_API_KEY")
    model = (os.environ.get("MINIMAX_MODEL") or env.get("MINIMAX_MODEL")
             or "MiniMax-M3")
    if not url or not key:
        raise RuntimeError(
            "未配置 MINIMAX_API_URL / MINIMAX_API_KEY，请检查 .env"
        )
    return {"url": url, "key": key, "model": model}


# --------------------------------------------------------------------------- #
# 响应解析（剥离 <think>...、代码块围栏、抽取首个 JSON 对象）
# --------------------------------------------------------------------------- #
def strip_think_and_parse_json(content: str) -> dict:
    if not isinstance(content, str):
        content = str(content)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r"<think>.*", "", content, flags=re.DOTALL)
    content = re.sub(r"```(?:json)?", "", content)
    content = content.strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("响应中未找到可解析的 JSON 对象")
    return json.loads(content[start : end + 1])


# --------------------------------------------------------------------------- #
# 调用 MiniMax chat/completions
# --------------------------------------------------------------------------- #
def call_minimax(cfg: dict, body: dict, timeout: int, retries: int):
    """流式调用 MiniMax chat/completions，返回 (content, elapsed_sec)。

    M3 是推理模型，非流式请求会在生成完成前整体挂起、极易触发读超时；
    改用 stream=True 逐块读取，块间持续保活，timeout 视为「块间最大间隔」。
    """
    if requests is None:
        raise RuntimeError("缺少 requests 库，请 pip install requests")
    payload = dict(body)
    payload["model"] = cfg["model"]
    payload["stream"] = True
    headers = {
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
    }
    last_err: str | None = None
    for attempt in range(retries):
        t0 = time.time()
        chunks: list[str] = []
        try:
            resp = requests.post(
                cfg["url"], json=payload, headers=headers,
                timeout=(15, timeout), stream=True,
            )
        except Exception as e:  # noqa: BLE001
            last_err = f"network(connect): {e!r}"
            log.warning(f"连接异常，{2 ** (attempt + 1)}s 后重试: {e!r}")
            time.sleep(2 ** (attempt + 1))
            continue
        # 可重试状态码
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            last_err = f"http {resp.status_code}: {resp.text[:200]}"
            log.warning(f"HTTP {resp.status_code}，{2 ** (attempt + 1)}s 后重试")
            time.sleep(2 ** (attempt + 1))
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"http {resp.status_code}: {resp.text[:300]}")
        # 逐块读取 SSE
        try:
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip() if isinstance(raw, str) else raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except Exception:  # noqa: BLE001
                    continue
                br = obj.get("base_resp") or {}
                if br.get("status_code", 0) != 0:
                    raise RuntimeError(f"stream base_resp: {br}")
                if "error" in obj:
                    raise RuntimeError(f"stream error: {str(obj['error'])[:300]}")
                ch = obj.get("choices") or []
                if not ch:
                    continue
                delta = ch[0].get("delta", {}) or {}
                c = delta.get("content") or ""
                if not c and delta.get("reasoning_content"):
                    c = delta["reasoning_content"]
                if c:
                    chunks.append(c)
        except requests.exceptions.ConnectionError as e:
            last_err = f"stream(conn): {e!r}"
            log.warning(f"流式中断，{2 ** (attempt + 1)}s 后重试 (已收 {len(chunks)} 块)")
            time.sleep(2 ** (attempt + 1))
            continue
        except requests.exceptions.ReadTimeout as e:
            last_err = f"stream(read-timeout): {e!r}"
            log.warning(f"流式块间超时 {timeout}s，重试 (已收 {len(chunks)} 块)")
            time.sleep(2 ** (attempt + 1))
            continue
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"流式读取异常: {e!r}")
        elapsed = time.time() - t0
        content = "".join(chunks).strip()
        if not content:
            last_err = "流式响应 content 为空"
            log.warning("流式响应为空，重试")
            time.sleep(2 ** (attempt + 1))
            continue
        return content, elapsed
    raise RuntimeError(f"API 调用失败（已重试 {retries} 次）: {last_err}")


# --------------------------------------------------------------------------- #
# improved_dsl 归一化 + 版本目录
# --------------------------------------------------------------------------- #
def _normalize_improved_dsl(improved) -> list[str]:
    """把 improved_dsl 归一化为 3 行合法 JSON 字符串；非法则抛异常。"""
    if isinstance(improved, str):
        lines = [l.strip() for l in improved.splitlines() if l.strip()]
    elif isinstance(improved, list):
        lines: list[str] = []
        for item in improved:
            if isinstance(item, str):
                sub = [l.strip() for l in item.splitlines() if l.strip()]
                lines.extend(sub if len(sub) > 1 else [item.strip()])
            else:
                lines.append(json.dumps(item, ensure_ascii=False))
    else:
        raise ValueError("improved_dsl 既非字符串也非数组")
    if len(lines) != 3:
        raise ValueError(f"improved_dsl 应为 3 行，实际 {len(lines)} 行")
    parsed = []
    for ln in lines:
        parsed.append(json.loads(ln))
    if "updateComponents" not in parsed[1]:
        raise ValueError("第 2 行缺少 updateComponents")
    return lines


def next_version_dir(case_dir: Path, dataset_root: Path) -> Path:
    """在数据集根目录下查找 {case_name}-vN 的最大版本号，返回 v(N+1) 目录。"""
    name = case_dir.name
    pattern = re.compile(rf"^{re.escape(name)}-v(\d+)$")
    max_v = 0
    for d in dataset_root.iterdir():
        if d.is_dir():
            m = pattern.match(d.name)
            if m:
                max_v = max(max_v, int(m.group(1)))
    return dataset_root / f"{name}-v{max_v + 1}"


def create_version_dir(case_dir: Path, dataset_root: Path,
                       result: dict) -> str:
    """把 improved_dsl 写入新版本目录并复制伴随文件；返回版本目录名。"""
    lines = _normalize_improved_dsl(result.get("improved_dsl"))
    target = next_version_dir(case_dir, dataset_root)
    target.mkdir(parents=True, exist_ok=False)
    (target / DSL_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    for fn in VERSION_COPY_FILES:
        src = case_dir / fn
        if src.is_file():
            shutil.copy2(src, target / fn)
    return target.name


# --------------------------------------------------------------------------- #
# 单 case 的 API 评分流水
# --------------------------------------------------------------------------- #
def process_case_call_api(case_dir: Path, dataset_root: Path, cfg: dict,
                          index: int, total: int, overwrite: bool,
                          retries: int, timeout: int) -> str:
    name = case_dir.name
    lp = f"[{index}/{total}]"
    score_path = case_dir / SCORE_RESULT_NAME
    if score_path.exists() and not overwrite:
        log.info(f"{lp} SKIP  {name} (score.result.json 已存在)")
        return "skip"
    body_path = case_dir / OUTPUT_NAME
    if not body_path.is_file():
        try:
            process_case(case_dir, OUTPUT_NAME, no_image=False, overwrite=True)
        except Exception as e:  # noqa: BLE001
            log.error(f"{lp} FAIL  {name} | 构建请求体失败: {e!r}")
            return "fail"
    body = json.loads(body_path.read_text(encoding="utf-8"))
    log.info(f"{lp} START {name}")
    try:
        content, elapsed = call_minimax(cfg, body, timeout, retries)
        result = strip_think_and_parse_json(content)
    except Exception as e:  # noqa: BLE001
        log.error(f"{lp} FAIL  {name} | {e}")
        return "fail"
    score_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    wt = result.get("weighted_total")
    wt_str = f"{wt}" if isinstance(wt, (int, float)) else "?"
    vtag = ""
    try:
        vtag = create_version_dir(case_dir, dataset_root, result)
    except Exception as e:  # noqa: BLE001
        log.warning(f"{lp} WARN  {name} | improved_dsl/版本目录失败: {e}")
    log.info(
        f"{lp} OK    {name} | {elapsed:.1f}s | total={wt_str} "
        f"| -> {vtag or '(无版本目录)'}"
    )
    return "ok"


def run_api_batch(case_dirs: list[Path], args: argparse.Namespace) -> int:
    cfg = load_minimax_config(args.env)
    log.info(
        f"API: {cfg['url']} | model={cfg['model']} "
        f"| concurrency={args.concurrency} | retries={args.retries} "
        f"| timeout={args.timeout}s"
    )
    log.info(f"待处理 case: {len(case_dirs)} 个")

    total = len(case_dirs)
    t0 = time.time()
    counters = {"ok": 0, "fail": 0, "skip": 0}

    def task(i: int, d: Path) -> str:
        try:
            return process_case_call_api(
                case_dir=d,
                dataset_root=args.dataset,
                cfg=cfg,
                index=i + 1,
                total=total,
                overwrite=args.overwrite,
                retries=args.retries,
                timeout=args.timeout,
            )
        except Exception as e:  # noqa: BLE001
            log.error(f"[{i + 1}/{total}] FAIL  {d.name} | 未捕获异常: {e!r}")
            return "fail"

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(task, i, d): d.name for i, d in enumerate(case_dirs)}
        for fut in as_completed(futs):
            st = fut.result()
            counters[st] = counters.get(st, 0) + 1

    elapsed = time.time() - t0
    log.info(
        f"汇总: 完成 {counters['ok']} | 失败 {counters['fail']} "
        f"| 跳过 {counters['skip']} | 用时 {elapsed:.1f}s"
    )
    return 0 if counters["fail"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="为每个 case 目录生成 VLM 评分请求体 score.request.json。"
    )
    parser.add_argument("-d", "--dataset", type=Path, default=Path("datasets/cases-600-mix"),
                        help="数据集根目录（其下每个子目录为一个 case）。")
    parser.add_argument("-c", "--case", type=str, default=None,
                        help="只处理名称匹配的 case（子串匹配）。")
    parser.add_argument("-n", "--limit", type=int, default=None,
                        help="最多处理的 case 数量（调试用）。")
    parser.add_argument("-o", "--output-name", type=str, default=OUTPUT_NAME,
                        help=f"请求体输出文件名，默认 {OUTPUT_NAME}。")
    parser.add_argument("--no-image", action="store_true",
                        help="不编码 PNG，生成纯文本请求体。")
    parser.add_argument("--overwrite", action="store_true",
                        help="覆盖已存在的输出/评分结果。")
    parser.add_argument("--disable-call-api", action="store_true",
                        help="只生成请求体，不调用 MiniMax 评分 API（默认会调用）。")
    parser.add_argument("-j", "--concurrency", type=int, default=5,
                        help="调用 API 时的并发 case 数，默认 5。")
    parser.add_argument("-r", "--retries", type=int, default=3,
                        help="单 case API 调用失败的重试次数，默认 3。")
    parser.add_argument("-t", "--timeout", type=int, default=300,
                        help="单次 API 请求超时秒数（流式模式下为块间最大"
                             "间隔），默认 300（5 分钟）。")
    parser.add_argument("-e", "--env", type=Path, default=None,
                        help=".env 文件路径，默认仓库根目录下的 .env。")
    parser.epilog = (
        "示例:\n"
        "  # 默认:生成请求体 + 调用 API 评分 + 提取改进 DSL 到 -vN 目录\n"
        "  python scripts/build_score_requests.py -d datasets/cases-600-mix\n"
        "  python scripts/build_score_requests.py -d datasets/cases-600-mix "
        "-c Case-007-01-low-power-007\n"
        "  python scripts/build_score_requests.py -d datasets/cases-600-mix "
        "-n 5 -j 5\n\n"
        "  # 只生成请求体,不调用 API\n"
        "  python scripts/build_score_requests.py -d datasets/cases-600-mix "
        "--disable-call-api\n\n"
        "  # 全量评分,并发 10,覆盖已有结果\n"
        "  python scripts/build_score_requests.py -d datasets/cases-600-mix "
        "-j 10 --overwrite\n\n"
        "  # 调试单 case(单线程)\n"
        "  python scripts/build_score_requests.py -d datasets/cases-600-mix "
        "-c Case-007-01-low-power-007 -j 1"
    )
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    args = parser.parse_args()

    call_api = not args.disable_call_api
    if call_api:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    if not args.dataset.is_dir():
        print(f"error: 数据集目录不存在: {args.dataset}", file=sys.stderr)
        return 1

    case_dirs = find_case_dirs(args.dataset)
    if args.case:
        case_dirs = [d for d in case_dirs if args.case in d.name]
    if args.limit is not None:
        case_dirs = case_dirs[: args.limit]

    if not case_dirs:
        print("未找到任何符合条件的 case 目录。", file=sys.stderr)
        return 1

    if call_api:
        return run_api_batch(case_dirs, args)

    ok = 0
    skipped = 0
    errors = 0
    for d in case_dirs:
        status = process_case(
            case_dir=d,
            output_name=args.output_name,
            no_image=args.no_image,
            overwrite=args.overwrite,
        )
        if status == "ok":
            ok += 1
            print(f"  [ok]   {d.name}")
        elif status == "skip_exists":
            skipped += 1
            print(f"  [skip] {d.name} (已存在，--overwrite 覆盖)")
        else:
            errors += 1
            print(f"  [err]  {d.name} -> {status}", file=sys.stderr)

    total = len(case_dirs)
    print(f"\n汇总：处理 {total} 个 | 成功 {ok} | 跳过 {skipped} | 错误 {errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
