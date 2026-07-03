# R-L0-005 surfaceId一致性

**严重度**: error

**描述**: 三行消息的 surfaceId 必须完全相等，否则卡片无法正确关联渲染。

**标签**: L0, protocol

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-005`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-005",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
