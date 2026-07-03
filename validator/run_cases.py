from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from validator import engine
from validator.cli import _collect_token_colors
from validator.context import CardContext
from validator.loader import load_genui


def _run(jsonl_path: Path) -> list[dict]:
    token_colors, token_source = _collect_token_colors()
    messages = load_genui(jsonl_path)
    ctx = CardContext.from_messages(messages, token_colors=token_colors, token_color_source=token_source)
    report = engine.run(ctx, disabled_ids=set())
    return [v.to_dict() for v in report.violations]


def _check(rule_id: str, rule_dir: Path, results: list[tuple[str, bool, str]]) -> None:
    expected_path = rule_dir / "expected.json"
    fail_path = rule_dir / "fail.jsonl"
    pass_path = rule_dir / "pass.jsonl"
    if not expected_path.exists():
        results.append((rule_id, False, "missing expected.json"))
        return
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    target = expected.get("rule_id")
    should_fire_fail = expected.get("should_fire_on_fail", True)
    should_fire_pass = expected.get("should_fire_on_pass", False)

    if fail_path.exists():
        violations = _run(fail_path)
        fired = any(v["rule_id"] == target for v in violations)
        if fired == should_fire_fail:
            results.append((rule_id, True, f"fail.jsonl: {target} fired={fired} (expected {should_fire_fail})"))
        else:
            msg = (
                f"fail.jsonl: expected {target} fired={should_fire_fail}, got {fired}. "
                f"actual: {[v['rule_id'] for v in violations]}"
            )
            results.append((rule_id, False, msg))
    else:
        results.append((rule_id, False, "missing fail.jsonl"))

    if pass_path.exists():
        violations = _run(pass_path)
        fired = any(v["rule_id"] == target for v in violations)
        if fired == should_fire_pass:
            results.append((rule_id, True, f"pass.jsonl: {target} fired={fired} (expected {should_fire_pass})"))
        else:
            msg = (
                f"pass.jsonl: expected {target} fired={should_fire_pass}, got {fired}. "
                f"actual: {[v['rule_id'] for v in violations]}"
            )
            results.append((rule_id, False, msg))
    else:
        results.append((rule_id, False, "missing pass.jsonl"))


def main() -> int:
    engine.discover_rules()
    cases_root = ROOT / "cases"
    if not cases_root.exists():
        print(f"cases dir not found: {cases_root}")
        return 2
    results: list[tuple[str, bool, str]] = []
    for rule_dir in sorted(cases_root.iterdir()):
        if not rule_dir.is_dir():
            continue
        _check(rule_dir.name, rule_dir, results)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    by_rule: dict[str, list[tuple[bool, str]]] = {}
    for rid, ok, msg in results:
        by_rule.setdefault(rid, []).append((ok, msg))
    for rid in sorted(by_rule):
        msgs = by_rule[rid]
        ok_all = all(ok for ok, _ in msgs)
        marker = "OK" if ok_all else "FAIL"
        print(f"[{marker}] {rid}")
        for ok, msg in msgs:
            print(f"    {'+' if ok else '!'} {msg}")
    print()
    print(f"summary: {passed} assertions passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
