#!/usr/bin/env python3
"""为每个数据集 case 调用 chat/completions API 生成 genui DSL。

读取每个 case 目录下的 task.request.json（仅含 {"messages":[...]}），
注入 .env 中的模型参数，流式调用 chat/completions，从响应中提取
```genui``` 代码块（3 行 JSONL），保存为 card.{model}.dsl.jsonl。

示例：
  # 默认：全量调用 MiniMax API 生成 DSL
  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5

  # 只处理单个 case（调试用）
  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5 \\
      -c Case-01-low-power-001 -j 1

  # 切换 GLM 提供商
  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5 \\
      --model-api GLM

  # 全量并发 10，覆盖已有结果
  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5 \\
      -j 10 --overwrite
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

log = logging.getLogger("build_dsl")

# --------------------------------------------------------------------------- #
# 文件名约定（每个 case 目录）
# --------------------------------------------------------------------------- #
TASK_REQUEST_NAME = "task.request.json"

# 默认提供商（.env 中的前缀）
DEFAULT_MODEL_API = "MINIMAX"

# --------------------------------------------------------------------------- #
# .env 与 API 配置
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


def load_api_config(model_api: str, env_path: Path | None = None) -> dict:
    """从仓库根目录 .env 读取指定提供商的凭据（系统环境变量优先）。"""
    resolved = env_path or (Path(__file__).resolve().parents[1] / ".env")
    env = _parse_env(resolved)
    prefix = model_api.upper()
    url = os.environ.get(f"{prefix}_API_URL") or env.get(f"{prefix}_API_URL")
    key = os.environ.get(f"{prefix}_API_KEY") or env.get(f"{prefix}_API_KEY")
    model = (os.environ.get(f"{prefix}_MODEL")
             or env.get(f"{prefix}_MODEL")
             or f"{model_api}-M3")
    if not url or not key:
        raise RuntimeError(
            f"未配置 {prefix}_API_URL / {prefix}_API_KEY，请检查 .env"
        )
    return {"url": url, "key": key, "model": model, "provider": model_api}


# --------------------------------------------------------------------------- #
# 流式调用 chat/completions（复用 build_score.py 逻辑）
# --------------------------------------------------------------------------- #
def call_chat_completions(cfg: dict, body: dict, timeout: int,
                          retries: int) -> tuple[str, float]:
    """流式调用 chat/completions，返回 (content, elapsed_sec)。

    推理模型（如 M3）非流式请求会在生成完成前整体挂起、极易触发读超时；
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
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            last_err = f"http {resp.status_code}: {resp.text[:200]}"
            log.warning(f"HTTP {resp.status_code}，{2 ** (attempt + 1)}s 后重试")
            time.sleep(2 ** (attempt + 1))
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"http {resp.status_code}: {resp.text[:300]}")
        try:
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = (raw.strip() if isinstance(raw, str)
                        else raw.decode("utf-8", "ignore").strip())
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
                    raise RuntimeError(
                        f"stream error: {str(obj['error'])[:300]}"
                    )
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
            log.warning(
                f"流式中断，{2 ** (attempt + 1)}s 后重试 (已收 {len(chunks)} 块)"
            )
            time.sleep(2 ** (attempt + 1))
            continue
        except requests.exceptions.ReadTimeout as e:
            last_err = f"stream(read-timeout): {e!r}"
            log.warning(
                f"流式块间超时 {timeout}s，重试 (已收 {len(chunks)} 块)"
            )
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
# 响应解析：提取 genui DSL（3 行 JSONL）
# --------------------------------------------------------------------------- #
GENUI_FENCE_RE = re.compile(
    r"```genui\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE
)
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
THINK_UNCLOSED_RE = re.compile(r"<think>.*", re.DOTALL)

EXPECTED_KEYS = ["createSurface", "updateComponents", "updateDataModel"]


