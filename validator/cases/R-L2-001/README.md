# R-L2-001 颜色格式合规

**严重度**: error

**描述**: 颜色值必须匹配 #RRGGBB 或 #AARRGGBB。

**标签**: L2, color

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L2-001`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L2-001",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
