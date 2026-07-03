# R-L1-008 linearGradient.colors非空

**严重度**: error

**描述**: styles.linearGradient.colors 必须是非空数组。

**标签**: L1, style

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-008`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-008",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
