# R-L1-006 padding/margin应使用间距表

**严重度**: warn

**描述**: styles.padding 与 styles.margin 应尽量使用间距表 {0,2,4,6,8,10,12,14,16}，偏离时给出告警。

**标签**: L1, style

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-006`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-006",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
