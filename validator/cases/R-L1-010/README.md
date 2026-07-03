# R-L1-010 Image必须有src

**严重度**: error

**描述**: Image 组件必须声明 src，且 src 不能为空。

**标签**: L1, style

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-010`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-010",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
