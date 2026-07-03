# validator

A2UI genui DSL 校验器：基于原子规则的插件式校验框架。

## 能力

- 输入：纯 genui 的 `.jsonl` 文件（恰好 3 行 JSONL）
- 输出：结构化 JSON（`passed`、`violations[]`、`summary`）
- 规则可注册、可发现、可单独开关
- 58 条原子规则，覆盖 L0 协议 / L1 数值布局 / L2 内容视觉
- 每条规则配 fail.jsonl / pass.jsonl / expected.json 反例与正例
- 配套自动回归 `run_cases.py`

## 快速使用

```bash
python -m validator path/to/card.dsl.jsonl
python -m validator path/to/card.dsl.jsonl -c path/to/config.json
```

退出码：`passed=true` → 0；有 error/warn → 1；加载/配置错误 → 2。

## 配置文件格式

```json
{
  "rules": {
    "R-L0-005": { "enabled": true },
    "R-L2-002": { "enabled": false }
  }
}
```

- 缺省即全部启用
- `enabled: false` 关闭该规则
- 引用未知 `rule_id` 报错退出
- 完整开关模板见 `rules-config.default.json`

## 新增规则

详见 `docs/add-rule-guide.md`。三步走：

1. 在 `validator/rules/<分组>.py` 中写函数 + `@rule(...)`
2. 在 `validator/generate_cases.py` 加 mutator（或手写 `cases/<RULE_ID>/`）
3. 跑 `python validator/generate_cases.py` + `python validator/run_cases.py`

## 目录

```
validator/
├── __init__.py / __main__.py
├── cli.py / config.py / context.py / engine.py / loader.py / registry.py / result.py / rule.py
├── rules-config.default.json    全规则开关模板
├── generate_cases.py            用例生成器
├── run_cases.py                 用例回归（断言 fail/pass）
├── docs/add-rule-guide.md       AI/人类 新增规则指南
├── rules/                       9 个分组 58 条原子规则
└── cases/                       58 个 case 目录，每目录含 fail/pass/expected/README
```

## 依赖

仅 Python 标准库。`from __future__ import annotations` + dataclass + re + json + argparse。

## Windows PowerShell 注意

`>` 重定向会写 UTF-16 BOM，破坏 JSON 解析。建议：

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m validator card.jsonl | Out-File -Encoding utf8 out.json
```

或直接 `python -m validator card.jsonl` 看 stdout（控制台编码可用 `chcp 65001` 切换为 UTF-8）。
