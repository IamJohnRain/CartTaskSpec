# -*- coding: utf-8 -*-
"""口语化版合并:30 场景 → 5000 条。
- 复用原版 normalize() 与原 10000Cases.txt 强去重(完全独立)
- 按场景配额(原 0.489 比例)选满
- 覆盖度校验
- 输出 5000Cases.txt + 报告
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_10K = HERE.parent / "cases-10k"
sys.path.insert(0, str(CASES_10K))
from coverage import MIN_QUOTA, AXES, axis_values  # noqa: E402
from scenarios_def import SCENARIOS  # noqa: E402

SCENARIOS_DIR = HERE / "scenarios"
ORIG_10000 = CASES_10K / "10000Cases.txt"
OUT_TXT = HERE / "5000Cases.txt"
OUT_JSONL = HERE / "5000Cases.tagged.jsonl"
OUT_MD = HERE / "coverage_report.md"
OUT_JSON = HERE / "coverage_stats.json"
TARGET_TOTAL = 5000

# 比例 5000/10220 ≈ 0.4892
ORAL_QUOTA = {s["id"]: round(s["quota"] * 5000 / 10220) for s in SCENARIOS}
# 调整总到 5000
total = sum(ORAL_QUOTA.values())
delta = TARGET_TOTAL - total
# 均匀加减
keys = sorted(ORAL_QUOTA)
i = 0
while delta != 0:
    k = keys[i % len(keys)]
    if delta > 0:
        ORAL_QUOTA[k] += 1
        delta -= 1
    elif ORAL_QUOTA[k] > 0:
        ORAL_QUOTA[k] -= 1
        delta += 1
    i += 1


def normalize(s):
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[，。！？、；:：,.!?;:()「」【】\[\]'\"]+", "", s)
    return s


def load_original_set():
    """读原 10000Cases.txt 的归一化 set。"""
    seen = set()
    for line in ORIG_10000.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            seen.add(normalize(s))
    return seen


def load_oral():
    """读 30 个 oral 场景文件。"""
    recs = []
    for sid_dir in sorted(SCENARIOS_DIR.iterdir()):
        if not sid_dir.is_dir():
            continue
        f = sid_dir / "cases.jsonl"
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def exact_dedup(records):
    seen = set()
    out, dup = [], 0
    for r in records:
        key = (r.get("scenario", ""), normalize(r["query"]))
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        out.append(r)
    return out, dup


def dedup_against_original(records, orig_set):
    """剔除与原 10000 集 normalize 重复的。"""
    out, removed = [], 0
    for r in records:
        if normalize(r["query"]) in orig_set:
            removed += 1
            continue
        out.append(r)
    return out, removed


def quota_select(records):
    """按场景配额选满,稀有度优先。"""
    by_scn = defaultdict(list)
    for r in records:
        by_scn[r.get("scenario", "")].append(r)

    # 全局轴值计数(用于稀有度)
    gc = Counter()
    for r in records:
        for ax, v in (r.get("axes") or {}).items():
            gc[(ax, v)] += 1

    def rarity(r):
        ax = r.get("axes") or {}
        return sum(1.0 / gc.get((a, v), 1) for a, v in ax.items())

    for sid, lst in by_scn.items():
        lst.sort(key=rarity, reverse=True)

    selected = []
    for sid, q in ORAL_QUOTA.items():
        lst = by_scn.get(sid, [])
        selected.extend(lst[:q])

    # 超出 TARGET 时按稀有度裁
    if len(selected) > TARGET_TOTAL:
        over = len(selected) - TARGET_TOTAL
        per_scn = Counter(r.get("scenario", "") for r in selected)
        candidates = []
        for r in selected:
            sid = r.get("scenario", "")
            if per_scn[sid] >= ORAL_QUOTA.get(sid, 0):
                candidates.append(r)
        candidates.sort(key=rarity)  # 稀有度低的先裁
        drop_ids = {id(r) for r in candidates[:over]}
        selected = [r for r in selected if id(r) not in drop_ids]
    return selected


def coverage_stats(records):
    stats = {}
    for ax in AXES:
        c = Counter()
        for r in records:
            v = (r.get("axes") or {}).get(ax)
            if v is not None:
                c[v] += 1
        stats[ax] = dict(c)
    return stats


def check_min(stats):
    out = []
    for ax, floor in MIN_QUOTA.items():
        actual = stats.get(ax, {})
        for v, q in floor.items():
            a = actual.get(v, 0)
            if a < q:
                out.append((ax, v, a, q, q - a))
    return out


def main():
    print("[1/5] 加载原 10000 集去重表...")
    orig_set = load_original_set()
    print(f"  原集: {len(orig_set)} 条 normalize")

    print("[2/5] 加载 30 个口语化场景...")
    raw = load_oral()
    print(f"  原始: {len(raw)} 条")

    print("[3/5] 精确去重(同场景内)...")
    dedup1, d1 = exact_dedup(raw)
    print(f"  去重后: {len(dedup1)} (移除 {d1})")

    print("[4/5] 与原 10000 集去重...")
    dedup2, d2 = dedup_against_original(dedup1, orig_set)
    print(f"  去重后: {len(dedup2)} (移除 {d2})")

    print("[5/5] 配额选择...")
    final = quota_select(dedup2)
    print(f"  最终: {len(final)} (目标 {TARGET_TOTAL})")

    stats = coverage_stats(final)
    short = check_min(stats)

    # 写出
    with OUT_TXT.open("w", encoding="utf-8") as f:
        for r in final:
            f.write(r["query"].strip() + "\n")
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in final:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    OUT_JSON.write_text(json.dumps({
        "total": len(final),
        "raw": len(raw),
        "exact_dups_removed": d1,
        "overlap_with_original_removed": d2,
        "stats": stats,
        "min_quotas": MIN_QUOTA,
        "shortfalls": [
            {"axis": a, "value": v, "actual": ac, "floor": fl, "short": sh}
            for (a, v, ac, fl, sh) in short
        ],
        "oral_quota": ORAL_QUOTA,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # markdown 报告
    lines = ["# 口语化版 A2UI Query 数据生产覆盖度报告\n"]
    lines.append(f"- **最终条数**: {len(final)}")
    lines.append(f"- **原始产出**: {len(raw)}")
    lines.append(f"- **精确去重移除**: {d1}")
    lines.append(f"- **与原 10000 集去重移除**: {d2}")
    lines.append(f"- **场景数**: {len(SCENARIOS)}")
    lines.append("")
    lines.append("## 1. 各场景配额\n")
    lines.append("| 场景 ID | 名称 | 配额 | 入选 |")
    lines.append("|---|---|---|---|")
    per_scn = Counter(r.get("scenario", "") for r in final)
    for s in SCENARIOS:
        sid = s["id"]
        sel = per_scn.get(sid, 0)
        q = ORAL_QUOTA.get(sid, 0)
        ok = "[OK]" if sel >= q else "[WARN]"
        lines.append(f"| {sid} | {s['name']} | {q} | {sel} | {ok} |")
    lines.append("")
    lines.append("## 2. 12 轴覆盖度\n")
    lines.append("| 轴 | 枚举值 | 原 10000 配额 | 实际 | 状态 |")
    lines.append("|---|---|---|---|---|")
    for ax in AXES:
        floor = MIN_QUOTA[ax]
        actual = stats.get(ax, {})
        for v, fq in sorted(floor.items(), key=lambda x: -x[1]):
            ac = actual.get(v, 0)
            ok = "[OK]" if ac >= fq else f"[WARN] 缺 {fq - ac}"
            lines.append(f"| {ax} | {v} | {fq} | {ac} | {ok} |")
    lines.append("")
    if short:
        lines.append("## 3. 未达标轴值\n")
        for ax, v, ac, fl, sh in short:
            lines.append(f"- **{ax}={v}**: 实际 {ac} < 配额 {fl} (缺 {sh})")
        lines.append("\n注:口语化版 5000 条样本量约原 10000 的一半,部分轴配额未达是预期,实际训练/测试可与原集合并补足。")
    else:
        lines.append("## 3. 覆盖度\n\n所有轴值均达到配额下限。")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n[OK] 5000Cases.txt: {len(final)} 条")
    print(f"[OK] coverage_report.md / coverage_stats.json 已写出")
    if short:
        print(f"[INFO] {len(short)} 个轴值未达原 10000 配额(预期,样本量减半)")


if __name__ == "__main__":
    raise SystemExit(main())
