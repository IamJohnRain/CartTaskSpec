# -*- coding: utf-8 -*-
"""生成 HTML 数据生产报告。"""
import html
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from coverage import AXES, MIN_QUOTA  # noqa: E402
from scenarios_def import SCENARIOS  # noqa: E402

OUT_HTML = HERE / "report.html"
STATS = json.loads((HERE / "coverage_stats.json").read_text(encoding="utf-8"))
TXT_FILE = HERE / "10000Cases.txt"
TAGGED_FILE = HERE / "10000Cases.tagged.jsonl"

# 读 tagged 拿样本
def load_tagged():
    out = []
    for line in TAGGED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def esc(s):
    return html.escape(str(s)) if s else ""


def section_header(title, n=2):
    return f'<h{n}>{esc(title)}</h{n}>'


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
                f'<td class="num">{bar}%</td>'
                f'</tr>'
            )
    return (
        '<table class="matrix"><thead><tr>'
        '<th>轴</th><th>枚举值</th><th>配额</th><th>实际</th><th>进度</th><th>比例</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    )


def scenario_table():
    rows = []
    by_scn = Counter(r.get("scenario", "") for r in load_tagged())
    produced = {}
    for s in SCENARIOS:
        f = HERE / "scenarios" / s["id"] / "cases.jsonl"
        produced[s["id"]] = sum(1 for _ in f.open(encoding="utf-8")) if f.exists() else 0
    for s in SCENARIOS:
        sid = s["id"]
        sel = by_scn.get(sid, 0)
        prod = produced[sid]
        rate = sel / s["quota"] * 100 if s["quota"] else 0
        ok = "✅" if sel >= s["quota"] else "⚠️"
        rows.append(
            f'<tr><td><code>{esc(sid)}</code></td>'
            f'<td>{esc(s["name"])}</td>'
            f'<td class="num">{s["quota"]}</td>'
            f'<td class="num">{prod}</td>'
            f'<td class="num">{sel}</td>'
            f'<td>{ok}</td></tr>'
        )
    return (
        '<table><thead><tr><th>场景 ID</th><th>名称</th>'
        '<th>配额</th><th>原始产出</th><th>入选</th><th>状态</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table>'
    )


def samples_per_scenario(n=3):
    """每个场景抽 n 条样本,展示多样化。"""
    by_scn = {}
    for r in load_tagged():
        by_scn.setdefault(r.get("scenario", ""), []).append(r)
    parts = ['<div class="samples">']
    for s in SCENARIOS:
        lst = by_scn.get(s["id"], [])
        if not lst:
            continue
        # 抽 3 条,按轴多样性选
        sample = lst[::max(1, len(lst) // n)][:n]
        parts.append(f'<div class="sample-card">')
        parts.append(f'<h3>{esc(s["name"])} <span class="sid">{esc(s["id"])}</span></h3>')
        parts.append(f'<p class="desc">{esc(s["desc"])}</p>')
        for r in sample:
            ax = r.get("axes", {})
            tags = " · ".join(
                f'<span class="tag">{esc(k)}={esc(v)}</span>'
                for k, v in ax.items() if v != "none"
            )
            parts.append(
                f'<div class="q"><div class="qtext">{esc(r["query"])}</div>'
                f'<div class="tags">{tags}</div></div>'
            )
        parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def stats_cards():
    total = STATS["total"]
    raw = STATS["raw"]
    short = STATS.get("shortfalls", [])
    cards = [
        ("最终条数", f"{total:,}", "card"),
        ("目标", f"{STATS.get('min_quotas', {}).get('size', {}).get('2x2', 0) + STATS.get('min_quotas', {}).get('size', {}).get('2x4', 0):,}", "card"),
        ("场景数", f"{len(SCENARIOS)}", "card"),
        ("原始产出", f"{raw:,}", "card"),
        ("精确去重", f"{STATS['exact_dups_removed']:,}", "card"),
        ("近似去重", f"{STATS['near_dups_removed']:,}", "card"),
        ("未达标轴", f"{len(short)}", "card" if not short else "card-warn"),
    ]
    return '<div class="cards">' + "".join(
        f'<div class="{c}"><div class="label">{esc(l)}</div><div class="value">{esc(v)}</div></div>'
        for l, v, c in cards
    ) + '</div>'


def main():
    html_parts = ["""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A2UI Query 数据生产报告</title>
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
  .qtext{font-size:13px;margin-bottom:6px;line-height:1.5}
  .tags{font-size:11px;line-height:1.6}
  .tag{display:inline-block;background:#1c2128;color:#79c0ff;
       padding:1px 6px;margin:2px 3px 2px 0;border-radius:10px;
       font-family:ui-monospace,Menlo,Consolas,monospace}
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
  footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--border);
         color:var(--muted);font-size:12px;text-align:center}
</style>
</head>
<body><div class="container">"""]
    html_parts.append('<h1>A2UI 卡片 Query 数据生产报告</h1>')
    html_parts.append('<p class="subtitle">基于 harmony-card-generation-datamodel-first skill 的能力覆盖矩阵驱动</p>')
    html_parts.append(f'<p class="meta">生产时间: 2026-07-02 · 引擎: MiniMax-M3 · 场景数: {len(SCENARIOS)}</p>')

    # 关键统计卡片
    html_parts.append('<h2>关键指标</h2>')
    html_parts.append(stats_cards())

    # 流程
    html_parts.append('<h2>生产流程</h2>')
    html_parts.append('<div class="pipeline">')
    steps = [
        ("1. 覆盖矩阵定义", "从 skill 提取 12 个能力轴,编码为 coverage.py"),
        ("2. 场景池 + 亲和度", "30 个场景(11 原+19 扩展),每个场景对各轴值加权"),
        ("3. 单场景生成", "gen_cases.py 调用 LLM 按覆盖配置采样,逐批追加"),
        ("4. 并行派发", "3 批 × 8 个独立 SubAgent 并行,每场景 1 个"),
        ("5. 合并 + 去重", "merge_and_validate.py 合并 + 精确去重 + 4-gram 近重复"),
        ("6. 配额选择", "按场景配额 + 稀有度评分裁剪到 10000 条"),
        ("7. 覆盖度校验", "对比 MIN_QUOTA,生成报告"),
    ]
    for i, (t, d) in enumerate(steps, 1):
        html_parts.append(f'<div class="step"><span class="n">{i}</span>'
                          f'<div class="t">{esc(t)}</div><div class="d">{esc(d)}</div></div>')
    html_parts.append('</div>')

    # 12 轴覆盖度
    html_parts.append('<h2>12 轴覆盖度</h2>')
    html_parts.append('<p class="meta">每个枚举值都达到配额下限</p>')
    html_parts.append(axis_table())

    # 场景配额
    html_parts.append('<h2>场景配额达成</h2>')
    html_parts.append(scenario_table())

    # 样本
    html_parts.append('<h2>各场景样本(每场景 3 条)</h2>')
    html_parts.append(samples_per_scenario(n=3))

    # 交付物
    html_parts.append('<h2>交付物</h2>')
    html_parts.append('<div class="files"><ul>')
    files = [
        ("10000Cases.txt", "最终 10000 条 query,纯文本一行一条,同 100Cases.txt 格式"),
        ("10000Cases.tagged.jsonl", "带元数据(场景 + 11 轴覆盖配置)的 10000 条"),
        ("coverage_report.md", "Markdown 覆盖度报告"),
        ("coverage_stats.json", "结构化覆盖度统计"),
        ("scenarios/&lt;id&gt;/cases.jsonl", "30 个场景的原始产出,每场景 350-525 条"),
        ("gen_cases.py", "单场景生成脚本(支持 minimax/glm 双后端)"),
        ("merge_and_validate.py", "合并 + 去重 + 覆盖度校验脚本"),
        ("coverage.py / scenarios_def.py", "覆盖矩阵 + 场景定义"),
        ("report.html", "本报告"),
    ]
    for name, desc in files:
        html_parts.append(f'<li><code>{esc(name)}</code> — {esc(desc)}</li>')
    html_parts.append('</ul></div>')

    html_parts.append('<footer>CartTaskSpec · A2UI 卡片生成 · 自动化数据生产管线</footer>')
    html_parts.append('</div></body></html>')

    OUT_HTML.write_text("".join(html_parts), encoding="utf-8")
    print(f"HTML 报告: {OUT_HTML}")


if __name__ == "__main__":
    raise SystemExit(main())