def extract_genui_dsl(content: str) -> list[str]:
    """从模型响应中提取 genui DSL，返回 3 行 JSON 字符串。

    解析顺序：
    1. 去除 <think>...</think> 块
    2. 优先匹配 ```genui ... ``` 围栏
    3. 回退：尝试匹配任意 ``` ... ``` 围栏
    4. 最终回退：将全文非空行视为 JSONL
    5. 校验：恰好 3 行、每行合法 JSON、version=v0.9、顺序正确
    """
    text = content
    text = THINK_RE.sub("", text)
    text = THINK_UNCLOSED_RE.sub("", text)

    # 优先 genui 围栏
    match = GENUI_FENCE_RE.search(text)
    if match:
        text = match.group(1)
    else:
        # 回退：任意围栏
        generic = re.search(r"```\w*\s*\n(.*?)\n```", text, re.DOTALL)
        if generic:
            text = generic.group(1)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) != 3:
        raise ValueError(
            f"genui DSL 应为 3 行，实际 {len(lines)} 行"
        )

    parsed: list[dict] = []
    for i, ln in enumerate(lines, 1):
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError as e:
            raise ValueError(f"第 {i} 行不是合法 JSON: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError(f"第 {i} 行不是 JSON 对象")
        if obj.get("version") != "v0.9":
            raise ValueError(
                f"第 {i} 行 version 应为 v0.9，实际 {obj.get('version')!r}"
            )
        parsed.append(obj)

    for i, (obj, key) in enumerate(zip(parsed, EXPECTED_KEYS), 1):
        if key not in obj:
            raise ValueError(f"第 {i} 行缺少 {key}")

    return lines


# --------------------------------------------------------------------------- #
# Case 发现
# --------------------------------------------------------------------------- #
def find_case_dirs(dataset: Path) -> list[Path]:
    """列出数据集下含 task.request.json 的 case 目录。"""
    return sorted(
        d for d in dataset.iterdir()
        if d.is_dir() and (d / TASK_REQUEST_NAME).is_file()
    )


# --------------------------------------------------------------------------- #
# 单 case 处理（带重试）
# --------------------------------------------------------------------------- #
def _classify_err(e: Exception) -> str:
    msg = str(e)
    if "网络" in msg or "network" in msg.lower() or "http " in msg.lower():
        return "网络"
    if "genui" in msg or "3 行" in msg or "JSON" in msg or "version" in msg:
        return "DSL解析"
    return "其它"


def process_case(case_dir: Path, cfg: dict, output_name: str,
                 index: int, total: int, overwrite: bool,
                 retries: int, timeout: int) -> str:
    name = case_dir.name
    lp = f"[{index}/{total}]"
    out_path = case_dir / output_name
    if out_path.exists() and not overwrite:
        log.info(f"{lp} SKIP  {name} ({output_name} 已存在)")
        return "skip"

    body_path = case_dir / TASK_REQUEST_NAME
    if not body_path.is_file():
        log.error(f"{lp} FAIL  {name} | 缺少 {TASK_REQUEST_NAME}")
        return "fail"

    try:
        body = json.loads(body_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.error(f"{lp} FAIL  {name} | 读取请求体失败: {e!r}")
        return "fail"

    if "messages" not in body:
        log.error(f"{lp} FAIL  {name} | 请求体缺少 messages 字段")
        return "fail"

    # 过滤掉 assistant 消息（task.request.json 中可能含旧 DSL 的 assistant
    # 回复），只保留 system + user，让模型从零生成新 DSL
    body["messages"] = [
        m for m in body["messages"] if m.get("role") != "assistant"
    ]

    log.info(f"{lp} START {name}")

    dsl_lines: list[str] | None = None
    elapsed = 0.0
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            content, elapsed = call_chat_completions(
                cfg, body, timeout, retries=1
            )
            dsl_lines = extract_genui_dsl(content)
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            kind = _classify_err(e)
            if attempt < retries:
                backoff = 2 ** attempt
                log.info(
                    f"{lp} RETRY {name} | {attempt}/{retries}次({kind}): "
                    f"{e} | {backoff}s后重试"
                )
                time.sleep(backoff)
            else:
                log.warning(
                    f"{lp} RETRY {name} | {attempt}/{retries}次({kind})"
                    f" 已用尽: {e}"
                )

    if dsl_lines is None:
        log.error(
            f"{lp} FAIL  {name} | 重试{retries}次仍失败: {last_err}"
        )
        return "fail"

    out_path.write_text(
        "\n".join(dsl_lines) + "\n", encoding="utf-8"
    )
    log.info(f"{lp} OK    {name} | {elapsed:.1f}s | -> {output_name}")
    return "ok"


# --------------------------------------------------------------------------- #
# 批处理
# --------------------------------------------------------------------------- #
def run_api_batch(case_dirs: list[Path], args: argparse.Namespace,
                  cfg: dict, output_name: str) -> int:
    log.info(
        f"API: {cfg['url']} | model={cfg['model']} "
        f"| provider={cfg['provider']} "
        f"| concurrency={args.concurrency} | retries={args.retries} "
        f"| timeout={args.timeout}s"
    )
    log.info(f"输出文件名: {output_name}")
    log.info(f"待处理 case: {len(case_dirs)} 个")

    total = len(case_dirs)
    t0 = time.time()
    counters = {"ok": 0, "fail": 0, "skip": 0}

    def task(i: int, d: Path) -> str:
        try:
            return process_case(
                case_dir=d,
                cfg=cfg,
                output_name=output_name,
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


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="调用 chat/completions API 为每个 case 生成 genui DSL，"
                    "保存为 card.{model}.dsl.jsonl。"
    )
    parser.add_argument("-d", "--dataset", type=Path,
                        default=Path("datasets/cases-600-mix"),
                        help="数据集根目录（其下每个子目录为一个 case）。")
    parser.add_argument("-c", "--case", type=str, default=None,
                        help="只处理名称匹配的 case（子串匹配）。")
    parser.add_argument("-n", "--limit", type=int, default=None,
                        help="最多处理的 case 数量（调试用）。")
    parser.add_argument("-j", "--concurrency", type=int, default=5,
                        help="调用 API 时的并发 case 数，默认 5。")
    parser.add_argument("-r", "--retries", type=int, default=3,
                        help="单 case 失败（网络/DSL解析）的总重试次数，"
                             "默认 3。")
    parser.add_argument("-t", "--timeout", type=int, default=300,
                        help="单次 API 请求超时秒数（流式模式下为块间"
                             "最大间隔），默认 300（5 分钟）。")
    parser.add_argument("-e", "--env", type=Path, default=None,
                        help=".env 文件路径，默认仓库根目录下的 .env。")
    parser.add_argument("--overwrite", action="store_true",
                        help="覆盖已存在的输出文件。")
    parser.add_argument("--model-api", type=str, default=DEFAULT_MODEL_API,
                        choices=["MINIMAX", "GLM", "DOUBAO"],
                        help=f"API 提供商前缀（对应 .env 中的 "
                             f"{DEFAULT_MODEL_API}_API_URL 等），"
                             f"默认 {DEFAULT_MODEL_API}。")
    parser.epilog = (
        "示例:\n"
        "  # 默认: 调用 MiniMax API 全量生成 DSL\n"
        "  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5\n\n"
        "  # 调试单个 case（单线程）\n"
        "  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5 "
        "-c Case-01-low-power-001 -j 1\n\n"
        "  # 切换 GLM 提供商\n"
        "  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5 "
        "--model-api GLM\n\n"
        "  # 全量并发 10，覆盖已有结果\n"
        "  python scripts/build_dsl.py -d datasets/case-600-newSkill-gpt5.5 "
        "-j 10 --overwrite\n"
    )
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not args.dataset.is_dir():
        print(f"error: 数据集目录不存在: {args.dataset}", file=sys.stderr)
        return 1

    try:
        cfg = load_api_config(args.model_api, args.env)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    output_name = f"card.{cfg['model']}.dsl.jsonl"

    case_dirs = find_case_dirs(args.dataset)
    if args.case:
        case_dirs = [d for d in case_dirs if args.case in d.name]
    if args.limit is not None:
        case_dirs = case_dirs[: args.limit]

    if not case_dirs:
        print("未找到任何符合条件的 case 目录。", file=sys.stderr)
        return 1

    return run_api_batch(case_dirs, args, cfg, output_name)


if __name__ == "__main__":
    raise SystemExit(main())
