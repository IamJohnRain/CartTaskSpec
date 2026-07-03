# R-L0-006 createSurface尺寸合规

**严重度**: error

**描述**: createSurface.width/height 必须等于卡片尺寸对应值（2x2→140x140，2x4→300x140），其它尺寸一律不接受。

**标签**: L0, protocol

## 反例 (fail.jsonl)

最小化破坏该规则的卡片，用于回归测试与人工复核。

## 正例 (pass.jsonl)

满足该规则的基线卡片，runner 应当不触发 `R-L0-006`。

## 期望 (expected.json)

```json
{
  "rule_id": "R-L0-006",
  "should_fire_on_fail": true,
  "should_fire_on_pass": false
}
```
