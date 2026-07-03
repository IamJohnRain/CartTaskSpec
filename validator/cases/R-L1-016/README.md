# R-L1-016 Row子项宽度预算

**严重度**: error

**描述**: Row 父容器宽 = 子项宽 + 子项 margin + 父 padding + itemMargin*间隔数，溢出时阻断。

**标签**: L1, layout

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-016`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-016",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
