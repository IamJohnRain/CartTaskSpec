# R-L1-003 root padding建议12

**严重度**: warn

**描述**: root 默认安全区 padding 应为 12，偏离时给出告警。

**标签**: L1, layout

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-003`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-003",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
