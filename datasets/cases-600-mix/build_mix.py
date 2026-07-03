# -*- coding: utf-8 -*-
"""从 5000Cases.tagged.jsonl (oral) 和 10000Cases.tagged.jsonl (10k) 中,
每个场景各取前 PER_SCENARIO 条,合并成一个 600 条的混合测试集。

输出(同目录):
- 600Cases.tagged.jsonl  合并后的数据,每条加 "source" 字段
- index.jsonl           索引文件,逐行映射到原文件与原行号
- README.md             说明
"""
import json
from collections import defaultdict, OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASETS = HERE.parent

PER_SCENARIO = 10

SOURCES = [
    ("oral", DATASETS / "cases-10k-oral" / "5000Cases.tagged.jsonl"),
    ("10k",  DATASETS / "cases-10k"      / "10000Cases.tagged.jsonl"),
]

OUT_JSONL = HERE / "600Cases.tagged.jsonl"
OUT_INDEX = HERE / "index.jsonl"
OUT_README = HERE / "README.md"


def sample_top_n(path, n):
    """按文件出现顺序,每个场景取前 n 条;返回 list[(original_line_no, record)]。
    场景顺序以文件中首次出现的顺序为准(后续按编号重排)。"""
    by_scn = defaultdict(list)
    order = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            scn = r.get("scenario", "")
            if scn not in by_scn:
                order.append(scn)
            if len(by_scn[scn]) < n:
                by_scn[scn].append((i, r))
    return by_scn, order


def main():
    # 1) 两个源各自采样
    sampled = {}        # source -> {scenario -> [(line, record), ...]}
    orders = {}         # source -> [scenario, ...]  文件首次出现顺序
    for tag, p in SOURCES:
        if not p.exists():
            raise SystemExit(f"[ERR] 找不到源文件: {p}")
        by_scn, order = sample_top_n(p, PER_SCENARIO)
        sampled[tag] = by_scn
        orders[tag] = order
        total = sum(len(v) for v in by_scn.values())
        print(f"[{tag}] {p.name}: {len(by_scn)} 场景, 共采样 {total} 条")

    # 2) 合并: 统一场景顺序按场景编号排序; 每个场景内 oral 在前、10k 在后
    all_scns = sorted(
        set(orders["oral"]) | set(orders["10k"]),
        key=lambda s: (int(s.split("-", 1)[0]), s),
    )

    merged = []      # [(source, source_file, original_line, record)]
    for scn in all_scns:
        for tag, _p in SOURCES:
            for orig_line, rec in sampled[tag].get(scn, []):
                merged.append((tag, str(_p), orig_line, rec))

    print(f"[合并] 总计 {len(merged)} 条, {len(all_scns)} 场景")

    # 3) 写 600Cases.tagged.jsonl
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for tag, _src, _line, rec in merged:
            out = OrderedDict(rec)
            out["source"] = tag
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    # 4) 写 index.jsonl (逐行对齐)
    with OUT_INDEX.open("w", encoding="utf-8") as f:
        for new_line, (tag, src, orig_line, rec) in enumerate(merged, start=1):
            entry = OrderedDict([
                ("new_line", new_line),
                ("source", tag),
                ("source_file", src),
                ("original_line", orig_line),
                ("scenario", rec.get("scenario", "")),
                ("scenario_name", rec.get("scenario_name", "")),
            ])
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 5) 写 README.md
    src_summary = "\n".join(
        f"- `{tag}`: `{p.relative_to(DATASETS)}`" for tag, p in SOURCES
    )
    OUT_README.write_text(
        "# cases-600-mix\n\n"
        "从两个源文件中,每个场景各取前 "
        f"{PER_SCENARIO} 条混合而成,合计 {len(merged)} 条测试集。\n\n"
        "## 来源\n" + src_summary + "\n\n"
        "## 文件\n"
        "- `600Cases.tagged.jsonl` — 合并数据,每条记录新增 `source` 字段(`oral`/`10k`)\n"
        "- `index.jsonl` — 索引,逐行映射到原文件名与原始行号\n"
        "- `build_mix.py` — 构建脚本\n\n"
        "## 顺序\n"
        "- 按 scenario 编号(01–30)排序\n"
        "- 每个场景内: oral 的前 10 条在前, 10k 的前 10 条在后\n\n"
        "## 索引字段\n"
        "| 字段 | 说明 |\n|---|---|\n"
        "| new_line | 新文件中的行号(1-based) |\n"
        "| source | `oral` 或 `10k` |\n"
        "| source_file | 原始文件相对路径 |\n"
        "| original_line | 在原始文件中的行号(1-based) |\n"
        "| scenario | 场景 ID |\n"
        "| scenario_name | 场景中文名 |\n",
        encoding="utf-8",
    )

    print(f"[OK] 写出: {OUT_JSONL}")
    print(f"[OK] 写出: {OUT_INDEX}")
    print(f"[OK] 写出: {OUT_README}")


if __name__ == "__main__":
    raise SystemExit(main())
