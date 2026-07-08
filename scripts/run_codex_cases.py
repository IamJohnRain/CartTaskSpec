#!/usr/bin/env python3
"""Run dataset cases through independent Codex CLI executions.

This script replaces the previous "main Agent starts SubAgents" workflow with a
local dispatcher that starts one `codex exec` process per case. The dispatcher
only prepares per-case inputs, controls concurrency, and records logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_JOBS = 6
DEFAULT_LIMIT = 100
DEFAULT_PROMPT_TEMPLATE = Path("prompts.txt")
REQUIRED_OUTPUTS = ("query.txt", "card.cardspec.json", "card.dsl.jsonl", "task.taskSpec.json")


PROMPT_TEMPLATE = """你是一个独立的 Codex 子任务执行进程。你只负责当前目录中的一个 case。

目标：
1. 阅读当前目录的 `case.json`、`query.txt`、`TaskSpec.md`。
2. 根据用户 query 生成 HarmonyOS A2UI Form 服务卡片产物。
3. 在当前目录写入以下文件：
   - `query.txt`：保留原始 query，不要改写语义。
   - `task.taskSpec.json`：符合 `TaskSpec.md` 协议的 TaskSpec。
   - `card.dsl.jsonl`：三行 genui JSONL。
   - `card.cardspec.json`：CardSpec JSON。

必须遵守：
- 只允许读取和修改当前执行目录中的文件。
- 禁止修改当前目录之外的任何文件或目录。
- 禁止修改 skill、脚本、仓库源码或其他 case 目录。
- 读取和写入文件都使用 UTF-8。
- 严格遵守下方“全局任务要求”。其中关于 DSL、TaskSpec、CardSpec、素材、事件、校验和禁止模板循环的要求优先级高于任何旧经验。
- 特别注意：暂时禁止使用 `children: {{"componentId":"...","path":"/..."}}` 模板循环对象；数组内容必须改用显式索引路径绑定到固定组件。

全局任务要求（来自 {prompt_source}）：
{batch_prompt}

当前 case：
```json
{case_json}
```

