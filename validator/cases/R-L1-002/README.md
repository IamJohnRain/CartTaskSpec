# R-L1-002 root圆角与clip合规

**严重度**: error

**描述**: root 必须使用尺寸对应圆角（2x2→18，2x4→22）并开启 clip。

**标签**: L1, layout

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-002`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-002",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
