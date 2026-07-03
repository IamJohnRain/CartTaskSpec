# R-L0-032 formatString参数类型

**严重度**: error

**描述**: formatString 调用的 args.value 必须是字符串模板。

**标签**: L0, bindings

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-032`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-032",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
