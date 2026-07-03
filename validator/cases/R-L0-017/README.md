# R-L0-017 children必须为数组或模板对象

**严重度**: error

**描述**: children 字段必须是 id 字符串数组，或 {componentId, path} 模板对象；其它类型一律非法。

**标签**: L0, components

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-017`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-017",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
