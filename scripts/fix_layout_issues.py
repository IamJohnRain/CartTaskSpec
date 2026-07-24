#!/usr/bin/env python3
"""使用 MiniMax-M3 多模态复检并迭代修复 A2UI 卡片布局问题。"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


SOURCE_DSL_NAME = "card.dsl.jsonl"
SOURCE_PNG_NAME = "card.dsl.png"
FIX_DSL_NAME = "fix.card.dsl.jsonl"
FIX_PNG_NAME = "fix.card.dsl.png"
RESULT_NAME = "layout_issue.result.json"
SUMMARY_NAME = "fix_layout_issues.summary.json"
CONTEXT_FILES = (
    "query.txt",
    "task.taskSpec.json",
    "card.cardspec.json",
    "layout_issue.result.json",
)
EXPECTED_MESSAGES = (
    "createSurface",
    "updateComponents",
    "updateDataModel",
)
ISSUE_KEYS = (
    "text_occlusion",
    "layout_overflow",
    "icon_background_visibility",
)
FIX_ISSUE_KEYS = ISSUE_KEYS + ("spacing_aesthetic",)

log = logging.getLogger("layout-issue-fixer")

SYSTEM_PROMPT = """你是 HarmonyOS A2UI Form 服务卡片的资深修复专家。你会收到当前三行 genui DSL、实际渲染截图，以及可用的 query、TaskSpec、CardSpec 和上一轮反馈。

每一轮必须先基于截图检查，再决定是否修复。把以下四类视觉问题视为未解决：
1. text_occlusion：文字被文字、图标、图片、按钮或装饰元素明显重叠、覆盖，导致难以辨认。
2. layout_overflow：组件或内容超出卡片/容器边界、进入圆角裁切风险区、被边界明显裁切，或挤出应在的布局区域。文字虽然大体可见，但笔画已经贴边或出现少量裁切，也必须判为 true。
3. icon_background_visibility：图标因背景颜色、背景图片、对比度不足或视觉融合而难以识别。
4. spacing_aesthetic：空间分配、留白、对齐或视觉密度明显不合理。重点检查文字和图标是否远离卡片圆角与边缘安全区、左右内边距是否一致、行列是否对齐、组内距与组间距是否有层级、内容是否局部拥挤而其他区域空泛、主次信息是否平衡。元素没有真正越界，但贴边、压迫、基线混乱或比例失衡时也必须判为 true。

若任一问题存在，必须生成修复后的完整三行 DSL。修复必须遵守：
- 截图是视觉问题的最终依据，DSL 用于交叉确认层级和数值布局。
- 保留用户需求、DataModel、事件和素材语义，不虚构数据、事件或资源。
- 只使用 v0.9 Form 组件：Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
- catalogId 必须为 ohos.a2ui.extended.catalog；三行 surfaceId 一致；updateDataModel.path 为 "/"。
- 2x2 使用 140x140、root padding 12、borderRadius 18、clip true；2x4 使用 300x140、root padding 12、borderRadius 22、clip true。
- root 必须明确 width、height、padding、borderRadius、clip 和背景；内部关键组件使用可推导的数值宽高，不使用 matchParent。
- 动态值只使用完整 {{ ... }} 表达式，不使用 {"path":...} 或 formatString 作为组件值绑定。
- 受保护文字（标题、时间、日期、状态、CTA、主指标、价格和数量）必须完整显示，不能用 ellipsis、clip 或 marquee 掩盖问题。
- Row/Column 必须满足子项宽高、margin、padding 和 itemMargin 的总预算；Stack 不得遮挡文字、CTA 或主数值。
- 不要只满足“勉强放得下”。所有文字笔画、图标和按钮都应避开圆角裁切区，并保留清晰的边缘安全留白；2x2/2x4 的 root 默认 padding 12 是最低安全基线，内部背板仍需为文字保留合理 padding。
- 优先通过重新分配列宽、增加局部 padding、缩短弱文案、降低非主信息字号或删除弱装饰解决拥挤；不得用缩到难读、强行贴边或不均匀挤压来换取表面上的完整显示。
- 修复后要从截图整体复核视觉平衡：左中右区域不能一侧过密一侧空洞，同组文本起始线与数值结束线应整齐，主指标、状态和支撑信息要有稳定层级。
- 深色或复杂背景上的黑色/深色图标应增加不透明浅色底板、换用已声明且清晰的资源，或删除非必要图标。
- 改动应聚焦四类目标问题，不做无关的大规模重设计。

