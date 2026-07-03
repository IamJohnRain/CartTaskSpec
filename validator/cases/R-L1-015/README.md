# R-L1-015 Button label宽度合规

**严重度**: error

**描述**: Button label 估算宽度 + 16vp 内边距不得超过 styles.width。

**标签**: L1, text-fit

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L1-015`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L1-015",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
