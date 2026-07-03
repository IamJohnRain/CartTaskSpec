# R-L1-005 textOverflow禁用截断值

**严重度**: error

**描述**: 受保护文本禁止使用 ellipsis / clip / marquee 这类截断/滚动值，避免信息丢失。

**标签**: L1, style

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-005`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-005",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
