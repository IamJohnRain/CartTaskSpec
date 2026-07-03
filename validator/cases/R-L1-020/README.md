# R-L1-020 root Column底部间距合规

**严重度**: error

**描述**: root 为 Column 时，最后一段到 root 底部的间距应 ≤ 16；过小（<8）时给出告警。

**标签**: L1, layout

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-020`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-020",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
