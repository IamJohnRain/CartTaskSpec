# R-L0-016 禁止SVG

**严重度**: error

**描述**: 禁止使用 SVG（包括 data:image/svg+xml 内联或 .svg 链接）。

**标签**: L0, components

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-016`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-016",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
