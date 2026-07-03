# R-L2-006 Button与Text并排基线告警

**严重度**: warn

**描述**: Button 与小号 Text 在同一 Row 并排时，若父 Row padding 上下相等且 Button 未设 margin.top，可能视觉基线偏高。

**标签**: L2, content

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L2-006`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L2-006",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
