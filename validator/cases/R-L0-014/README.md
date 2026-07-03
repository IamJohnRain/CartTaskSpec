# R-L0-014 仅允许onClick事件

**严重度**: error

**描述**: DSL 只允许 onClick 一种事件；其它 on* 事件一律禁止。

**标签**: L0, components

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-014`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-014",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
