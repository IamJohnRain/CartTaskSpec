# R-L1-012 Image objectFit建议contain

**严重度**: warn

**描述**: Image 应使用 objectFit=contain 以避免刻意裁切，除非确认需要。

**标签**: L1, style

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-012`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-012",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