输出严格 JSON，不要输出 Markdown、思考过程或额外文字：
{
  "case_id": "原样返回",
  "issues": {
    "text_occlusion": {"detected": true或false, "confidence": 0到1, "evidence": "中文具体证据"},
    "layout_overflow": {"detected": true或false, "confidence": 0到1, "evidence": "中文具体证据"},
    "icon_background_visibility": {"detected": true或false, "confidence": 0到1, "evidence": "中文具体证据"},
    "spacing_aesthetic": {"detected": true或false, "confidence": 0到1, "evidence": "中文具体证据"}
  },
  "summary": "中文总结",
  "improved_dsl": null 或 [
    "第一行完整 JSON：createSurface",
    "第二行完整 JSON：updateComponents",
    "第三行完整 JSON：updateDataModel"
  ]
}

规则：四类问题全部为 false 时 improved_dsl 必须为 null；任一为 true 时 improved_dsl 必须是恰好三个合法 JSON 字符串组成的数组。即使文字仍可辨认，只要贴近卡片边缘、进入圆角风险区或整体空间明显失衡，也不能判定已经解决。
"""


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return parsed


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def load_minimax_config(env_path: Path | None) -> dict[str, str]:
    resolved_env = env_path or (Path(__file__).resolve().parents[1] / ".env")
    file_env = parse_env(resolved_env)

    def get_value(name: str, default: str | None = None) -> str | None:
        return os.environ.get(name) or file_env.get(name) or default

    api_url = get_value("MINIMAX_API_URL")
    api_key = get_value("MINIMAX_API_KEY")
    model = get_value("MINIMAX_MODEL", "MiniMax-M3")
    if not api_url or not api_key or not model:
        raise RuntimeError(
            "MiniMax 配置不完整，请设置 MINIMAX_API_URL、"
            "MINIMAX_API_KEY 和 MINIMAX_MODEL"
        )
    return {"url": api_url, "key": api_key, "model": model}


def encode_png(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def parse_json_response(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    cleaned = re.sub(r"```(?:json)?", "", cleaned).replace("```", "").strip()
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("响应中没有 JSON 对象")
    parsed, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    if not isinstance(parsed, dict):
        raise ValueError("响应 JSON 顶层必须是对象")
    return parsed


def extract_non_stream_content(response: Any) -> str:
    payload = response.json()
    base_resp = payload.get("base_resp") or {}
    if base_resp.get("status_code", 0) != 0:
        raise RuntimeError(f"MiniMax base_resp 错误: {base_resp}")
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("响应中缺少 choices")
    message = choices[0].get("message") or {}
    return message.get("content") or message.get("reasoning_content") or ""


def extract_stream_content(response: Any) -> str:
    content_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = (raw_line.strip() if isinstance(raw_line, str)
                else raw_line.decode("utf-8", "ignore").strip())
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        base_resp = event.get("base_resp") or {}
        if base_resp.get("status_code", 0) != 0:
            raise RuntimeError(f"MiniMax base_resp 错误: {base_resp}")
        if event.get("error"):
            raise RuntimeError(f"MiniMax 流式错误: {event['error']}")
        choices = event.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        if delta.get("content"):
            content_chunks.append(delta["content"])
        if delta.get("reasoning_content"):
            reasoning_chunks.append(delta["reasoning_content"])
    return "".join(content_chunks).strip() or "".join(reasoning_chunks).strip()


def call_minimax_once(
    config: dict[str, str], payload: dict[str, Any], timeout: int,
) -> str:
    if requests is None:
        raise RuntimeError("缺少 requests 依赖，请执行 pip install requests")
    headers = {
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json",
    }
    with requests.post(
        config["url"],
        json=payload,
        headers=headers,
        timeout=(15, timeout),
        stream=True,
    ) as response:
        if response.status_code == 429 or response.status_code >= 500:
            raise RuntimeError(
                f"可重试 HTTP {response.status_code}: {response.text[:300]}"
            )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
        content_type = response.headers.get("Content-Type", "").lower()
        content = (
            extract_stream_content(response)
            if "text/event-stream" in content_type
            else extract_non_stream_content(response)
        )
    if not content:
        raise RuntimeError("MiniMax 响应内容为空")
    return content


def normalize_result(raw: dict[str, Any], case_id: str) -> dict[str, Any]:
    raw_issues = raw.get("issues")
    if not isinstance(raw_issues, dict):
        raise ValueError("响应缺少 issues 对象")
    issues: dict[str, dict[str, Any]] = {}
    for issue_key in ISSUE_KEYS:
        issue = raw_issues.get(issue_key)
        if not isinstance(issue, dict):
            raise ValueError(f"响应缺少 issues.{issue_key}")
        detected = issue.get("detected")
        confidence = issue.get("confidence")
        evidence = issue.get("evidence")
        if not isinstance(detected, bool):
            raise ValueError(f"issues.{issue_key}.detected 必须是布尔值")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise ValueError(f"issues.{issue_key}.confidence 必须是数字")
        if not 0 <= float(confidence) <= 1:
            raise ValueError(f"issues.{issue_key}.confidence 必须在 0 到 1 之间")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(f"issues.{issue_key}.evidence 必须是非空字符串")
        issues[issue_key] = {
            "detected": detected,
            "confidence": round(float(confidence), 4),
            "evidence": evidence.strip(),
        }
    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary 必须是非空字符串")
    return {
        "case_id": case_id,
        "has_issue": any(item["detected"] for item in issues.values()),
        "issues": issues,
        "summary": summary.strip(),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "处理指定数据集目录中的布局问题 Case，通过 MiniMax-M3 检查并生成修复 DSL，"
            "使用 a2ui-render 渲染后持续复检，直到目标问题解决。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  python scripts/fix_layout_issues.py -i layout-issues/case-600-newSkill-gpt5.5-long
  python scripts/fix_layout_issues.py -i layout-issues/case-600-newSkill-gpt5.5-long -j 5 --max-iterations 6
  python scripts/fix_layout_issues.py -i layout-issues/case-600-newSkill-gpt5.5-long --start 1 --end 1 -j 1

存在问题且修复成功的 Case 最终新增 fix.card.dsl.jsonl 和
fix.card.dsl.png；首次检查正常的 Case 只写 layout_issue.result.json。

候选 DSL 和渲染图只存在于 Case 内的临时目录。只有 DSL 校验通过且
a2ui-render 成功生成图片后，才会成对替换正式 fix.* 文件。
""",
    )
    parser.add_argument(
        "-i", "--input", type=Path, default=Path("layout-issues"),
        help="输入数据集目录，递归发现其下的 Case；默认 layout-issues。",
    )
    parser.add_argument(
        "-j", "--concurrency", type=positive_int, default=10,
        help="并发处理 Case 数，默认 10。",
    )
    parser.add_argument(
        "--start", type=positive_int, default=None,
        help="从排序后的第几个 Case 开始（1-based，包含）。",
    )
    parser.add_argument(
        "--end", type=positive_int, default=None,
        help="处理到排序后的第几个 Case（1-based，包含）。",
    )
    parser.add_argument(
        "--max-iterations", type=positive_int, default=5,
        help="每个 Case 最多成功修复轮数，默认 5。",
    )
    parser.add_argument(
        "--proposal-attempts", type=positive_int, default=3,
        help="每轮候选 DSL 校验或渲染失败后的重新生成次数，默认 3。",
    )
    parser.add_argument(
        "-r", "--retries", type=positive_int, default=3,
        help="每次多模态 API 请求失败后的最大尝试次数，默认 3。",
    )
    parser.add_argument(
        "-t", "--timeout", type=positive_int, default=300,
        help="MiniMax 流式块间超时秒数，默认 300。",
    )
    parser.add_argument(
        "--render-timeout", type=positive_int, default=120,
        help="单次 a2ui-render 超时秒数，默认 120。",
    )
    parser.add_argument(
        "--renderer", type=Path, default=None,
        help="a2ui-render 可执行文件路径；默认从 PATH 自动发现。",
    )
    parser.add_argument(
        "-e", "--env", type=Path, default=None,
        help="MiniMax 环境配置文件；默认仓库根目录 .env。",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="把每次 API 调用的 request/response JSON 保存到对应 Case 目录。",
    )
    return parser.parse_args()


