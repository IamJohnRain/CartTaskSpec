"""生成口语化版 vs 原版 query 差异对比报告。"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_10K = HERE.parent / "cases-10k"
ORAL_FILE = HERE / "5000Cases.txt"
# 原版对比用 100Cases.txt(原始 11 场景种子,有 ## 段标记)和 10000Cases.txt(完整生成集)
ORIG_SEED_FILE = HERE.parent.parent / "100Cases.txt"
ORIG_FULL_FILE = CASES_10K / "10000Cases.txt"
OUT_MD = HERE / "oral_vs_official.md"


PARTICLES = ["啊", "嘛", "呢", "吧", "哈", "嗯", "哦", "呀"]
FILLERS = ["那个", "就是", "然后", "反正", "其实", "觉得", "感觉"]
SLANG = ["yyds", "绝绝子", "摆烂", "卷", "破防", "上头", "拿捏", "嘎嘎", "泰酷辣"]
PUNCT = ["。", "，", "!", "?", "！", "?"]

# 口语化特征开头
ORAL_STARTERS = ["帮我", "帮我弄", "给我", "能给我", "整个", "搞个", "整一个", "弄一个", "我想要"]


def load(path):
    return [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def length_stats(queries):
    lens = [len(q) for q in queries]
    return {
        "min": min(lens),
        "max": max(lens),
        "avg": sum(lens) / len(lens),
        "median": sorted(lens)[len(lens) // 2],
        "under35_pct": sum(1 for x in lens if x <= 35) / len(lens) * 100,
    }


def symbol_pct(queries, ch):
    return sum(1 for q in queries if ch in q) / len(queries) * 100


def count_pattern(queries, pat):
    return sum(1 for q in queries if pat in q)


def main():
    oral = load(ORAL_FILE)
    off = load(ORIG_FULL_FILE)  # 用 10000Cases.txt 做"原版完整集"对比
    print(f"口语化版: {len(oral)} 条")
    print(f"原版: {len(off)} 条")

    md = ["# 口语化版 vs 原版 Query 差异对比报告\n"]
    md.append(f"- **口语化版**: {len(oral)} 条 (`datasets/cases-10k-oral/5000Cases.txt`)")
    md.append(f"- **原版(完整)**: {len(off)} 条 (`datasets/cases-10k/10000Cases.txt`)")
    md.append(f"- **原版(原始 11 场景种子)**: 100 条 (`100Cases.txt`),用于样例对比")
    md.append("")

    # 1. 长度分布
    md.append("## 1. 长度分布\n")
    md.append("| 指标 | 口语化版 | 原版 |")
    md.append("|---|---|---|")
    o = length_stats(oral)
    f = length_stats(off)
    for k in ["min", "max", "avg", "median", "under35_pct"]:
        if k == "under35_pct":
            md.append(f"| {k} | {o[k]:.1f}% | {f[k]:.1f}% |")
        else:
            md.append(f"| {k} | {o[k]:.1f} | {f[k]:.1f} |")
    md.append("")

    # 2. 标点频率
    md.append("## 2. 标点频率(占 query 总数比例 %)\n")
    md.append("| 标点 | 口语化版 | 原版 | 差异 |")
    md.append("|---|---|---|---|")
    for ch in PUNCT:
        a = symbol_pct(oral, ch)
        b = symbol_pct(off, ch)
        md.append(f"| `{ch}` | {a:.1f}% | {b:.1f}% | {a - b:+.1f}pp |")
    md.append("")
    # 禁用符号
    md.append("### 禁用符号(应趋近 0%)\n")
    md.append("| 符号 | 口语化版 | 原版 |")
    md.append("|---|---|---|")
    for ch in ["(", ")", "（", "）", "[", "]", "「", "」",
               "——", "…", "…", "「", "」", "：", ";", "；", "@", "*", "_", "~", "=", "+", "|", "\\", "/", "`"]:
        a = symbol_pct(oral, ch)
        b = symbol_pct(off, ch)
        md.append(f"| `{ch}` | {a:.1f}% | {b:.1f}% |")
    md.append("")

    # 3. 语气词
    md.append("## 3. 语气词(出现次数)\n")
    md.append("| 语气词 | 口语化版 | 原版 | 倍数 |")
    md.append("|---|---|---|---|")
    for p in PARTICLES:
        a = count_pattern(oral, p)
        b = count_pattern(off, p)
        ratio = a / max(b, 1)
        md.append(f"| `{p}` | {a} ({a/len(oral)*100:.1f}%) | {b} ({b/len(off)*100:.1f}%) | {ratio:.1f}x |")
    md.append("")

    # 4. 填充词
    md.append("## 4. 填充词(出现次数)\n")
    md.append("| 填充词 | 口语化版 | 原版 |")
    md.append("|---|---|---|")
    for p in FILLERS:
        a = count_pattern(oral, p)
        b = count_pattern(off, p)
        md.append(f"| `{p}` | {a} | {b} |")
    md.append("")

    # 5. 俚语
    md.append("## 5. 网络俚语(出现次数)\n")
    md.append("| 俚语 | 口语化版 | 原版 |")
    md.append("|---|---|---|")
    for p in SLANG:
        a = count_pattern(oral, p)
        b = count_pattern(off, p)
        md.append(f"| `{p}` | {a} | {b} |")
    md.append("")

    # 6. 口语化开头
    md.append("## 6. 口语化开头动词(出现次数)\n")
    md.append("| 开头 | 口语化版 | 原版 | 倍数 |")
    md.append("|---|---|---|---|")
    for s in ORAL_STARTERS:
        a = count_pattern(oral, s)
        b = count_pattern(off, s)
        ratio = a / max(b, 1)
        md.append(f"| `{s}` | {a} ({a/len(oral)*100:.1f}%) | {b} ({b/len(off)*100:.1f}%) | {ratio:.1f}x |")
    md.append("")

    # 7. 样例对比
    md.append("## 7. 同一场景样例对比\n")
    md.append("| 场景 | 口语化版 | 原版 |")
    md.append("|---|---|---|")
    test_scenarios = [
        ("01-low-power", "低电模式"),
        ("05-agenda", "议程提醒"),
        ("09-weather-care", "天气关怀"),
        ("24-todo", "待办清单"),
        ("29-elderly-care", "老人关怀看护"),
    ]
    # 一次性解析 100Cases.txt(原版种子文件,有 ## 段),收集每段
    off_text = ORIG_SEED_FILE.read_text(encoding="utf-8")
    sections = {}
    cur, buf = None, []
    for line in off_text.splitlines():
        s = line.strip()
        if s.startswith("##"):
            if cur:
                sections[cur] = [x for x in buf if x]
            cur = s.lstrip("#").strip()
            buf = []
        elif s:
            buf.append(s)
    if cur:
        sections[cur] = [x for x in buf if x]

    oral_by = {}
    for line in (HERE / "5000Cases.tagged.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        oral_by.setdefault(r["scenario"], []).append(r["query"])
    for sid, sname in test_scenarios:
        oq = oral_by.get(sid, ["(无)"])[0]
        if sname in sections and sections[sname]:
            oq_orig = sections[sname][0]
        else:
            oq_orig = "(原 100Cases.txt 无 seed)"
        md.append(f"| {sname} | {oq} | {oq_orig} |")
    md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"对比报告: {OUT_MD}")


if __name__ == "__main__":
    main()
