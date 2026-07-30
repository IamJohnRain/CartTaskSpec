#!/usr/bin/env python3
"""检查修复 DSL 使用的静态素材是否已在对应 TaskSpec 中声明。"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


TASKSPEC_NAME = "task.taskSpec.json"
FIX_DSL_NAME = "fix.card.dsl.jsonl"
REMOVE_NAMES = (
    "layout_issue.result.json",
    "fix.card.dsl.jsonl",
    "fix.card.dsl.png",
)
ASSET_KEYS = {"src", "backgroundImage"}

log = logging.getLogger("fix-asset-declarations")


@dataclass(frozen=True)
class CaseIssue:
    case_dir: Path
    undeclared_assets: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "扫描数据集中的 fix.card.dsl.jsonl，找出未在同 Case "
            "task.taskSpec.json 的 assetCandidates 中声明的静态素材。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  python scripts/check_fix_asset_declarations.py -d datasets/case-600-newSkill-gpt5.5-long
  python scripts/check_fix_asset_declarations.py -d datasets/case-600-newSkill-gpt5.5-long --remove

默认只报告问题，不修改文件。传入 --remove 后，仅对检测到未声明素材的 Case 删除：
  layout_issue.result.json
  fix.card.dsl.jsonl
  fix.card.dsl.png
""",
    )
    parser.add_argument(
        "-d", "--dataset", type=Path, required=True,
        help="数据集目录；递归扫描其下的 Case。",
    )
    parser.add_argument(
        "--remove", action="store_true",
        help="删除命中未声明素材的 Case 中三个指定修复文件。",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def find_case_dirs(dataset: Path) -> list[Path]:
    return sorted(
        {path.parent for path in dataset.rglob(FIX_DSL_NAME)},
        key=lambda path: path.relative_to(dataset).as_posix(),
    )


def normalize_asset_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def is_expression(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("{{") and stripped.endswith("}}")


def iter_static_assets(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in ASSET_KEYS and isinstance(nested, str) and not is_expression(nested):
                yield normalize_asset_path(nested)
            yield from iter_static_assets(nested)
    elif isinstance(value, list):
        for item in value:
            yield from iter_static_assets(item)


def read_fix_assets(path: Path) -> set[str]:
    assets: set[str] = set()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {line_number} 行不是合法 JSON: {exc}") from exc
        assets.update(iter_static_assets(message))
    return assets


def read_declared_assets(path: Path) -> set[str]:
    try:
        taskspec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"TaskSpec 不是合法 JSON: {exc}") from exc
    candidates = taskspec.get("assetCandidates")
    if not isinstance(candidates, list):
        return set()
    return {
        normalize_asset_path(candidate["src"])
        for candidate in candidates
        if isinstance(candidate, dict) and isinstance(candidate.get("src"), str)
    }


def inspect_case(case_dir: Path) -> CaseIssue | None:
    taskspec_path = case_dir / TASKSPEC_NAME
    if not taskspec_path.is_file():
        raise FileNotFoundError(f"缺少 {TASKSPEC_NAME}")
    used_assets = read_fix_assets(case_dir / FIX_DSL_NAME)
    declared_assets = read_declared_assets(taskspec_path)
    undeclared = tuple(sorted(used_assets - declared_assets))
    return CaseIssue(case_dir, undeclared) if undeclared else None


def remove_case_files(case_dir: Path, dataset: Path) -> list[str]:
    resolved_case = case_dir.resolve()
    resolved_dataset = dataset.resolve()
    try:
        resolved_case.relative_to(resolved_dataset)
    except ValueError as exc:
        raise RuntimeError(f"Case 目录超出数据集范围: {resolved_case}") from exc

    removed: list[str] = []
    for filename in REMOVE_NAMES:
        target = resolved_case / filename
        if target.parent != resolved_case:
            raise RuntimeError(f"删除目标异常: {target}")
        if target.is_file():
            target.unlink()
            removed.append(filename)
    return removed


def run(args: argparse.Namespace) -> int:
    dataset = args.dataset.resolve()
    if not dataset.is_dir():
        log.error("数据集目录不存在: %s", dataset)
        return 2

    case_dirs = find_case_dirs(dataset)
    if not case_dirs:
        log.info("未找到 %s，未执行任何操作", FIX_DSL_NAME)
        return 0

    log.info("开始扫描 | dataset=%s | cases=%d | remove=%s",
             dataset, len(case_dirs), args.remove)
    issues: list[CaseIssue] = []
    errors = 0
    removed_cases = 0
    removed_files = 0
    for index, case_dir in enumerate(case_dirs, start=1):
        relative = case_dir.relative_to(dataset).as_posix()
        try:
            issue = inspect_case(case_dir)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            log.error("[%d/%d] %s | 检查失败: %s",
                      index, len(case_dirs), relative, exc)
            continue
        if issue is None:
            log.info("[%d/%d] %s | 素材声明完整", index, len(case_dirs), relative)
            continue

        issues.append(issue)
        log.warning("[%d/%d] %s | 未声明素材: %s", index, len(case_dirs),
                    relative, ", ".join(issue.undeclared_assets))
        if args.remove:
            removed = remove_case_files(case_dir, dataset)
            removed_cases += 1
            removed_files += len(removed)
            log.warning("[%d/%d] %s | 已删除: %s", index, len(case_dirs),
                        relative, ", ".join(removed) if removed else "无匹配文件")

    log.info(
        "扫描完成 | cases=%d | 未声明=%d | 检查失败=%d | 删除Case=%d | 删除文件=%d",
        len(case_dirs), len(issues), errors, removed_cases, removed_files,
    )
    return 1 if errors else 0


def main() -> int:
    configure_logging()
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
