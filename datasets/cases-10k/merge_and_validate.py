# -*- coding: utf-8 -*-
"""合并、去重、覆盖度校验,输出 10000Cases.txt + 覆盖度报告。"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from coverage import MIN_QUOTA, AXES, axis_values  # noqa: E402
from scenarios_def import SCENARIOS, scenario_by_id  # noqa: E402

SCENARIOS_DIR = HERE / "scenarios"
OUT_TXT = HERE / "10000Cases.txt"
OUT_JSONL = HERE / "10000Cases.tagged.jsonl"
OUT_MD = HERE / "coverage_report.md"
OUT_JSON = HERE / "coverage_stats.json"
TARGET_TOTAL = 10000


def load_all():
    """读全部 scenarios/<id>/cases.jsonl -> list[dict]。"""
    recs = []
    for f in sorted(SCENARIOS_DIR.glob("*/cases.jsonl")):
        sid = f.parent.name
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if "query" in r:
                    recs.append(r)
            except json.JSONDecodeError:
                continue
    return recs


def normalize(s):
    """规范化做精确去重:去空白、标点、全角符号。"""
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[，。！？、；:：,.!?;:()「」【】\[\]'\"]+", "", s)
    return s


def exact_dedup(records):
    """精确去重:同 scenario + 规范化 query 相同则只留第一条。"""
    seen = set()
    out = []
    dup = 0
    for r in records:
        key = (r.get("scenario", ""), normalize(r["query"]))
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        out.append(r)
    return out, dup


def ngram_jaccard(a, b, n=4):
    sa = {a[i:i + n] for i in range(len(a) - n + 1)}
    sb = {b[i:i + n] for i in range(len(b) - n + 1)}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def near_dedup(records, threshold=0.85, sample_per_scenario=2000):
    """4-gram Jaccard 近重复:每场景内两两比较,超过阈值视为重复。
    为效率只抽样 2000 条/场景。"""
    by_scn = defaultdict(list)
    for r in records:
        by_scn[r.get("scenario", "")].append(r)
    drop = set()
    for sid, lst in by_scn.items():
        if len(lst) > sample_per_scenario:
            # 大场景抽样
            import random
            sample = random.sample(lst, sample_per_scenario)
        else:
            sample = lst
        # 按 query 长度分桶,只在相邻桶比较
        sample.sort(key=lambda r: len(r["query"]))
        kept = []
        for r in sample:
            q = r["query"]
            is_dup = False
            for kr in kept:
                if abs(len(kr["query"]) - len(q)) > 60:
                    continue
                if ngram_jaccard(kr["query"], q) >= threshold:
                    is_dup = True
                    break
            if is_dup:
                drop.add(id(r))
            else:
                kept.append(r)
    return [r for r in records if id(r) not in drop]


def quota_select(records, target_total=TARGET_TOTAL):
    """按场景配额选择,优先保留更「稀有」轴值的记录。
    若总配额 < target,全留;> target,从超大场景按稀有度裁剪。"""
    quota = {s["id"]: s["quota"] for s in SCENARIOS}
    by_scn = defaultdict(list)
    for r in records:
        by_scn[r.get("scenario", "")].append(r)

    # 稀有度评分:对每条记录,计算其轴值在全局的稀缺度
    global_axis_counter = Counter()
    for r in records:
        for ax, v in (r.get("axes") or {}).items():
            global_axis_counter[(ax, v)] += 1
    N = len(records) or 1

    def rarity(r):
        axes = r.get("axes") or {}
        s = 0.0
        for ax, v in axes.items():
            cnt = global_axis_counter.get((ax, v), 1)
            s += 1.0 / cnt  # 越稀有值越大
        return s

    # 计算全球比例下「理想」覆盖目标(用于排序)
    for sid, lst in by_scn.items():
        lst.sort(key=rarity, reverse=True)

    selected = []
    overflow = 0
    for sid, q in quota.items():
        lst = by_scn.get(sid, [])
        if len(lst) <= q:
            selected.extend(lst)
        else:
            selected.extend(lst[:q])
            overflow += len(lst) - q

    # 如果 selected > target_total,从超出配额场景按稀有度升序裁掉尾部
    if len(selected) > target_total:
        over = len(selected) - target_total
        per_scn = Counter(r.get("scenario", "") for r in selected)
        # 收集「本场景已收满或超量」的记录
        candidates = []
        for r in selected:
            sid = r.get("scenario", "")
            if per_scn[sid] >= quota.get(sid, 0):
                candidates.append(r)
        candidates.sort(key=rarity)  # 稀有的保,优先删"常见轴值"
        drop_ids = {id(r) for r in candidates[:over]}
        selected = [r for r in selected if id(r) not in drop_ids]

    return selected


def coverage_stats(records):
    """计算各轴值的命中数。"""
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
    """对照 MIN_QUOTA,返回 (axis, value, actual, floor, short)。"""
    out = []
    for ax, floor in MIN_QUOTA.items():
        actual = stats.get(ax, {})
        for v, q in floor.items():
            a = actual.get(v, 0)
            if a < q:
                out.append((ax, v, a, q, q - a))
    return out


def write_outputs(records, stats, short, raw_count, exact_dups, near_dups):
    # 10000Cases.txt: 纯文本,一行一条 query
    with OUT_TXT.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(r["query"].strip() + "\n")
    # 10000Cases.tagged.jsonl: 带元数据
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # coverage_stats.json
    OUT_JSON.write_text(json.dumps({
        "total": len(records),
        "raw": raw_count,
        "exact_dups_removed": exact_dups,
        "near_dups_removed": near_dups,
        "stats": stats,
        "min_quotas": MIN_QUOTA,
        "shortfalls": [
            {"axis": a, "value": v, "actual": ac, "floor": fl, "short": sh}
            for (a, v, ac, fl, sh) in short
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # coverage_report.md
    lines = []
    lines.append("# A2UI Query 数据生产覆盖度报告\n")
    lines.append(f"- **最终有效条数**: {len(records)}")
    lines.append(f"- **原始产出**: {raw_count}")
    lines.append(f"- **精确去重移除**: {exact_dups}")
    lines.append(f"- **近似去重移除**: {near_dups}")
    lines.append(f"- **场景数**: {len(SCENARIOS)}")
    lines.append("")
    lines.append("## 1. 各场景配额达成\n")
    lines.append("| 场景 ID | 场景名 | 配额 | 产出 | 入选 | 达成 |")
    lines.append("|---|---|---|---|---|---|")
    per_scn = Counter(r.get("scenario", "") for r in records)
    for s in SCENARIOS:
        sid = s["id"]
        produced = sum(1 for _ in (SCENARIOS_DIR / sid / "cases.jsonl").open(encoding="utf-8")) if (SCENARIOS_DIR / sid / "cases.jsonl").exists() else 0
        sel = per_scn.get(sid, 0)
        ok = "✅" if sel >= s["quota"] else "⚠️"
        lines.append(f"| {sid} | {s['name']} | {s['quota']} | {produced} | {sel} | {ok} |")
    lines.append("")
    lines.append("## 2. 12 轴覆盖度\n")
    lines.append("| 轴 | 枚举值 | 配额下限 | 实际命中 | 状态 |")
    lines.append("|---|---|---|---|---|")
    for ax in AXES:
        floor = MIN_QUOTA[ax]
        actual = stats.get(ax, {})
        for v, fq in sorted(floor.items(), key=lambda x: -x[1]):
            ac = actual.get(v, 0)
            ok = "✅" if ac >= fq else f"⚠️ 缺 {fq - ac}"
            lines.append(f"| {ax} | {v} | {fq} | {ac} | {ok} |")
    lines.append("")
    if short:
        lines.append("## 3. 未达标轴值(需补采)\n")
        for ax, v, ac, fl, sh in short:
            lines.append(f"- **{ax}={v}**: 实际 {ac} < 配额 {fl} (缺 {sh})")
    else:
        lines.append("## 3. 覆盖度\n")
        lines.append("所有轴值均达到配额下限。")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    print("加载原始数据...")
    raw = load_all()
    raw_count = len(raw)
    print(f"  原始: {raw_count}")

    print("精确去重...")
    dedup1, exact_d = exact_dedup(raw)
    print(f"  去重后: {len(dedup1)} (移除 {exact_d})")

    print("近重复(4-gram Jaccard)...")
    dedup2 = near_dedup(dedup1)
    near_d = len(dedup1) - len(dedup2)
    print(f"  去重后: {len(dedup2)} (移除 {near_d})")

    print("按配额选择...")
    final = quota_select(dedup2, TARGET_TOTAL)
    print(f"  最终: {len(final)} (目标 {TARGET_TOTAL})")

    print("计算覆盖度...")
    stats = coverage_stats(final)
    short = check_min(stats)

    print("写出...")
    write_outputs(final, stats, short, raw_count, exact_d, near_d)

    print(f"完成: {OUT_TXT}")
    if short:
        print(f"[WARN] {len(short)} 个轴值未达标,见 {OUT_MD}")
    else:
        print("[OK] 全部轴值达标")


if __name__ == "__main__":
    raise SystemExit(main())
