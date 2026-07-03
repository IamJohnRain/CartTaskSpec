# R-L2-005 可见文本可能语义重复

**严重度**: warn

**描述**: 两个可见文本归一化后存在包含关系，可能为同义/聚合重复，需人工复核。

**标签**: L2, content

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L2-005`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L2-005",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
