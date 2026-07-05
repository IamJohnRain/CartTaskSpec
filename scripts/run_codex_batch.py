#!/usr/bin/env python3
"""Batch runner: invoke ``codex`` CLI non-interactively, one process per case.

Reads a JSONL dataset (one card-generation case per line) and spawns one
independent ``codex exec`` subAgent per case, loading the configured skill.
The local script is only a scheduler: it materializes the input ``query``
into ``query.txt``, launches codex, captures per-case logs and writes a
summary file. The DSL, CardSpec, TaskSpec and mock data are produced
exclusively by codex.

Constraints respected:
  * only writes inside the configured output directory (under ``datasets/``);
  * never touches ``.agents/skills/``;
  * never parses or rewrites the generated DSL / CardSpec / TaskSpec;
  * model is passed explicitly as ``-m gpt-5.5`` to avoid silent downgrade.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

DEFAULT_INPUT = Path("datasets/case-600-mix-codex-gpt-5.5/600Cases.tagged.jsonl")
DEFAULT_OUTPUT = Path("datasets/case-600-mix-codex-gpt-5.5")
DEFAULT_SKILL = "harmony-card-generation-datamodel-first"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_SANDBOX = "workspace-write"
DEFAULT_CONCURRENCY = 10
DEFAULT_TIMEOUT = 900
SCENARIO_PREFIX_RE = re.compile(r"^(\d{2})-(.+)$")
REQUIRED_FIELDS = ("scenario", "scenario_name", "query")

CODEX_GENERATED_OUTPUTS = (
    "card.cardspec.json",
    "card.dsl.jsonl",
    "task.taskSpec.json",
)
EXPECTED_OUTPUTS = ("query.txt", *CODEX_GENERATED_OUTPUTS)

PROMPT_TEMPLATE = """\
$harmony-card-generation-datamodel-first

为下面这**一个** Case 生成 HarmonyOS A2UI Form 卡片 DSL 与 TaskSpec。
**只处理当前 case，不要遍历或读取 JSONL 其它行，不要批量处理。**

# Case
- case_id: {case_id}
- scenario: {scenario}
- scenario_name: {scenario_name}
- query: {query}
- axes: {axes}
- source: {source}

# 唯一允许写文件的目录
{output_dir}

必须生成以下 4 个文件（其它路径一律不要写）：
1. query.txt           —— 核对/覆盖已有内容（与上面那条 query 一致即可）
2. card.cardspec.json  —— 卡片规格，参考仓库根的 TaskSpec.md
3. card.dsl.jsonl      —— 恰好 3 行 JSONL：createSurface / updateComponents / updateDataModel
4. task.taskSpec.json  —— TaskSpec 协议（顶层只允许 userQuery / size / eventCandidates / dataModel / assetCandidates）

# 协议硬性要求
- 严格遵循仓库根目录下的 TaskSpec.md 与 taskspec.schema.json。
- 卡片尺寸取 axes.size（必须是 2x2 或 2x4）；root shell 完整。
- 组件范围: Text / Image / Divider / Progress / Button / Checkbox / Row / Column / List / Stack。
- DSL 第 3 行 updateDataModel.value 必须 == TaskSpec.dataModel.value。
- DSL 中所有数据绑定路径必须能在 dataModel.value 中找到。
- eventCandidates 必须使用 clickToCallPhone / clickToDeeplink / clickToIntent 之一；不允许出现 id / label / description / required / onClick。
- assetCandidates[].description 必须非空；如设置 bindTo，路径必须能解析到 dataModel.value。

# 其它硬性要求
1. 模型必须是 GPT-5.5，不要降级到 5.4 或其它。
2. 不要修改 .agents/skills/ 下任何内容，不要写 datasets/ 之外的任何路径。
3. 每个可见组件只承载一个信息职责，避免信息重复；文本不要截断。
4. 完成后直接结束，不要输出解释、总结、校验日志或命令。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_codex_batch.py",
        description=(
            "Run one independent `codex exec` subAgent per JSONL case, "
            "using the configured skill. The local script only schedules; "
            "DSL / CardSpec / TaskSpec / mock data are produced by codex."
        ),
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input JSONL path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output root directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Max concurrent codex processes (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--cd",
        dest="workdir",
        type=Path,
        default=None,
        help="Working directory for codex (default: repo root inferred from this script)",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model passed as -m to codex exec (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--skill",
        default=DEFAULT_SKILL,
        help=f"Skill name used in prompt (default: {DEFAULT_SKILL})",
    )
    parser.add_argument(
        "--sandbox",
        default=DEFAULT_SANDBOX,
        choices=["read-only", "workspace-write", "danger-full-access"],
        help=f"Sandbox mode (default: {DEFAULT_SANDBOX})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-case timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Process only the first N cases (debugging)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip cases whose generated outputs already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the schedule without launching codex",
    )
    return parser.parse_args()


def infer_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_cases(path: Path, limit: Optional[int]) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"input not found: {path}")
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            for field in REQUIRED_FIELDS:
                if field not in obj:
                    raise ValueError(f"{path}:{lineno}: missing field {field!r}")
            cases.append(obj)
            if limit is not None and len(cases) >= limit:
                break
    return cases


