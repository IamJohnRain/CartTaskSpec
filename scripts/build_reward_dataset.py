#!/usr/bin/env python3
"""为每个 case 目录生成奖励模型训练数据。

阶段一（始终执行）：扫描每个 Case-* 子目录，读取 query.txt /
card.dsl.jsonl / score.result.json，组装成 OpenAI 风格 chat 训练样本，
写入该 case 目录下的 reward.request.json。

阶段二（-o 传入时执行）：把全部样本聚合到输出目录：
  - 不传 --split_ratio  -> 全量写 <output>/train.jsonl
  - 传 --split_ratio    -> 按比例随机切分，写 train.jsonl + test.jsonl

评分三维度来源：score.result.json -> scores.{instruction,aesthetic,layout}
（详见 scripts/build_score.py）。

示例：
  # 仅生成每 case 的 reward.request.json
  python scripts/build_reward_dataset.py -d datasets/case-600-newSkill-gpt5.5

  # 聚合到目录（不拆分）
  python scripts/build_reward_dataset.py -d datasets/case-600 -o output/

  # 8:2 随机拆分（--split_ratio 表示训练集比例）
  python scripts/build_reward_dataset.py -d datasets/case-600 -o output/ --split_ratio 0.8
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# --------------------------------------------------------------------------- #
# 文件名约定（每个 case 目录）
# --------------------------------------------------------------------------- #
QUERY_NAME = "query.txt"
DSL_NAME = "card.dsl.jsonl"
SCORE_RESULT_NAME = "score.result.json"
REWARD_REQUEST_NAME = "reward.request.json"

# --------------------------------------------------------------------------- #
# 奖励模型 system prompt（精简，引导模型理解任务并给出符合格式的分数）
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """你是 HarmonyOS A2UI Form 服务卡片的质量评审奖励模型。你会收到用户原始指令和模型生成的卡片 genui DSL（3 行 JSONL），你的任务是从三个维度对卡片打分（0-10，给到小数点后 1 位）：
- instruction（指令遵从）：是否满足用户原始指令的明确诉求，信息是否齐全、事件是否落实、素材是否正确。
- aesthetic（样式美观）：配色是否和谐、文字是否清晰可读、字号字重层级与留白对齐是否舒适。
- layout（排版布局）：是否存在元素堆叠重叠、文字被裁切/截断、组件溢出卡片边界等布局问题。

