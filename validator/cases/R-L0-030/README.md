# R-L0-030 表达式路径在DataModel缺失

**严重度**: error

**描述**: {{ ... }} 内引用的所有绝对 JSON Pointer 路径必须在 updateDataModel.value 中存在。

**标签**: L0, bindings

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-030`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-030",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
