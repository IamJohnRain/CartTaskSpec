"""把 smoke 样本从 3 个扩到 9 个(3 场景 × 3 case),做完整 stratified_split dry-run。"""
import json
import shutil
from pathlib import Path

ROOT = Path("D:/A2UI/CartTaskSpec")
TAGGED = ROOT / "datasets/cases-10k/10000Cases.tagged.jsonl"
EXAMPLES = ROOT / "examples"
OUT_BASE = ROOT / "datasets/Scenario/cases-10k-gpt-5.5"


def pick_records():
    """每个场景取 3 条 record。"""
    by_scn = {}
    with TAGGED.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            sid = r["scenario"]
            by_scn.setdefault(sid, []).append(r)
    # 取前 3 个场景,每场景 3 条
    out = []
    for sid in sorted(by_scn)[:3]:
        out.extend(by_scn[sid][:3])
    return out


def main():
    picked = pick_records()
    by_scn = {}
    for r in picked:
        by_scn.setdefault(r["scenario"], []).append(r)
    print(f"将创建 {sum(len(v) for v in by_scn.values())} 个 case,")
    print(f"覆盖 {len(by_scn)} 个场景: {list(by_scn)}")

    if OUT_BASE.exists():
        shutil.rmtree(OUT_BASE)
    OUT_BASE.mkdir(parents=True)

    example_files = [EXAMPLES / "parent-care.taskspec.json",
                     EXAMPLES / "freeclip2-earbuds.taskspec.json"]
    for sid, recs in by_scn.items():
        for i, r in enumerate(recs, 1):
            case_dir = OUT_BASE / sid / f"Case-{i:03d}"
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "query.txt").write_text(r["query"], encoding="utf-8")
            ex = example_files[(i - 1) % len(example_files)]
            shutil.copy2(ex, case_dir / "task.taskSpec.json")
            (case_dir / "card.dsl.jsonl").write_text("", encoding="utf-8")
    print(f"\n[OK] fixtures 就绪: {OUT_BASE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
