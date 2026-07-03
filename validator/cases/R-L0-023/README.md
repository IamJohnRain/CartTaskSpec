# R-L0-023 onClick handler必须为对象

**严重度**: error

**描述**: onClick 数组中的每一项必须是 JSON 对象。

**标签**: L0, events

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-023`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-023",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
