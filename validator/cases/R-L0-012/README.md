# R-L0-012 不支持的组件类型

**严重度**: error

**描述**: 组件 component 字段必须是受支持集合之一（Text/Image/Divider/Progress/Button/Checkbox/Row/Column/List/Stack）。

**标签**: L0, components

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-012`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-012",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
