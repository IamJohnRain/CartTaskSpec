# R-L0-011 禁用组件类型

**严重度**: error

**描述**: Form 卡片禁止使用 TextInput/Toggle/Radio/CheckboxGroup/Select/NavContainer/Tabs/TabContent/Web/Grid/If 等组件。

**标签**: L0, components

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-011`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-011",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