def find_case_dirs(input_dir: Path) -> list[Path]:
    case_dirs = {
        dsl_path.parent
        for dsl_path in input_dir.rglob(SOURCE_DSL_NAME)
        if (dsl_path.parent / SOURCE_PNG_NAME).is_file()
    }
    return sorted(
        case_dirs,
        key=lambda path: path.relative_to(input_dir).as_posix(),
    )


def resolve_renderer(explicit_path: Path | None) -> Path:
    if explicit_path is not None:
        resolved = explicit_path.expanduser().resolve()
        if not resolved.is_file():
            raise RuntimeError(f"渲染器不存在: {resolved}")
        return resolved
    command = shutil.which("a2ui-render.cmd") or shutil.which("a2ui-render")
    if not command:
        raise RuntimeError("PATH 中未找到 a2ui-render，请使用 --renderer 指定")
    return Path(command).resolve()


def read_context(case_dir: Path) -> str:
    sections: list[str] = []
    for filename in CONTEXT_FILES:
        path = case_dir / filename
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8").strip()
        except Exception as exc:  # noqa: BLE001
            log.warning("%s | 读取 %s 失败: %s", case_dir.name, filename, exc)
            continue
        if content:
            sections.append(f"=== {filename} ===\n{content}")
    return "\n\n".join(sections) or "（无额外契约文件）"


