# R-L0-020 模板componentId存在

**严重度**: error

**描述**: 模板 children.componentId 必须引用已声明的组件 id。

**标签**: L0, protocol

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-020`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-020",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