请直接生成并保存文件。最终回复只需简短说明完成情况。
"""


@dataclass(frozen=True)
class CaseItem:
    line_no: int
    scenario: str
    scenario_index: int
    query: str
    payload: dict

    @property
    def directory_name(self) -> str:
        scenario_slug = slugify(self.scenario or "unknown-scenario")
        return f"Case-{scenario_slug}-{self.scenario_index:03d}"


@dataclass
class CaseResult:
    case: CaseItem
    ok: bool
    returncode: int | None
    elapsed: float
    out_dir: Path
    error: str = ""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{now()}] {message}", flush=True)


def slugify(value: str) -> str:
    value = value.strip().replace("\\", "-").replace("/", "-")
    value = re.sub(r"[^0-9A-Za-z._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "case"


def parse_index(value: str | None, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("index must be >= 1")
    return parsed


def load_cases(path: Path) -> list[CaseItem]:
    cases: list[CaseItem] = []
    scenario_counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} is not valid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_no} must be a JSON object")
            scenario = str(payload.get("scenario") or f"line-{line_no:03d}")
            query = str(payload.get("query") or "").strip()
            if not query:
                raise ValueError(f"{path}:{line_no} missing non-empty query field")
            scenario_counts[scenario] += 1
            cases.append(
                CaseItem(
                    line_no=line_no,
                    scenario=scenario,
                    scenario_index=scenario_counts[scenario],
                    query=query,
                    payload=payload,
                )
            )
    return cases


def select_cases(
    cases: Iterable[CaseItem],
    *,
    start: int | None,
    end: int | None,
    limit: int | None,
) -> list[CaseItem]:
    selected = [
        case
        for case in cases
        if (start is None or case.line_no >= start) and (end is None or case.line_no <= end)
    ]
    if limit is not None and limit > 0:
        selected = selected[:limit]
    return selected


def write_case_inputs(case: CaseItem, case_dir: Path, taskspec_path: Path, force: bool) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = case_dir / "prompt.txt"
    files_to_create = [
        case_dir / "query.txt",
        case_dir / "case.json",
        case_dir / "TaskSpec.md",
        prompt_path,
    ]
    if not force:
        existing_outputs = [case_dir / name for name in REQUIRED_OUTPUTS if (case_dir / name).exists()]
        if existing_outputs:
            names = ", ".join(path.name for path in existing_outputs)
            raise FileExistsError(f"{case_dir} already contains output file(s): {names}; use --force to rerun")

    (case_dir / "query.txt").write_text(case.query + "\n", encoding="utf-8")
    (case_dir / "case.json").write_text(
        json.dumps(case.payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(taskspec_path, case_dir / "TaskSpec.md")
    prompt_path.write_text(
        PROMPT_TEMPLATE.format(case_json=json.dumps(case.payload, ensure_ascii=False, indent=2)),
        encoding="utf-8",
    )

    for path in files_to_create:
        if not path.exists():
            raise RuntimeError(f"failed to prepare {path}")


def build_codex_command(args: argparse.Namespace, case_dir: Path, prompt_path: Path, output_path: Path) -> list[str]:
    command = [
        args.codex_bin,
        "exec",
        "--cd",
        str(case_dir),
        "--sandbox",
        args.sandbox,
        "--ask-for-approval",
        args.approval,
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
    ]
    if args.ephemeral:
        command.append("--ephemeral")
    if args.model:
        command.extend(["--model", args.model])
    if args.profile:
        command.extend(["--profile", args.profile])
    command.append("-")
    return command


async def pipe_stream(prefix: str, stream: asyncio.StreamReader, log_path: Path) -> None:
    with log_path.open("ab") as handle:
        while True:
            line = await stream.readline()
            if not line:
                break
            handle.write(line)
            handle.flush()
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                log(f"{prefix} {text}")


def verify_outputs(case_dir: Path) -> tuple[bool, str]:
    missing = [name for name in REQUIRED_OUTPUTS if not (case_dir / name).is_file()]
    if missing:
        return False, "missing output file(s): " + ", ".join(missing)
    dsl_lines = [line for line in (case_dir / "card.dsl.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(dsl_lines) != 3:
        return False, f"card.dsl.jsonl must contain exactly 3 non-empty lines, got {len(dsl_lines)}"
    for name in ("card.cardspec.json", "task.taskSpec.json"):
        try:
            json.loads((case_dir / name).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return False, f"{name} is not valid JSON: {exc}"
    for index, line in enumerate(dsl_lines, start=1):
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            return False, f"card.dsl.jsonl line {index} is not valid JSON: {exc}"
    return True, ""


async def run_case(
    case: CaseItem,
    args: argparse.Namespace,
    output_dir: Path,
    taskspec_path: Path,
    semaphore: asyncio.Semaphore,
) -> CaseResult:
    async with semaphore:
        case_dir = output_dir / case.directory_name
        started = time.perf_counter()
        log(f"START line={case.line_no} case={case.directory_name} scenario={case.scenario}")
        try:
            write_case_inputs(case, case_dir, taskspec_path, args.force)
        except Exception as exc:
            elapsed = time.perf_counter() - started
            log(f"FAIL  line={case.line_no} case={case.directory_name} prepare_error={exc}")
            return CaseResult(case, False, None, elapsed, case_dir, str(exc))

        prompt_path = case_dir / "prompt.txt"
        final_message_path = case_dir / "codex.final.md"
        stdout_path = case_dir / "codex.stdout.log"
        stderr_path = case_dir / "codex.stderr.log"
        command = build_codex_command(args, case_dir, prompt_path, final_message_path)
        prompt_text = prompt_path.read_text(encoding="utf-8")

        if args.dry_run:
            elapsed = time.perf_counter() - started
            log(f"DRY   line={case.line_no} case={case.directory_name} command={' '.join(command)}")
            return CaseResult(case, True, 0, elapsed, case_dir)

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(case_dir),
            )
            assert process.stdin is not None
            process.stdin.write(prompt_text.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

            stdout_task = asyncio.create_task(pipe_stream(f"[{case.directory_name}][stdout]", process.stdout, stdout_path))
            stderr_task = asyncio.create_task(pipe_stream(f"[{case.directory_name}][stderr]", process.stderr, stderr_path))
            try:
                returncode = await asyncio.wait_for(process.wait(), timeout=args.timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                await asyncio.gather(stdout_task, stderr_task)
                returncode = process.returncode
                elapsed = time.perf_counter() - started
                log(f"TIMEOUT line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s")
                return CaseResult(case, False, returncode, elapsed, case_dir, f"timeout after {args.timeout}s")
            await asyncio.gather(stdout_task, stderr_task)
        except FileNotFoundError as exc:
            elapsed = time.perf_counter() - started
            log(f"FAIL  line={case.line_no} case={case.directory_name} codex not found: {args.codex_bin}")
            return CaseResult(case, False, None, elapsed, case_dir, str(exc))

        ok, error = verify_outputs(case_dir)
        elapsed = time.perf_counter() - started
        if returncode == 0 and ok:
            log(f"DONE  line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s")
            return CaseResult(case, True, returncode, elapsed, case_dir)

        if returncode != 0 and not error:
            error = f"codex exited with code {returncode}"
        elif returncode != 0:
            error = f"codex exited with code {returncode}; {error}"
        log(f"FAIL  line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s error={error}")
        return CaseResult(case, False, returncode, elapsed, case_dir, error)


def write_summary(output_dir: Path, results: list[CaseResult]) -> None:
    summary = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "ok": sum(1 for result in results if result.ok),
        "failed": sum(1 for result in results if not result.ok),
        "results": [
            {
                "line": result.case.line_no,
                "scenario": result.case.scenario,
                "case": result.case.directory_name,
                "ok": result.ok,
                "returncode": result.returncode,
                "elapsedSeconds": round(result.elapsed, 3),
                "outputDir": str(result.out_dir),
                "error": result.error,
            }
            for result in results
        ],
    }
    (output_dir / "codex_batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-run JSONL cases with Codex CLI, one isolated codex exec process per case."
    )
    parser.add_argument("jsonl", type=Path, help="Input dataset JSONL file, UTF-8 encoded.")
    parser.add_argument("-o", "--output-dir", required=True, type=Path, help="Directory where case outputs are saved.")
    parser.add_argument("-j", "--jobs", type=int, default=DEFAULT_JOBS, help=f"Parallel Codex processes. Default: {DEFAULT_JOBS}.")
    parser.add_argument("--start", type=lambda value: parse_index(value), help="1-based inclusive start line.")
    parser.add_argument("--end", type=lambda value: parse_index(value), help="1-based inclusive end line.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum selected cases to run. Default: {DEFAULT_LIMIT}; use 0 for no limit.",
    )
    parser.add_argument("--model", help="Codex model name passed to `codex exec --model`.")
    parser.add_argument("--profile", help="Codex config profile passed to `codex exec --profile`.")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable path. Default: codex.")
    parser.add_argument("--sandbox", default="workspace-write", choices=["read-only", "workspace-write", "danger-full-access"])
    parser.add_argument("--approval", default="never", choices=["untrusted", "on-request", "never"])
    parser.add_argument("--timeout", type=int, default=1800, help="Per-case timeout in seconds. Default: 1800.")
    parser.add_argument("--task-spec", type=Path, default=Path("TaskSpec.md"), help="TaskSpec.md path copied into each case dir.")
    parser.add_argument("--force", action="store_true", help="Allow rerunning into a case dir that already has output files.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare inputs and print commands without running Codex.")
    parser.add_argument("--ephemeral", action="store_true", help="Pass `--ephemeral` to codex exec.")
    return parser.parse_args(argv)


async def async_main(args: argparse.Namespace) -> int:
    if args.jobs < 1:
        raise ValueError("--jobs must be >= 1")
    args.limit = None if args.limit == 0 else args.limit

    jsonl_path = args.jsonl.resolve()
    output_dir = args.output_dir.resolve()
    taskspec_path = args.task_spec.resolve()
    if not jsonl_path.is_file():
        raise FileNotFoundError(f"input JSONL not found: {jsonl_path}")
    if not taskspec_path.is_file():
        raise FileNotFoundError(f"TaskSpec file not found: {taskspec_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_cases(jsonl_path)
    selected = select_cases(cases, start=args.start, end=args.end, limit=args.limit)
    if not selected:
        log("No cases selected.")
        return 0

    log(
        "Batch start "
        f"input={jsonl_path} output={output_dir} cases={len(selected)} "
        f"jobs={args.jobs} range={args.start or 1}-{args.end or 'EOF'} limit={args.limit or 'none'}"
    )
    semaphore = asyncio.Semaphore(args.jobs)
    results = await asyncio.gather(
        *(run_case(case, args, output_dir, taskspec_path, semaphore) for case in selected)
    )
    write_summary(output_dir, list(results))

    ok_count = sum(1 for result in results if result.ok)
    fail_count = len(results) - ok_count
    log(f"Batch finished total={len(results)} ok={ok_count} failed={fail_count} summary={output_dir / 'codex_batch_summary.json'}")
    return 0 if fail_count == 0 else 1


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv or sys.argv[1:])
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        log("Interrupted.")
        return 130
    except Exception as exc:
        log(f"ERROR {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