def result_payload(review: dict[str, Any], case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "has_issue": review["has_issue"],
        "issues": review["issues"],
        "summary": review["summary"],
    }


def write_layout_result(
    case_dir: Path, review: dict[str, Any], case_id: str,
) -> None:
    write_json(case_dir / RESULT_NAME, result_payload(review, case_id))


def has_clean_layout_result(case_dir: Path) -> bool:
    result_path = case_dir / RESULT_NAME
    if not result_path.is_file():
        return False
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("%s | 现有 %s 无法解析，将重新检查: %s",
                    case_dir.name, RESULT_NAME, exc)
        return False
    issues = result.get("issues")
    if not isinstance(issues, dict):
        return False
    for issue_key in FIX_ISSUE_KEYS:
        issue = issues.get(issue_key)
        if not isinstance(issue, dict) or issue.get("detected") is not False:
            return False
    return True


def build_request(
    case_id: str,
    dsl_path: Path,
    png_path: Path,
    context: str,
    model: str,
    iteration: int,
    feedback: str | None,
) -> dict[str, Any]:
    dsl = dsl_path.read_text(encoding="utf-8").strip()
    feedback_text = feedback or "（无；请直接检查当前截图与 DSL）"
    user_text = (
        f"case_id: {case_id}\n"
        f"当前修复轮次: {iteration}\n\n"
        f"=== 当前 card DSL ===\n{dsl}\n\n"
        f"{context}\n\n"
        f"=== 上一候选失败反馈 ===\n{feedback_text}\n\n"
        "请先检查随附的当前渲染截图。若仍存在任一目标问题，生成可以完整替换"
        "当前文件的三行 improved_dsl；若三类问题均已解决，返回 null。"
    )
    return {
        "model": model,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {
                    "url": encode_png(png_path)
                }},
            ]},
        ],
        "response_format": {"type": "json_object"},
    }


