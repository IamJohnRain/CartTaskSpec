# R-L0-015 禁止网络URL

**严重度**: error

**描述**: 所有字符串值禁止以 http:// 或 https:// 开头，禁止引入网络资源。

**标签**: L0, components

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-015`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-015",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
