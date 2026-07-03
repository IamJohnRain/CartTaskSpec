# R-L0-024 事件能力必须已知

**严重度**: error

**描述**: onClick handler 的 call 必须是已知事件能力：clickToCallPhone / clickToDeeplink / clickToIntent。

**标签**: L0, events

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-024`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-024",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