def normalize_dsl(value: Any) -> list[str]:
    if isinstance(value, str):
        lines = [line.strip() for line in value.splitlines() if line.strip()]
    elif isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, str):
                lines.append(item.strip())
            elif isinstance(item, dict):
                lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
            else:
                raise ValueError("improved_dsl 数组元素必须是 JSON 字符串或对象")
    else:
        raise ValueError("improved_dsl 必须是三行字符串数组")
    if len(lines) != 3 or any(not line for line in lines):
        raise ValueError("improved_dsl 必须恰好包含三行非空 JSON")

    parsed_lines: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"improved_dsl 第 {index + 1} 行 JSON 非法: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"improved_dsl 第 {index + 1} 行必须是 JSON 对象")
        if parsed.get("version") != "v0.9":
            raise ValueError(f"improved_dsl 第 {index + 1} 行 version 必须为 v0.9")
        message_key = EXPECTED_MESSAGES[index]
        if message_key not in parsed:
            raise ValueError(f"improved_dsl 第 {index + 1} 行必须包含 {message_key}")
        parsed_lines.append(parsed)

    create_surface = parsed_lines[0]["createSurface"]
    update_components = parsed_lines[1]["updateComponents"]
    update_data_model = parsed_lines[2]["updateDataModel"]
    if not all(isinstance(item, dict) for item in (
        create_surface, update_components, update_data_model
    )):
        raise ValueError("三条消息内容必须是 JSON 对象")
    if create_surface.get("catalogId") != "ohos.a2ui.extended.catalog":
        raise ValueError("createSurface.catalogId 非法")
    surface_ids = {
        create_surface.get("surfaceId"),
        update_components.get("surfaceId"),
        update_data_model.get("surfaceId"),
    }
    if None in surface_ids or len(surface_ids) != 1:
        raise ValueError("三行 DSL 的 surfaceId 必须一致且非空")
    if update_data_model.get("path") != "/":
        raise ValueError("updateDataModel.path 必须为 /")
    return [
        json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        for parsed in parsed_lines
    ]


def normalize_review(raw: dict[str, Any], case_id: str) -> dict[str, Any]:
    base = normalize_result(raw, case_id)
    raw_issues = raw.get("issues")
    spacing = raw_issues.get("spacing_aesthetic") if isinstance(raw_issues, dict) else None
    if not isinstance(spacing, dict):
        raise ValueError("响应缺少 issues.spacing_aesthetic")
    detected = spacing.get("detected")
    confidence = spacing.get("confidence")
    evidence = spacing.get("evidence")
    if not isinstance(detected, bool):
        raise ValueError("issues.spacing_aesthetic.detected 必须是布尔值")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("issues.spacing_aesthetic.confidence 必须是数字")
    if not 0 <= float(confidence) <= 1:
        raise ValueError("issues.spacing_aesthetic.confidence 必须在 0 到 1 之间")
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("issues.spacing_aesthetic.evidence 必须是非空字符串")
    base["issues"]["spacing_aesthetic"] = {
        "detected": detected,
        "confidence": round(float(confidence), 4),
        "evidence": evidence.strip(),
    }
    base["has_issue"] = any(
        base["issues"][key]["detected"] for key in FIX_ISSUE_KEYS
    )
    result = base
    improved = raw.get("improved_dsl")
    if result["has_issue"]:
        result["improved_dsl"] = normalize_dsl(improved)
    else:
        if improved not in (None, [], ""):
            raise ValueError("四类问题均未命中时 improved_dsl 必须为 null")
        result["improved_dsl"] = None
    return result