只输出一个 ```json``` 代码块，schema 固定为：
{"scores": {"instruction": 0-10, "aesthetic": 0-10, "layout": 0-10}}
不要输出 <think> 标签、解释、前后缀文字。"""

# --------------------------------------------------------------------------- #
# 读取各文件
# --------------------------------------------------------------------------- #
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _read_dsl_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s:
            lines.append(s)
    return lines


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 组装训练样本
# --------------------------------------------------------------------------- #
SCORE_DIMS = ("instruction", "aesthetic", "layout")


def _extract_scores(score_result: dict) -> dict | None:
    """从 score.result.json 提取三维度分数；任一缺失返回 None。"""
    raw_scores = score_result.get("scores") or {}
    out: dict[str, float] = {}
    for dim in SCORE_DIMS:
        item = raw_scores.get(dim) or {}
        if not isinstance(item, dict):
            return None
        score = item.get("score")
        if not isinstance(score, (int, float)):
            return None
        out[dim] = float(score)
    return out


def _build_user_text(query: str, dsl_lines: list[str]) -> str:
    dsl_block = "\n".join(dsl_lines) if dsl_lines else "(无)"
    return (
        f"=== 用户原始指令 ===\n{query}\n\n"
        f"=== 待评审卡片 DSL（{len(dsl_lines)} 行 JSONL）===\n{dsl_block}"
    )


def _build_assistant_content(scores: dict) -> str:
    payload = {"scores": scores}
    body = json.dumps(payload, ensure_ascii=False)
    return f"```json\n{body}\n```"


def build_sample(query: str, dsl_lines: list[str], scores: dict) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_text(query, dsl_lines)},
            {"role": "assistant", "content": _build_assistant_content(scores)},
        ]
    }


# --------------------------------------------------------------------------- #
# case 发现
# --------------------------------------------------------------------------- #
def find_case_dirs(dataset: Path, case_filter: str | None = None) -> list[Path]:
    def _is_case(d: Path) -> bool:
        return d.is_dir() and d.name.startswith("Case-")

    dirs = sorted(d for d in dataset.iterdir() if _is_case(d))
    if case_filter:
        dirs = [d for d in dirs if case_filter in d.name]
    return dirs


def process_case(case_dir: Path, overwrite: bool) -> tuple[str, dict | None]:
    """返回 (status, sample)：sample 仅在成功时非 None。"""
    out_path = case_dir / REWARD_REQUEST_NAME
    if out_path.exists() and not overwrite:
        # 即使跳过也尽量回读样本，便于阶段二聚合
        try:
            return "skip_exists", _load_json(out_path)
        except Exception:
            return "skip_exists", None

    try:
        query = _read_text(case_dir / QUERY_NAME)
        dsl_lines = _read_dsl_lines(case_dir / DSL_NAME)
        score_result = _load_json(case_dir / SCORE_RESULT_NAME)
    except Exception as e:  # noqa: BLE001
        return f"skip_read_error:{e!r}", None

    if not query or not dsl_lines:
        return "skip_empty", None

    scores = _extract_scores(score_result)
    if scores is None:
        return "skip_no_scores", None

    sample = build_sample(query, dsl_lines, scores)
    out_path.write_text(
        json.dumps(sample, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return "ok", sample


# --------------------------------------------------------------------------- #
# 聚合与拆分
# --------------------------------------------------------------------------- #
def _write_jsonl(path: Path, samples: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def split_samples(samples: list[dict], ratio: float,
                  seed: int) -> tuple[list[dict], list[dict]]:
    """按 ratio（训练集比例）随机切分。"""
    rng = random.Random(seed)
    shuffled = list(samples)
    rng.shuffle(shuffled)
    n_train = int(round(len(shuffled) * ratio))
    return shuffled[:n_train], shuffled[n_train:]


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "为每个 Case-* 子目录生成奖励模型训练数据 reward.request.json。\n"
            "读取每个 case 下的 query.txt / card.dsl.jsonl / score.result.json，\n"
            "组装成 OpenAI 风格的 3-message chat 样本（system/user/assistant）。\n"
            "assistant 目标内容为 ```json``` 代码块，只含三个维度的分数\n"
            "（instruction 指令遵从 / aesthetic 样式美观 / layout 排版布局），\n"
            "分数取自 score.result.json（详见 scripts/build_score.py）。\n\n"
            "阶段一（始终执行）：为每个 case 写 reward.request.json。\n"
            "阶段二（仅当 -o 传入）：聚合样本到输出目录：\n"
            "  - 不传 --split_ratio  -> 全量写 train.jsonl\n"
            "  - 传 --split_ratio    -> 按比例随机切分，写 train.jsonl + test.jsonl"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  # 仅生成每个 case 的 reward.request.json\n"
            "  python scripts/build_reward_dataset.py "
            "-d datasets/case-600-newSkill-gpt5.5\n\n"
            "  # 聚合到目录，全量写 train.jsonl（不拆分）\n"
            "  python scripts/build_reward_dataset.py "
            "-d datasets/case-600-newSkill-gpt5.5 -o output/\n\n"
            "  # 8:2 随机拆分（--split_ratio 表示训练集比例）\n"
            "  python scripts/build_reward_dataset.py "
            "-d datasets/case-600-newSkill-gpt5.5 -o output/ --split_ratio 0.8\n\n"
            "  # 指定随机种子 + 覆盖已有文件\n"
            "  python scripts/build_reward_dataset.py "
            "-d datasets/case-600-newSkill-gpt5.5 -o output/ "
            "--split_ratio 0.8 --seed 123 --overwrite\n\n"
            "  # 调试单个 case（子串匹配）\n"
            "  python scripts/build_reward_dataset.py "
            "-d datasets/case-600-newSkill-gpt5.5 -c Case-01-low-power-001"
        ),
    )
    parser.add_argument("-d", "--dataset", type=Path, required=True,
                        help="【必填】数据集根目录，其下每个 Case-* 子目录为一个 case。")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="输出目录；传入时聚合样本到该目录下的 "
                             "train.jsonl（带 --split_ratio 时额外写 test.jsonl）。"
                             "不传则只生成每个 case 的 reward.request.json。")
    parser.add_argument("--split_ratio", type=float, default=None,
                        help="训练集比例（0-1 之间的浮点数），如 0.8 表示 "
                             "80%% 进 train.jsonl、20%% 进 test.jsonl。"
                             "不传则全量写 train.jsonl。需配合 -o 使用。")
    parser.add_argument("--seed", type=int, default=42,
                        help="拆分随机种子，默认 42；同种子下切分结果可复现。")
    parser.add_argument("-c", "--case", type=str, default=None,
                        help="只处理名称匹配的 case（子串匹配，调试用）。")
    parser.add_argument("--overwrite", action="store_true",
                        help="覆盖已存在的 reward.request.json（默认跳过）。")
    args = parser.parse_args()

    if not args.dataset.is_dir():
        print(f"error: 数据集目录不存在: {args.dataset}", file=sys.stderr)
        return 1

    if args.split_ratio is not None and not (0.0 < args.split_ratio < 1.0):
        print("error: --split_ratio 必须在 (0, 1) 之间", file=sys.stderr)
        return 1

    if args.output is None and args.split_ratio is not None:
        print("error: 使用 --split_ratio 必须同时指定 -o/--output",
              file=sys.stderr)
        return 1

    case_dirs = find_case_dirs(args.dataset, args.case)
    if not case_dirs:
        print("未找到任何 Case-* 子目录。", file=sys.stderr)
        return 1

    # ------------------- 阶段一：逐 case 生成 reward.request.json -------- #
    counters: dict[str, int] = {}
    samples: list[dict] = []
    for i, d in enumerate(case_dirs, 1):
        status, sample = process_case(d, args.overwrite)
        counters[status] = counters.get(status, 0) + 1
        if status == "ok":
            print(f"  [{i}/{len(case_dirs)}] ok    {d.name}")
            if sample is not None:
                samples.append(sample)
        elif status == "skip_exists":
            if sample is not None:
                samples.append(sample)
            print(f"  [{i}/{len(case_dirs)}] skip  {d.name} (已存在，--overwrite 覆盖)")
        else:
            print(f"  [{i}/{len(case_dirs)}] ERR   {d.name} -> {status}",
                  file=sys.stderr)

    ok = counters.get("ok", 0) + counters.get("skip_exists", 0)
    err = sum(v for k, v in counters.items()
              if k not in ("ok", "skip_exists"))
    print(f"\n[阶段一] 处理 {len(case_dirs)} 个 | 成功/已有 {ok} "
          f"| 跳过/错误 {err}")
    if not samples:
        print("无可用样本，结束。", file=sys.stderr)
        return 1

    # ------------------- 阶段二：聚合 / 拆分 ----------------------------- #
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        if args.split_ratio is not None:
            train, test = split_samples(samples, args.split_ratio, args.seed)
            train_path = args.output / "train.jsonl"
            test_path = args.output / "test.jsonl"
            _write_jsonl(train_path, train)
            _write_jsonl(test_path, test)
            print(f"[阶段二] 拆分 ratio={args.split_ratio} seed={args.seed}")
            print(f"  train.jsonl: {len(train)} 条 -> {train_path}")
            print(f"  test.jsonl : {len(test)} 条 -> {test_path}")
        else:
            train_path = args.output / "train.jsonl"
            _write_jsonl(train_path, samples)
            print(f"[阶段二] 全量聚合")
            print(f"  train.jsonl: {len(samples)} 条 -> {train_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
