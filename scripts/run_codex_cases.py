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
REQUIRED_OUTPUTS = ("query.txt", "card.cardspec.json", "card.dsl.jsonl", "task.taskSpec.json")
VALIDATED_OUTPUTS = ("card.dsl.jsonl", "card.cardspec.json", "task.taskSpec.json")
DEFAULT_TASKSPEC_REFS_VALIDATOR = Path("scripts/validate_taskspec_dsl_refs.py")
DEFAULT_CARD_VALIDATOR = Path(".agents/skills/harmony-card-generation-datamodel-first/scripts/validate_card.py")
LOG_PATH: Path | None = None


PROMPT_TEMPLATE = """你是一个独立的 Codex CLI 子任务进程，只负责当前目录中的这一个 HarmonyOS A2UI Form 服务卡片 case。

当前 case JSON：
```json
{case_json}
```

当前目录已经包含：
- `query.txt`：原始用户需求，必须保持语义不变。
- `TaskSpec.md`：TaskSpec 协议说明，生成 `task.taskSpec.json` 时必须遵守。

你的目标是在当前目录生成并保存：
- `task.taskSpec.json`
- `card.dsl.jsonl`
- `card.cardspec.json`

边界要求：
- 只读取和修改当前执行目录中的文件。
- 不要修改 skill、脚本、仓库源码、父目录或其他 case 目录。
- 所有文件读写都使用 UTF-8。
- 不要批量处理其他 case，不要创建子任务，不要解释批处理流程。

生成要求：
- 使用 `$harmony-card-generation-datamodel-first` 的规则和当前仓库中的 skill 参考，生成同一张卡片对应的 DSL 与 CardSpec。
- 根据 `TaskSpec.md` 生成 `task.taskSpec.json`，必须使用 `dataModelSchema`，不要使用旧的 `dataModel.value`。
- `dataModelSchema` 中被 DSL 动态绑定使用的字段节点必须包含 `type`、`description`、`sampleValue`。
- `eventCandidates` 只描述候选事件能力，不能写成 DSL `onClick`、按钮文案、入口文案或布局指令。
- `assetCandidates` 只描述素材候选白名单，必须包含 `src` 和非空 `description`；如包含 `bindTo`，必须能从 `dataModelSchema` 推导到同一个 `src`。
- DSL 中实际使用的 `onClick` 只能来自 `task.taskSpec.json` 的 `eventCandidates`。
- DSL 中实际使用的 `Image.src` 和 `styles.backgroundImage` 只能来自 `task.taskSpec.json` 的 `assetCandidates`，或用户明确提供的本地资源路径。
- 如果使用 Image 或 backgroundImage，优先使用 skill 中 `reference/design/asset-library.md` 声明的 allowlist 素材，不要为了通过引用校验而虚构资源路径。

DSL 要求：
- `card.dsl.jsonl` 必须恰好 3 行非空 JSONL：`createSurface`、`updateComponents`、`updateDataModel`。
- 所有动态绑定必须使用完整 `{{{{ ... }}}}` 表达式读取 DataModel；不要使用 `{{"path":"/..."}}` 或 `formatString` 作为值绑定。
- DSL 中所有动态绑定路径必须能从 `task.taskSpec.json` 的 `dataModelSchema`、最终 CardSpec、能力 `outputSchema` 或微服务允许的展示字段中推导。
- 第三行 `updateDataModel.value` 只能包含 DSL 所需的受控静态辅助字段、加载态或空态字段；不要在动态数据能力输出路径下新增未授权字段。
- 将 `dataModelSchema.sampleValue` 填入最终 `updateDataModel`，作为可直接渲染的样例数据。
- 暂时禁止使用模板循环 children 对象，也就是不要写 `children: {{{{"componentId":"...","path":"/..."}}}}`；数组内容必须改用显式固定组件和显式索引路径绑定。
- 如需展示会议、日程、天气、待办等少量重复内容，使用固定 Text/Row 组件并绑定显式索引路径；空间不足时只展示第一条或摘要，不使用 List/Row/Column 模板循环。
- 避免组件重叠、文字被按钮或容器裁切、受保护文本显示不全、无意义空白过大。特别检查按钮文字高度和宽度，按钮文案估算宽度必须至少保留 16vp 水平内边距余量。
- 手算 Row/Column 宽高预算：子项宽高 + margin + padding + itemMargin 不得超过父容器。

CardSpec 要求：
- `card.cardspec.json` 必须包含 skill 校验器要求的 `title`、`description` 等必要字段，不要只输出 `suggestSize`。
- 动态卡片的 `dataBindings` 必须来自已声明的数据能力，并与 DSL 实际绑定路径、TaskSpec 数据契约保持一致。

完成前必须运行以下两个校验命令，命令从当前 case 目录执行：

```powershell
python "{taskspec_refs_validator}" --taskspec "task.taskSpec.json" --dsl "card.dsl.jsonl" --format json
python "{card_validator}" --dsl "card.dsl.jsonl" --cardspec "card.cardspec.json" --format json
```

通过标准：
- 第一个校验器必须返回 `valid: true`。
- 第二个校验器必须返回 `status: polished`、`errorCount: 0`、`warningCount: 0`，且 `qualityScore >= {min_quality_score}`。
- 如果任一命令失败、返回 invalid、出现 error/warning，或 `qualityScore < {min_quality_score}`，必须修复 `task.taskSpec.json`、`card.dsl.jsonl` 或 `card.cardspec.json` 后重新运行两个命令，直到通过。

最终回复只需简短说明完成情况，不要输出长篇解释或中间过程。
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
    action: str
    error: str = ""


@dataclass
class ValidationResult:
    ok: bool
    returncode: int | None
    error: str = ""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    line = f"[{now()}] {message}"
    print(line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"), flush=True)
    if LOG_PATH is not None:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


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


def write_case_inputs(
    case: CaseItem,
    case_dir: Path,
    taskspec_path: Path,
    taskspec_refs_validator: Path,
    card_validator: Path,
    min_quality_score: int,
    force: bool,
    debug: bool,
) -> str:
    log(f"PREP  line={case.line_no} case={case.directory_name} mkdir={case_dir}")
    case_dir.mkdir(parents=True, exist_ok=True)
    files_to_create = [
        case_dir / "query.txt",
        case_dir / "TaskSpec.md",
    ]
    if not force:
        existing_outputs = [case_dir / name for name in REQUIRED_OUTPUTS if (case_dir / name).exists()]
        if existing_outputs:
            names = ", ".join(path.name for path in existing_outputs)
            raise FileExistsError(f"{case_dir} already contains output file(s): {names}; use --force to rerun")

    log(f"PREP  line={case.line_no} case={case.directory_name} write=query.txt")
    (case_dir / "query.txt").write_text(case.query + "\n", encoding="utf-8")
    if debug:
        log(f"PREP  line={case.line_no} case={case.directory_name} write=case.json")
        (case_dir / "case.json").write_text(
            json.dumps(case.payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    log(f"PREP  line={case.line_no} case={case.directory_name} copy=TaskSpec.md")
    shutil.copyfile(taskspec_path, case_dir / "TaskSpec.md")
    prompt_text = PROMPT_TEMPLATE.format(
        case_json=json.dumps(case.payload, ensure_ascii=False, indent=2),
        taskspec_refs_validator=str(taskspec_refs_validator),
        card_validator=str(card_validator),
        min_quality_score=min_quality_score,
    )

    for path in files_to_create:
        if not path.exists():
            raise RuntimeError(f"failed to prepare {path}")
    log(f"PREP  line={case.line_no} case={case.directory_name} done")
    return prompt_text


def build_codex_command(args: argparse.Namespace, case_dir: Path, prompt_path: Path, output_path: Path) -> list[str]:
    command = [
        args.codex_bin,
        "--ask-for-approval",
        args.approval,
        "exec",
        "--cd",
        str(case_dir),
        "--sandbox",
        args.sandbox,
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
    ]
    if args.dangerously_bypass_approvals_and_sandbox:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    if args.ephemeral:
        command.append("--ephemeral")
    if args.model:
        command.extend(["--model", args.model])
    if args.profile:
        command.extend(["--profile", args.profile])
    command.append("-")
    return command


async def pipe_stream(prefix: str, stream: asyncio.StreamReader, log_path: Path | None, echo: bool) -> None:
    handle = log_path.open("ab") if log_path is not None else None
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            if handle is not None:
                handle.write(line)
                handle.flush()
            text = line.decode("utf-8", errors="replace").rstrip()
            if echo and text:
                log(f"{prefix} {text}")
    finally:
        if handle is not None:
            handle.close()


async def run_json_command(
    command: list[str],
    cwd: Path,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
) -> tuple[int, str, str]:
    process = await asyncio.wait_for(
        asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        ),
        timeout=30,
    )
    stdout, stderr = await process.communicate()
    if stdout_path is not None:
        stdout_path.write_bytes(stdout)
    if stderr_path is not None:
        stderr_path.write_bytes(stderr)
    return process.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


def _contains_template_children(value: object) -> bool:
    if isinstance(value, dict):
        children = value.get("children")
        if isinstance(children, dict) and {"componentId", "path"}.issubset(children.keys()):
            return True
        return any(_contains_template_children(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_template_children(child) for child in value)
    return False


def has_validated_outputs(case_dir: Path) -> bool:
    return all((case_dir / name).is_file() for name in VALIDATED_OUTPUTS)


def verify_validation_inputs(case_dir: Path) -> tuple[bool, str]:
    missing = [name for name in VALIDATED_OUTPUTS if not (case_dir / name).is_file()]
    if missing:
        return False, "missing validation input file(s): " + ", ".join(missing)
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
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            return False, f"card.dsl.jsonl line {index} is not valid JSON: {exc}"
        if _contains_template_children(value):
            return False, "card.dsl.jsonl uses forbidden template children object; use explicit indexed bindings instead"
    return True, ""


def verify_outputs(case_dir: Path) -> tuple[bool, str]:
    missing = [name for name in REQUIRED_OUTPUTS if not (case_dir / name).is_file()]
    if missing:
        return False, "missing output file(s): " + ", ".join(missing)
    return verify_validation_inputs(case_dir)


def validate_taskspec_refs_report(returncode: int, stdout: str, stderr: str) -> tuple[bool, str]:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return False, f"TaskSpec/DSL refs validator did not return valid JSON: {exc}; stderr={stderr.strip()}"
    if returncode != 0:
        errors = report.get("errors")
        return False, "TaskSpec/DSL refs validator failed: " + json.dumps(errors, ensure_ascii=False)
    if report.get("valid") is not True:
        errors = report.get("errors")
        return False, "TaskSpec/DSL refs validator returned valid=false: " + json.dumps(errors, ensure_ascii=False)
    return True, ""


def validate_card_report(returncode: int, stdout: str, stderr: str, min_quality_score: int) -> tuple[bool, str]:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return False, f"card validator did not return valid JSON: {exc}; stderr={stderr.strip()}"

    status = report.get("status")
    error_count = int(report.get("errorCount") or 0)
    warning_count = int(report.get("warningCount") or 0)
    quality_score = int(report.get("qualityScore") or 0)
    diagnostics = report.get("diagnostics")
    if returncode != 0 or status == "invalid" or error_count > 0:
        return False, "card validator failed: " + json.dumps(diagnostics, ensure_ascii=False)
    if status != "polished" or warning_count > 0 or quality_score < min_quality_score:
        return False, (
            "card validator has quality risks: "
            f"status={status} warnings={warning_count} qualityScore={quality_score} "
            f"diagnostics={json.dumps(diagnostics, ensure_ascii=False)}"
        )
    return True, ""


async def validate_existing_case(case_dir: Path, args: argparse.Namespace) -> ValidationResult:
    ok, error = verify_validation_inputs(case_dir)
    if not ok:
        return ValidationResult(False, None, error)

    refs_command = [
        sys.executable,
        str(args.taskspec_refs_validator),
        "--taskspec",
        str(case_dir / "task.taskSpec.json"),
        "--dsl",
        str(case_dir / "card.dsl.jsonl"),
        "--format",
        "json",
    ]
    card_command = [
        sys.executable,
        str(args.card_validator),
        "--dsl",
        str(case_dir / "card.dsl.jsonl"),
        "--cardspec",
        str(case_dir / "card.cardspec.json"),
        "--format",
        "json",
    ]
    try:
        log(f"VALIDATE case={case_dir.name} refs=start")
        refs_returncode, refs_stdout, refs_stderr = await run_json_command(
            refs_command,
            case_dir,
            case_dir / "validate.taskspec_dsl_refs.stdout.json" if args.debug else None,
            case_dir / "validate.taskspec_dsl_refs.stderr.log" if args.debug else None,
        )
        refs_ok, refs_error = validate_taskspec_refs_report(refs_returncode, refs_stdout, refs_stderr)
        if not refs_ok:
            log(f"VALIDATE case={case_dir.name} refs=fail returncode={refs_returncode} error={refs_error}")
            return ValidationResult(False, refs_returncode, refs_error)
        log(f"VALIDATE case={case_dir.name} refs=pass")

        log(f"VALIDATE case={case_dir.name} card=start")
        card_returncode, card_stdout, card_stderr = await run_json_command(
            card_command,
            case_dir,
            case_dir / "validate.card.stdout.json" if args.debug else None,
            case_dir / "validate.card.stderr.log" if args.debug else None,
        )
        card_ok, card_error = validate_card_report(card_returncode, card_stdout, card_stderr, args.min_quality_score)
        if not card_ok:
            log(f"VALIDATE case={case_dir.name} card=fail returncode={card_returncode} error={card_error}")
            return ValidationResult(False, card_returncode, card_error)
        log(f"VALIDATE case={case_dir.name} card=pass")
    except FileNotFoundError as exc:
        return ValidationResult(False, None, str(exc))

    return ValidationResult(True, 0)


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
        if has_validated_outputs(case_dir) and not args.force:
            validation = await validate_existing_case(case_dir, args)
            if validation.ok:
                elapsed = time.perf_counter() - started
                log(f"SKIP  line={case.line_no} case={case.directory_name} validation=passed elapsed={elapsed:.1f}s")
                return CaseResult(case, True, 0, elapsed, case_dir, "skipped")
            log(f"RERUN line={case.line_no} case={case.directory_name} validation_failed={validation.error}")

        try:
            prompt_text = write_case_inputs(
                case,
                case_dir,
                taskspec_path,
                args.taskspec_refs_validator,
                args.card_validator,
                args.min_quality_score,
                args.force or has_validated_outputs(case_dir),
                args.debug,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            log(f"FAIL  line={case.line_no} case={case.directory_name} prepare_error={exc}")
            return CaseResult(case, False, None, elapsed, case_dir, "failed", str(exc))

        prompt_path = case_dir / "prompt.txt"
        final_message_path = case_dir / "codex.final.md"
        stdout_path = case_dir / "codex.stdout.log" if args.debug else None
        stderr_path = case_dir / "codex.stderr.log" if args.debug else None
        if args.debug:
            log(f"PREP  line={case.line_no} case={case.directory_name} write=prompt.txt")
            prompt_path.write_text(prompt_text, encoding="utf-8")
        command = build_codex_command(args, case_dir, prompt_path, final_message_path)
        log(f"CODEX line={case.line_no} case={case.directory_name} command={' '.join(command)}")
        log(f"CODEX line={case.line_no} case={case.directory_name} prompt=memory bytes={len(prompt_text.encode('utf-8'))}")

        if args.dry_run:
            elapsed = time.perf_counter() - started
            log(f"DRY   line={case.line_no} case={case.directory_name} command={' '.join(command)}")
            return CaseResult(case, True, 0, elapsed, case_dir, "dry-run")

        process: asyncio.subprocess.Process | None = None
        stdout_task: asyncio.Task[None] | None = None
        stderr_task: asyncio.Task[None] | None = None
        try:
            log(f"CODEX line={case.line_no} case={case.directory_name} start")
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(case_dir),
                ),
                timeout=args.startup_timeout,
            )
            log(f"CODEX line={case.line_no} case={case.directory_name} pid={process.pid} send_prompt_bytes={len(prompt_text.encode('utf-8'))}")
            assert process.stdin is not None
            stdout_task = asyncio.create_task(pipe_stream(f"[{case.directory_name}][stdout]", process.stdout, stdout_path, args.echo_codex_streams))
            stderr_task = asyncio.create_task(pipe_stream(f"[{case.directory_name}][stderr]", process.stderr, stderr_path, args.echo_codex_streams))
            process.stdin.write(prompt_text.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
            log(f"CODEX line={case.line_no} case={case.directory_name} prompt_sent wait")

            try:
                returncode = await asyncio.wait_for(process.wait(), timeout=args.timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                await asyncio.gather(stdout_task, stderr_task)
                returncode = process.returncode
                elapsed = time.perf_counter() - started
                log(f"TIMEOUT line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s")
                return CaseResult(case, False, returncode, elapsed, case_dir, "failed", f"timeout after {args.timeout}s")
            await asyncio.gather(stdout_task, stderr_task)
            log(f"CODEX line={case.line_no} case={case.directory_name} exit={returncode}")
        except FileNotFoundError as exc:
            elapsed = time.perf_counter() - started
            log(f"FAIL  line={case.line_no} case={case.directory_name} codex not found: {args.codex_bin}")
            return CaseResult(case, False, None, elapsed, case_dir, "failed", str(exc))
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - started
            error = f"codex process did not start within {args.startup_timeout}s"
            log(f"FAIL  line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s error={error}")
            return CaseResult(case, False, None, elapsed, case_dir, "failed", error)
        except (BrokenPipeError, ConnectionError, OSError, RuntimeError) as exc:
            if process is not None:
                try:
                    if process.returncode is None:
                        process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
            tasks = [task for task in (stdout_task, stderr_task) if task is not None]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.perf_counter() - started
            returncode = process.returncode if process is not None else None
            error = f"codex process I/O failed: {exc}"
            log(f"FAIL  line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s returncode={returncode} error={error}")
            return CaseResult(case, False, returncode, elapsed, case_dir, "failed", error)

        ok, error = verify_outputs(case_dir)
        if returncode == 0 and ok:
            log(f"CHECK line={case.line_no} case={case.directory_name} dispatcher_validation=start")
            validation = await validate_existing_case(case_dir, args)
            elapsed = time.perf_counter() - started
            if validation.ok:
                log(f"DONE  line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s")
                return CaseResult(case, True, returncode, elapsed, case_dir, "generated")
            error = validation.error
        else:
            elapsed = time.perf_counter() - started

        if returncode != 0 and not error:
            error = f"codex exited with code {returncode}"
        elif returncode != 0:
            error = f"codex exited with code {returncode}; {error}"
        log(f"FAIL  line={case.line_no} case={case.directory_name} elapsed={elapsed:.1f}s error={error}")
        return CaseResult(case, False, returncode, elapsed, case_dir, "failed", error)


def write_summary(output_dir: Path, results: list[CaseResult]) -> None:
    summary = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "ok": sum(1 for result in results if result.ok),
        "skipped": sum(1 for result in results if result.action == "skipped"),
        "generated": sum(1 for result in results if result.action == "generated"),
        "failed": sum(1 for result in results if not result.ok),
        "results": [
            {
                "line": result.case.line_no,
                "scenario": result.case.scenario,
                "case": result.case.directory_name,
                "ok": result.ok,
                "action": result.action,
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
    parser.add_argument(
        "--dangerously-bypass-approvals-and-sandbox",
        action="store_true",
        help="Pass Codex CLI's dangerous no-sandbox/no-approval option to each subprocess.",
    )
    parser.add_argument("--timeout", type=int, default=1800, help="Per-case timeout in seconds. Default: 1800.")
    parser.add_argument("--startup-timeout", type=int, default=60, help="Timeout for starting each Codex process, in seconds. Default: 60.")
    parser.add_argument("--echo-codex-streams", action="store_true", help="Also echo each Codex subprocess stdout/stderr line into the batch log.")
    parser.add_argument("--task-spec", type=Path, default=Path("TaskSpec.md"), help="TaskSpec.md path copied into each case dir.")
    parser.add_argument(
        "--taskspec-refs-validator",
        type=Path,
        default=DEFAULT_TASKSPEC_REFS_VALIDATOR,
        help=f"TaskSpec/DSL reference validator. Default: {DEFAULT_TASKSPEC_REFS_VALIDATOR}.",
    )
    parser.add_argument(
        "--card-validator",
        type=Path,
        default=DEFAULT_CARD_VALIDATOR,
        help=f"Skill card validator. Default: {DEFAULT_CARD_VALIDATOR}.",
    )
    parser.add_argument(
        "--min-quality-score",
        type=int,
        default=70,
        help="Minimum acceptable validate_card.py qualityScore for skipping or accepting generated output. Default: 70.",
    )
    parser.add_argument("--force", action="store_true", help="Allow rerunning into a case dir that already has output files.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare inputs and print commands without running Codex.")
    parser.add_argument("--debug", action="store_true", help="Keep per-case debug files: case.json, prompt.txt, codex stdout/stderr logs, and validator outputs.")
    parser.add_argument("--ephemeral", action="store_true", help="Pass `--ephemeral` to codex exec.")
    return parser.parse_args(argv)


async def async_main(args: argparse.Namespace) -> int:
    global LOG_PATH
    if args.jobs < 1:
        raise ValueError("--jobs must be >= 1")
    args.limit = None if args.limit == 0 else args.limit

    jsonl_path = args.jsonl.resolve()
    output_dir = args.output_dir.resolve()
    taskspec_path = args.task_spec.resolve()
    args.taskspec_refs_validator = args.taskspec_refs_validator.resolve()
    args.card_validator = args.card_validator.resolve()
    if not jsonl_path.is_file():
        raise FileNotFoundError(f"input JSONL not found: {jsonl_path}")
    if not taskspec_path.is_file():
        raise FileNotFoundError(f"TaskSpec file not found: {taskspec_path}")
    if not args.taskspec_refs_validator.is_file():
        raise FileNotFoundError(f"TaskSpec/DSL refs validator not found: {args.taskspec_refs_validator}")
    if not args.card_validator.is_file():
        raise FileNotFoundError(f"card validator not found: {args.card_validator}")

    output_dir.mkdir(parents=True, exist_ok=True)
    LOG_PATH = output_dir / "codex_batch.log"
    LOG_PATH.write_text("", encoding="utf-8")
    cases = load_cases(jsonl_path)
    selected = select_cases(cases, start=args.start, end=args.end, limit=args.limit)
    if not selected:
        log("No cases selected.")
        return 0

    log(
        "Batch start "
        f"input={jsonl_path} output={output_dir} cases={len(selected)} "
        f"jobs={args.jobs} range={args.start or 1}-{args.end or 'EOF'} "
        f"limit={args.limit or 'none'} minQualityScore={args.min_quality_score}"
    )
    semaphore = asyncio.Semaphore(args.jobs)
    results = await asyncio.gather(
        *(run_case(case, args, output_dir, taskspec_path, semaphore) for case in selected)
    )
    write_summary(output_dir, list(results))

    ok_count = sum(1 for result in results if result.ok)
    skip_count = sum(1 for result in results if result.action == "skipped")
    generated_count = sum(1 for result in results if result.action == "generated")
    fail_count = len(results) - ok_count
    log(
        f"Batch finished total={len(results)} ok={ok_count} skipped={skip_count} "
        f"generated={generated_count} failed={fail_count} summary={output_dir / 'codex_batch_summary.json'}"
    )
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