def request_review(
    case_id: str,
    dsl_path: Path,
    png_path: Path,
    context: str,
    config: dict[str, str],
    iteration: int,
    feedback: str | None,
    retries: int,
    timeout: int,
    debug_dir: Path | None,
    round_number: int,
    proposal_attempt: int,
) -> dict[str, Any]:
    payload = build_request(
        case_id, dsl_path, png_path, context, config["model"], iteration, feedback
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        content: str | None = None
        debug_stem: str | None = None
        if debug_dir is not None:
            debug_stem = f"fix.round{round_number}"
            if proposal_attempt != 1 or attempt != 1:
                debug_stem += f".proposal{proposal_attempt}.api{attempt}"
            write_json(debug_dir / f"{debug_stem}.request.json", payload)
        try:
            content = call_minimax_once(config, payload, timeout)
            parsed_response = parse_json_response(content)
            if debug_dir is not None and debug_stem is not None:
                write_json(
                    debug_dir / f"{debug_stem}.response.json",
                    parsed_response,
                )
            return normalize_review(parsed_response, case_id)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if debug_dir is not None and debug_stem is not None:
                debug_response = {"error": str(exc)}
                if content is not None:
                    debug_response["raw_content"] = content
                write_json(
                    debug_dir / f"{debug_stem}.response.json",
                    debug_response,
                )
            if attempt >= retries:
                break
            delay = 2 ** attempt
            log.warning(
                "%s | API 第 %d/%d 次失败: %s | %ds 后重试",
                case_id, attempt, retries, exc, delay,
            )
            time.sleep(delay)
    raise RuntimeError(f"多模态 API 请求失败，已尝试 {retries} 次: {last_error}")


def run_renderer(
    renderer: Path,
    dsl_path: Path,
    output_dir: Path,
    output_name: str,
    timeout: int,
) -> Path:
    command = [
        str(renderer),
        "-i", str(dsl_path),
        "-o", str(output_dir),
        "-n", output_name,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output_path = output_dir / output_name
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "无错误输出").strip()
        raise RuntimeError(
            f"a2ui-render 退出码 {completed.returncode}: {details[-2000:]}"
        )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        details = (completed.stderr or completed.stdout or "无输出").strip()
        raise RuntimeError(f"a2ui-render 未生成有效图片: {details[-2000:]}")
    return output_path


def promote_pair(
    case_dir: Path,
    candidate_dsl: Path,
    candidate_png: Path,
    backup_dir: Path,
) -> None:
    final_dsl = case_dir / FIX_DSL_NAME
    final_png = case_dir / FIX_PNG_NAME
    backup_dsl = backup_dir / FIX_DSL_NAME
    backup_png = backup_dir / FIX_PNG_NAME
    had_dsl = final_dsl.is_file()
    had_png = final_png.is_file()
    if had_dsl:
        os.replace(final_dsl, backup_dsl)
    if had_png:
        os.replace(final_png, backup_png)
    try:
        os.replace(candidate_dsl, final_dsl)
        os.replace(candidate_png, final_png)
    except Exception:
        final_dsl.unlink(missing_ok=True)
        final_png.unlink(missing_ok=True)
        if had_dsl and backup_dsl.is_file():
            os.replace(backup_dsl, final_dsl)
        if had_png and backup_png.is_file():
            os.replace(backup_png, final_png)
        raise


def render_and_promote(
    case_dir: Path,
    dsl_lines: list[str],
    renderer: Path,
    render_timeout: int,
) -> None:
    with tempfile.TemporaryDirectory(prefix=".fix_layout_", dir=case_dir) as temp_name:
        temp_dir = Path(temp_name)
        candidate_dsl = temp_dir / "candidate.card.dsl.jsonl"
        candidate_dsl.write_text("\n".join(dsl_lines) + "\n", encoding="utf-8")
        candidate_png = run_renderer(
            renderer, candidate_dsl, temp_dir, "candidate.card.dsl.png", render_timeout
        )
        promote_pair(case_dir, candidate_dsl, candidate_png, temp_dir)


def process_case(
    case_dir: Path,
    case_id: str,
    config: dict[str, str],
    renderer: Path,
    args: argparse.Namespace,
    index: int,
    total: int,
) -> dict[str, Any]:
    prefix = f"[{index}/{total}] {case_id}"
    started = time.time()
    source_dsl = case_dir / SOURCE_DSL_NAME
    source_png = case_dir / SOURCE_PNG_NAME
    current_dsl = source_dsl
    current_png = source_png
    context = read_context(case_dir)
    history: list[dict[str, Any]] = []
    successful_iterations = 0
    log.info("%s | 开始处理 | case_dir=%s", prefix, case_dir.resolve())
    if has_clean_layout_result(case_dir):
        elapsed = time.time() - started
        log.info("%s | 跳过 | %s 已存在且四项检查均为 false",
                 prefix, RESULT_NAME)
        return {
            "case_id": case_id,
            "status": "skipped_clean",
            "iterations": 0,
            "elapsed_seconds": round(elapsed, 3),
            "history": history,
        }

    for review_number in range(args.max_iterations + 1):
        feedback: str | None = None
        review: dict[str, Any] | None = None
        for proposal_attempt in range(1, args.proposal_attempts + 1):
            try:
                review = request_review(
                    case_id=case_id,
                    dsl_path=current_dsl,
                    png_path=current_png,
                    context=context,
                    config=config,
                    iteration=review_number,
                    feedback=feedback,
                    retries=args.retries,
                    timeout=args.timeout,
                    debug_dir=case_dir if args.debug else None,
                    round_number=review_number + 1,
                    proposal_attempt=proposal_attempt,
                )
            except Exception as exc:  # noqa: BLE001
                feedback = (
                    "上一轮 API 输出或 improved_dsl 格式无效，请严格按 schema 重新"
                    f"生成。错误：{exc}"
                )
                log.warning(
                    "%s | 第 %d 轮响应 %d/%d 无效: %s",
                    prefix, review_number + 1, proposal_attempt,
                    args.proposal_attempts, exc,
                )
                continue
            history.append({
                "review": review_number,
                "proposal_attempt": proposal_attempt,
                "has_issue": review["has_issue"],
                "issues": review["issues"],
                "summary": review["summary"],
            })
            matched = [key for key, item in review["issues"].items()
                       if item["detected"]]
            log.info(
                "%s | 第 %d/%d 次多模态反思 | 发现问题类别=%d | 问题=%s",
                prefix,
                review_number + 1,
                args.max_iterations + 1,
                len(matched),
                ",".join(matched) if matched else "无",
            )
            if not review["has_issue"]:
                write_layout_result(case_dir, review, case_id)
                elapsed = time.time() - started
                status = "clean" if successful_iterations == 0 else "solved"
                log.info("%s | %s | 修复轮数=%d | %.1fs",
                         prefix,
                         "首次检查正常，不生成 fix 文件"
                         if status == "clean" else "已解决",
                         successful_iterations, elapsed)
                return {
                    "case_id": case_id,
                    "status": status,
                    "iterations": successful_iterations,
                    "elapsed_seconds": round(elapsed, 3),
                    "final_issues": review["issues"],
                    "history": history,
                }

            if review_number >= args.max_iterations:
                write_layout_result(case_dir, review, case_id)
                elapsed = time.time() - started
                log.error("%s | 达到最大修复轮数，仍命中 %s",
                          prefix, ",".join(matched))
                return {
                    "case_id": case_id,
                    "status": "unresolved",
                    "iterations": successful_iterations,
                    "elapsed_seconds": round(elapsed, 3),
                    "final_issues": review["issues"],
                    "history": history,
                }

            try:
                render_and_promote(
                    case_dir,
                    review["improved_dsl"],
                    renderer,
                    args.render_timeout,
                )
                successful_iterations += 1
                current_dsl = case_dir / FIX_DSL_NAME
                current_png = case_dir / FIX_PNG_NAME
                log.warning(
                    "%s | 第 %d 轮候选渲染成功，复检中 | 命中=%s",
                    prefix, successful_iterations, ",".join(matched),
                )
                break
            except Exception as exc:  # noqa: BLE001
                feedback = (
                    "上一版 improved_dsl 未通过本地校验或渲染，请根据错误重新生成"
                    f"完整三行 DSL。错误：{exc}"
                )
                log.warning(
                    "%s | 第 %d 轮候选 %d/%d 失败: %s",
                    prefix, review_number + 1, proposal_attempt,
                    args.proposal_attempts, exc,
                )
        else:
            raise RuntimeError(
                f"第 {review_number + 1} 轮连续 {args.proposal_attempts} 个候选均渲染失败"
            )

    raise RuntimeError("迭代流程异常结束")


def run(args: argparse.Namespace) -> int:
    input_dir = args.input.resolve()
    if not input_dir.is_dir():
        log.error("输入目录不存在: %s", input_dir)
        return 2
    if args.start is not None and args.end is not None and args.start > args.end:
        log.error("--start 不能大于 --end: start=%d, end=%d", args.start, args.end)
        return 2
    try:
        config = load_minimax_config(args.env)
        renderer = resolve_renderer(args.renderer)
    except Exception as exc:  # noqa: BLE001
        log.error("初始化失败: %s", exc)
        return 2

    case_dirs = find_case_dirs(input_dir)
    start_index = (args.start or 1) - 1
    case_dirs = case_dirs[start_index:args.end]
    if not case_dirs:
        log.error("未找到包含 %s 和 %s 的 Case", SOURCE_DSL_NAME, SOURCE_PNG_NAME)
        return 2

    log.info(
        "开始迭代修复 | input=%s | cases=%d | model=%s | concurrency=%d | renderer=%s",
        input_dir, len(case_dirs), config["model"], args.concurrency, renderer,
    )
    started = time.time()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    def task(index: int, case_dir: Path) -> dict[str, Any]:
        case_id = case_dir.relative_to(input_dir).as_posix()
        return process_case(
            case_dir, case_id, config, renderer, args, index, len(case_dirs)
        )

    with ThreadPoolExecutor(max_workers=args.concurrency,
                            thread_name_prefix="fix-layout") as executor:
        future_map = {
            executor.submit(task, index, case_dir): case_dir
            for index, case_dir in enumerate(case_dirs, start=1)
        }
        for future in as_completed(future_map):
            case_dir = future_map[future]
            case_id = case_dir.relative_to(input_dir).as_posix()
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                log.error("%s | 处理失败: %s", case_id, exc)
                failures.append({"case_id": case_id, "error": str(exc)})

    results.sort(key=lambda item: item["case_id"])
    failures.sort(key=lambda item: item["case_id"])
    elapsed = time.time() - started
    solved = sum(item["status"] == "solved" for item in results)
    clean = sum(item["status"] == "clean" for item in results)
    skipped_clean = sum(item["status"] == "skipped_clean" for item in results)
    unresolved = sum(item["status"] == "unresolved" for item in results)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "model": config["model"],
        "renderer": str(renderer),
        "concurrency": args.concurrency,
        "max_iterations": args.max_iterations,
        "total_cases": len(case_dirs),
        "solved_cases": solved,
        "clean_cases": clean,
        "skipped_clean_cases": skipped_clean,
        "unresolved_cases": unresolved,
        "failed_cases": len(failures),
        "elapsed_seconds": round(elapsed, 3),
        "results": results,
        "failures": failures,
    }
    summary_path = input_dir / SUMMARY_NAME
    write_json(summary_path, summary)
    log.info(
        "修复完成 | 总数=%d | 修复解决=%d | 首检正常=%d | 已跳过=%d | 未解决=%d | 失败=%d | 用时=%.1fs | 汇总=%s",
        len(case_dirs), solved, clean, skipped_clean, unresolved, len(failures),
        elapsed, summary_path,
    )
    return 1 if failures or unresolved else 0


def main() -> int:
    configure_logging()
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
