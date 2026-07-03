# R-L0-002 version必须为v0.9

**严重度**: error

**描述**: genui 三行消息的 version 字段必须等于字符串 v0.9，否则协议解析失败。

**标签**: L0, protocol

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-002`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-002",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
