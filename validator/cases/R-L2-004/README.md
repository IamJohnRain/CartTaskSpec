# R-L2-004 可见文本字面重复

**严重度**: error

**描述**: 同一卡片内 Text / Button 显示文本（去空白与标点后）不得完全相同，否则信息职责冲突。

**标签**: L2, content

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L2-004`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L2-004",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
