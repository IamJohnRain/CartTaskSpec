# R-L0-021 模板path必须为绝对指针

**严重度**: error

**描述**: 模板 children.path 必须是字符串且以 / 开头（绝对 JSON Pointer）。

**标签**: L0, protocol

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-021`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-021",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
