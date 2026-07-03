# R-L1-014 Button可点击高度

**严重度**: error

**描述**: Button 高度必须 ≥ 24vp，否则热区不足。

**标签**: L1, text-fit

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-014`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-014",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