def assign_case_ids(cases: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Return list of (case_id, case_dict), preserving JSONL order.

    Naming: ``Case-{XX}-{scenario}-{NNN}``
      * ``XX``     = 2-digit scenario prefix extracted from the ``scenario``
        field (e.g. ``01-low-power`` -> ``01``); falls back to a fresh
        ordinal beyond the existing range when no prefix is present.
      * ``scenario`` = the literal scenario stem (e.g. ``low-power``).
      * ``NNN``   = 3-digit per-scenario ordinal by JSONL position.
    """
    by_scenario: dict[str, list[int]] = {}
    for idx, case in enumerate(cases):
        by_scenario.setdefault(case["scenario"], []).append(idx)

    existing_prefixes: list[int] = []
    for sc in by_scenario:
        m = SCENARIO_PREFIX_RE.match(sc)
        if m:
            existing_prefixes.append(int(m.group(1)))
    existing_prefixes.sort()

    ordinals: dict[int, str] = {}
    for sc, indices in by_scenario.items():
        m = SCENARIO_PREFIX_RE.match(sc)
        if m:
            prefix = m.group(1)
            stem = m.group(2)
        else:
            stem = sc
            base = (existing_prefixes[-1] if existing_prefixes else 0) + 31
            prefix = f"{base:02d}"
        for nnn, case_idx in enumerate(indices, start=1):
            ordinals[case_idx] = f"Case-{prefix}-{stem}-{nnn:03d}"

    return [(ordinals[i], cases[i]) for i in range(len(cases))]


def build_prompt(case_id: str, case: dict[str, Any], case_dir: Path) -> str:
    return PROMPT_TEMPLATE.format(
        case_id=case_id,
        scenario=case.get("scenario", ""),
        scenario_name=case.get("scenario_name", ""),
        query=case.get("query", ""),
        axes=json.dumps(case.get("axes", {}), ensure_ascii=False),
        source=case.get("source", ""),
        output_dir=str(case_dir.resolve()),
    )


@dataclass
class CaseResult:
    case_id: str
    scenario: str
    returncode: Optional[int]
    duration_sec: float
    timed_out: bool
    missing_files: list[str]
    log_path: str
    error: Optional[str] = None


def check_outputs(case_dir: Path) -> list[str]:
    return [name for name in EXPECTED_OUTPUTS if not (case_dir / name).is_file()]


def case_already_done(case_dir: Path, skip_existing: bool) -> bool:
    if not skip_existing:
        return False
    return not check_outputs(case_dir)


async def run_one_case(
    case_id: str,
    case: dict[str, Any],
    output_root: Path,
    workdir: Path,
    model: str,
    sandbox: str,
    timeout: int,
    sem: asyncio.Semaphore,
    dry_run: bool,
    log_root: Path,
) -> CaseResult:
    case_dir = output_root / case_id
    log_path = log_root / f"{case_id}.log"
    start = time.monotonic()

    if dry_run:
        return CaseResult(
            case_id=case_id,
            scenario=case.get("scenario", ""),
            returncode=None,
            duration_sec=0.0,
            timed_out=False,
            missing_files=[],
            log_path=str(log_path),
        )

    try:
        case_dir.mkdir(parents=True, exist_ok=True)
        log_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return CaseResult(
            case_id=case_id,
            scenario=case.get("scenario", ""),
            returncode=None,
            duration_sec=time.monotonic() - start,
            timed_out=False,
            missing_files=list(EXPECTED_OUTPUTS),
            log_path=str(log_path),
            error=f"mkdir failed: {exc}",
        )

    query_path = case_dir / "query.txt"
    try:
        query_path.write_text(case.get("query", ""), encoding="utf-8")
    except OSError as exc:
        return CaseResult(
            case_id=case_id,
            scenario=case.get("scenario", ""),
            returncode=None,
            duration_sec=time.monotonic() - start,
            timed_out=False,
            missing_files=list(EXPECTED_OUTPUTS),
            log_path=str(log_path),
            error=f"write query.txt failed: {exc}",
        )

    prompt = build_prompt(case_id, case, case_dir)
    cmd = [
        "codex",
        "exec",
        "--cd",
        str(workdir),
        "--add-dir",
        str(case_dir.resolve()),
        "--sandbox",
        sandbox,
        "--dangerously-bypass-approvals-and-sandbox",
        "-m",
        model,
        "--ephemeral",
        prompt,
    ]

    async with sem:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(workdir),
            )
        except FileNotFoundError as exc:
            return CaseResult(
                case_id=case_id,
                scenario=case.get("scenario", ""),
                returncode=None,
                duration_sec=time.monotonic() - start,
                timed_out=False,
                missing_files=list(EXPECTED_OUTPUTS),
                log_path=str(log_path),
                error=f"failed to launch codex: {exc}",
            )

        timed_out = False
        stdout = b""
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                stdout, _ = await proc.communicate()
            except Exception:
                stdout = b""

    rc = proc.returncode
    duration = time.monotonic() - start

    try:
        payload = b"\xef\xbb\xbf" + (stdout or b"")  # UTF-8 BOM so Notepad/VSCode auto-detect
        log_path.write_bytes(payload)
    except OSError as exc:
        print(f"warn: cannot write log {log_path}: {exc}", file=sys.stderr)

    missing = check_outputs(case_dir)
    error: Optional[str] = None
    if timed_out:
        error = f"timeout after {timeout}s"
    elif rc != 0 and missing:
        error = f"codex rc={rc}, missing={','.join(missing)}"
    elif rc != 0:
        error = f"codex rc={rc}"

    return CaseResult(
        case_id=case_id,
        scenario=case.get("scenario", ""),
        returncode=rc,
        duration_sec=duration,
        timed_out=timed_out,
        missing_files=missing,
        log_path=str(log_path),
        error=error,
    )


def print_plan(args: argparse.Namespace, assigned: list[tuple[str, dict[str, Any]]]) -> None:
    scenarios = sorted({c["scenario"] for _, c in assigned})
    print(f"[plan] input         : {args.input.resolve()}")
    print(f"[plan] output_root   : {args.output.resolve()}")
    print(f"[plan] workdir       : {(args.workdir or infer_repo_root()).resolve()}")
    print(f"[plan] cases         : {len(assigned)} ({len(scenarios)} scenarios)")
    print(f"[plan] concurrency   : {args.concurrency}")
    print(f"[plan] model         : {args.model}")
    print(f"[plan] skill         : {args.skill}")
    print(f"[plan] sandbox       : {args.sandbox}")
    print(f"[plan] timeout/case  : {args.timeout}s")
    print(f"[plan] skip_existing : {args.skip_existing}")
    print(f"[plan] dry_run       : {args.dry_run}")
    if args.dry_run:
        preview = assigned[: min(5, len(assigned))]
        for case_id, case in preview:
            print(f"  would run: {case_id} ({case.get('scenario')})")
        if len(assigned) > len(preview):
            print(f"  ... (+{len(assigned) - len(preview)} more)")


async def main_async(args: argparse.Namespace) -> int:
    workdir = (args.workdir or infer_repo_root()).resolve()
    input_path = args.input.resolve()
    output_root = args.output.resolve()
    log_root = output_root / "_logs"

    if args.concurrency < 1:
        print(f"error: --concurrency must be >= 1, got {args.concurrency}", file=sys.stderr)
        return 2
    if args.timeout < 1:
        print(f"error: --timeout must be >= 1, got {args.timeout}", file=sys.stderr)
        return 2

    try:
        cases = load_cases(input_path, args.limit)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not cases:
        print("error: no cases in input", file=sys.stderr)
        return 2

    output_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)

    assigned = assign_case_ids(cases)
    print_plan(args, assigned)

    if args.dry_run:
        return 0

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [
        asyncio.create_task(
            run_one_case(
                case_id=cid,
                case=case,
                output_root=output_root,
                workdir=workdir,
                model=args.model,
                sandbox=args.sandbox,
                timeout=args.timeout,
                sem=sem,
                dry_run=False,
                log_root=log_root,
            )
        )
        for cid, case in assigned
        if not case_already_done(output_root / cid, args.skip_existing)
    ]

    if not tasks:
        print("nothing to do (all cases skipped)")
        return 0

    print(f"[run] launching {len(tasks)} case(s) (concurrency={args.concurrency})...")
    t0 = time.monotonic()
    results = await asyncio.gather(*tasks)
    total = time.monotonic() - t0

    summary_path = output_root / "_summary.jsonl"
    with summary_path.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(asdict(r), ensure_ascii=False))
            fh.write("\n")

    succ = sum(1 for r in results if r.error is None)
    fail = [r for r in results if r.error is not None]
    print()
    print("=" * 72)
    print(f"summary: total={len(results)} success={succ} fail={len(fail)} duration={total:.1f}s")
    if fail:
        print("failures:")
        for r in fail:
            tag = "TIMEOUT" if r.timed_out else f"rc={r.returncode}"
            miss = f" missing={','.join(r.missing_files)}" if r.missing_files else ""
            print(f"  - {r.case_id} [{tag}] {r.error}{miss} (log={r.log_path})")
    print(f"summary written to {summary_path}")
    print("=" * 72)
    return 0 if not fail else 1


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
