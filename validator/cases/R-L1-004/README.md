# R-L1-004 fontSize必须在字号表

**严重度**: error

**描述**: styles.fontSize 必须命中受支持字号表 {10,12,14,16,18,20,32,40}。

**标签**: L1, style

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-004`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-004",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
