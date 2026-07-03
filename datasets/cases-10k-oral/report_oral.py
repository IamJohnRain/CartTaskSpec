# -*- coding: utf-8 -*-
"""生成口语化版 HTML 数据生产报告 + 与原版对比的差异报告。"""
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_10K = HERE.parent / "cases-10k"
sys.path.insert(0, str(CASES_10K))
from coverage import AXES, MIN_QUOTA  # noqa: E402
from scenarios_def import SCENARIOS  # noqa: E402

OUT_HTML = HERE / "report.html"
STATS = json.loads((HERE / "coverage_stats.json").read_text(encoding="utf-8"))


def load_tagged():
    return [json.loads(l) for l in (HERE / "5000Cases.tagged.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def load_original_queries():
    return [l.strip() for l in (CASES_10K / "10000Cases.txt").read_text(encoding="utf-8").splitlines() if l.strip()]


def esc(s):
    return html.escape(str(s)) if s else ""


def axis_table():
    rows = []
    for ax in AXES:
        floor = MIN_QUOTA[ax]
        actual = STATS["stats"].get(ax, {})
        for v, fq in sorted(floor.items(), key=lambda x: -x[1]):
            ac = actual.get(v, 0)
            ratio = ac / fq if fq else 1
            cls = "ok" if ac >= fq else "warn"
            bar = min(100, int(ratio * 100))
            rows.append(
                f'<tr class="{cls}">'
                f'<td><code>{esc(ax)}</code></td>'
                f'<td>{esc(v)}</td>'
                f'<td class="num">{fq}</td>'
                f'<td class="num">{ac}</td>'
                f'<td><div class="bar"><div class="fill" style="width:{bar}%"></div></div></td>'
                f'<td class="num">{bar}%</td></tr>'
            )
    return ('<table class="matrix"><thead><tr>'
            '<th>轴</th><th>枚举值</th><th>原 10000 配额</th><th>实际</th><th>进度</th><th>比例</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')


def scenario_table():
    rows = []
    by_scn = Counter(r.get("scenario", "") for r in load_tagged())
    quota = STATS.get("oral_quota", {})
    for s in SCENARIOS:
        sid = s["id"]
        sel = by_scn.get(sid, 0)
        q = quota.get(sid, 0)
        ok = "[OK]" if sel >= q else "[WARN]"
        rows.append(f'<tr><td><code>{esc(sid)}</code></td>'
                    f'<td>{esc(s["name"])}</td>'
                    f'<td class="num">{q}</td>'
                    f'<td class="num">{sel}</td>'
                    f'<td>{ok}</td></tr>')
    return ('<table><thead><tr><th>场景 ID</th><th>名称</th><th>配额</th><th>入选</th><th>状态</th></tr></thead>'
            '<tbody>' + "".join(rows) + '</tbody></table>')


def samples_per_scenario(n=4):
    by_scn = {}
    for r in load_tagged():
        by_scn.setdefault(r.get("scenario", ""), []).append(r)
    parts = ['<div class="samples">']
    for s in SCENARIOS:
        lst = by_scn.get(s["id"], [])
        if not lst:
            continue
        sample = lst[::max(1, len(lst) // n)][:n]
        parts.append('<div class="sample-card">')
        parts.append(f'<h3>{esc(s["name"])} <span class="sid">{esc(s["id"])}</span></h3>')
        parts.append(f'<p class="desc">{esc(s["desc"])}</p>')
        for r in sample:
            q = r["query"]
            parts.append(
                f'<div class="q"><div class="qtext">{esc(q)}</div>'
                f'<div class="meta">长度 {len(q)} 字</div></div>'
            )
        parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def stats_cards():
    total = STATS["total"]
    cards = [
        ("最终条数", f"{total:,}", "card"),
        ("目标", "5,000", "card"),
        ("场景数", f"{len(SCENARIOS)}", "card"),
        ("原始产出", f"{STATS['raw']:,}", "card"),
        ("精确去重移除", f"{STATS['exact_dups_removed']:,}", "card"),
        ("与原 10000 集去重", f"{STATS['overlap_with_original_removed']:,}", "card"),
        ("未达原配额轴值", f"{len(STATS['shortfalls'])}", "card-warn"),
    ]
    return '<div class="cards">' + "".join(
        f'<div class="{c}"><div class="label">{esc(l)}</div><div class="value">{esc(v)}</div></div>'
        for l, v, c in cards
    ) + '</div>'


def main():
    head = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>口语化版 A2UI Query 数据生产报告</title>
<style>
  :root { --primary:#1f6feb; --bg:#0d1117; --panel:#161b22; --text:#e6edf3;
         --muted:#7d8590; --ok:#3fb950; --warn:#d29922; --border:#30363d; }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",PingFang SC,
                    Microsoft YaHei,sans-serif;line-height:1.6;font-size:14px}
  .container{max-width:1280px;margin:0 auto;padding:24px}
  h1{font-size:28px;margin:0 0 8px;color:#fff}
  h2{font-size:20px;margin:40px 0 12px;padding-bottom:8px;
     border-bottom:1px solid var(--border);color:#fff}
  h3{font-size:16px;margin:0 0 6px;color:#fff}
  .subtitle{color:var(--muted);margin:0 0 24px}
  .meta{color:var(--muted);font-size:12px;margin-bottom:24px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
         gap:12px;margin:20px 0}
  .card,.card-warn{background:var(--panel);border:1px solid var(--border);
                   border-radius:8px;padding:14px;text-align:center}
  .card-warn{border-color:var(--warn)}
  .card .label{color:var(--muted);font-size:12px;margin-bottom:4px}
  .card .value{font-size:22px;font-weight:600;color:var(--primary)}
  .card-warn .value{color:var(--warn)}
  table{width:100%;border-collapse:collapse;background:var(--panel);
        border:1px solid var(--border);border-radius:6px;overflow:hidden;
        font-size:13px}
  th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--border)}
  th{background:#1c2128;color:var(--muted);font-weight:500}
  td.num{text-align:right;font-variant-numeric:tabular-nums}
  code{background:#0d1117;padding:2px 6px;border-radius:3px;
       font-size:12px;color:#79c0ff}
  tr.ok{background:rgba(63,185,80,0.05)}
  tr.warn{background:rgba(210,153,34,0.08)}
  .bar{height:8px;background:#0d1117;border-radius:4px;overflow:hidden;width:100%}
  .fill{height:100%;background:linear-gradient(90deg,#3fb950,#1f6feb);
        transition:width .3s}
  tr.warn .fill{background:linear-gradient(90deg,#d29922,#d29922)}
  .samples{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));
           gap:14px;margin:20px 0}
  .sample-card{background:var(--panel);border:1px solid var(--border);
               border-radius:8px;padding:14px}
  .sample-card .sid{color:var(--muted);font-size:12px;font-weight:400}
  .sample-card .desc{color:var(--muted);font-size:12px;margin:0 0 10px}
  .q{margin-top:10px;padding:10px;background:#0d1117;
    border-left:3px solid var(--primary);border-radius:4px}
  .qtext{font-size:14px;margin-bottom:4px;line-height:1.5}
  .meta{color:var(--muted);font-size:11px}
  .pipeline{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
            gap:10px;margin:16px 0}
  .step{background:var(--panel);border:1px solid var(--border);
        border-radius:6px;padding:12px;position:relative}
  .step .n{position:absolute;top:8px;right:10px;color:var(--primary);
           font-weight:600;font-size:18px}
  .step .t{font-weight:600;margin-bottom:4px}
  .step .d{color:var(--muted);font-size:12px}
  .files{background:var(--panel);border:1px solid var(--border);
         border-radius:6px;padding:14px;margin:12px 0}
  .files li{margin:4px 0}
  .files code{font-size:12px}
  .oral{color:#f0883e}
  footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--border);
         color:var(--muted);font-size:12px;text-align:center}
</style>
</head>
<body><div class="container">"""
    parts = [head]
    parts.append('<h1>口语化版 A2UI Query 数据生产报告</h1>')
    parts.append('<p class="subtitle">手机输入习惯 · 口语化 · 8-35 字为主 · 无特殊符号</p>')
    parts.append('<p class="meta">生产时间: 2026-07 · 引擎: MiniMax-M3 · 场景数: 30 · 与原 10000 集完全独立</p>')

    parts.append('<h2>关键指标</h2>')
    parts.append(stats_cards())

    parts.append('<h2>生产流程</h2>')
    parts.append('<div class="pipeline">')
    steps = [
        ("1. 复用覆盖矩阵", "12 轴 + 30 场景 + 亲和度,直接 import 自 cases-10k/"),
        ("2. 口语化 prompt", "8-35 字、语气词、填充词、少量俚语"),
        ("3. 符号/长度校验", "中文+数字+英文+部分标点,严控特殊符号;8≤len≤60"),
        ("4. 失败重采样", "校验失败重抽覆盖配置再问,直到凑够 12 条"),
        ("5. 30 场景 3 波并行", "30 个独立 SubAgent 各跑一个场景"),
        ("6. 与原 10000 强去重", "normalize() 后命中即丢弃,确保完全独立"),
        ("7. 配额选择到 5000", "按场景比例 0.4892 选满,稀有度优先"),
    ]
    for i, (t, d) in enumerate(steps, 1):
        parts.append(f'<div class="step"><span class="n">{i}</span>'
                     f'<div class="t">{esc(t)}</div><div class="d">{esc(d)}</div></div>')
    parts.append('</div>')

    parts.append('<h2>12 轴覆盖度(对比原 10000 配额)</h2>')
    parts.append('<p class="meta">样本量 5000,约原 10000 的一半,部分轴未达原配额是预期</p>')
    parts.append(axis_table())

    parts.append('<h2>场景配额达成</h2>')
    parts.append(scenario_table())

    parts.append('<h2>各场景样本(每场景 4 条)</h2>')
    parts.append(samples_per_scenario(n=4))

    parts.append('<h2>交付物</h2>')
    parts.append('<div class="files"><ul>')
    files = [
        ("5000Cases.txt", "最终 5000 条口语化 query,纯文本一行一条"),
        ("5000Cases.tagged.jsonl", "带元数据(场景+11 轴覆盖配置)"),
        ("coverage_report.md", "Markdown 覆盖度报告"),
        ("coverage_stats.json", "结构化覆盖度统计"),
        ("scenarios/&lt;id&gt;/cases.jsonl", "30 个场景的原始产出,每场景 205-307 条"),
        ("gen_oral.py", "口语化生成脚本(支持 minimax/glm 双后端)"),
        ("merge_oral.py", "合并 + 与原 10000 集去重 + 选满 5000"),
        ("oral_vs_official.md", "与原版的差异对比报告"),
        ("report.html", "本报告"),
    ]
    for name, desc in files:
        parts.append(f'<li><code>{esc(name)}</code> — {esc(desc)}</li>')
    parts.append('</ul></div>')

    parts.append('<footer>CartTaskSpec · A2UI 卡片生成 · 口语化版数据生产</footer>')
    parts.append('</div></body></html>')

    OUT_HTML.write_text("".join(parts), encoding="utf-8")
    print(f"HTML 报告: {OUT_HTML}")


if __name__ == "__main__":
    raise SystemExit(main())
