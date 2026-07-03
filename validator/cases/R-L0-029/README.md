# R-L0-029 表达式必须完整{{...}}

**严重度**: error

**描述**: 字符串值若含 {{ 或 }}，必须构成完整 {{ ... }} 表达式；不允许半截表达式。

**标签**: L0, bindings

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-029`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-029",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
