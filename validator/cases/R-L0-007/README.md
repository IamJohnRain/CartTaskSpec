# R-L0-007 components必须为数组

**严重度**: error

**描述**: updateComponents.components 必须是 JSON 数组，否则组件树无法解析。

**标签**: L0, protocol

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-007`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-007",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
