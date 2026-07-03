# R-L0-003 消息结构纯净

**严重度**: error

**描述**: 三行消息除 version 外只能各自包含 createSurface / updateComponents / updateDataModel 之一，不能混入多余键。

**标签**: L0, protocol

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-003`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-003",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
