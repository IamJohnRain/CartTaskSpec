# TaskSpec 协议规范

> 版本：`taskspec/v1`  
> 规则集：`harmony-form-datamodel-first-rules/v1`  
> 依据：`.agents/skills/harmony-card-generation-datamodel-first`  
> 用途：作为大模型与小模型之间的轻量桥接契约。大模型只给出卡片目标、内容需求、DataModel、动作和素材；具体布局、组件实现和 DSL 规则由 system prompt 约束，小模型最终只生成 `genui` DSL。

## 0. 项目级硬约束

- 禁止修改 `.agents/skills/` 目录下的任何内容。
- 本项目以 `harmony-card-generation-datamodel-first` skill 为只读依据，放弃旧 skill 的“禁用表达式 / 原生绑定优先”约束。
- 新 skill 原文仍描述 `genui + cardspec` 两个代码块；本项目在转换脚本的 system prompt 中做 DSL-only 适配：小模型不得输出 `cardspec`。
- 协议、schema、样例、转换脚本、校验脚本可以演进，但不得通过修改 skill 内容来消除不一致。

## 1. 设计目标

TaskSpec 要保持短小，不应变成半成品 DSL。

- 只描述“要显示什么、要点击什么、DataModel 里有什么、可用哪些素材”。
- 不描述具体布局树、区域划分、宽高预算、组件嵌套和视觉排版。
- 不包含 `rules.dsl`；DSL 硬规则统一写入 `taskspec_to_chat_completions.py` 的 system prompt。
- 不包含 `cardSpec` / `dataCapabilities` / 顶层 `eventBindings`。
- 不包含 `validation` / `capabilityGap`。
- 小模型只生成 `genui` DSL，不生成 `cardspec`。

## 2. 流程

1. 用户 query 经由大模型 Agent 生成轻量 TaskSpec。
2. `validate_taskspec.py` 校验 TaskSpec 结构、DataModel 引用、素材引用和内联动作。
3. `taskspec_to_chat_completions.py` 把 TaskSpec 转成 chat-completions request body，并在 system prompt 中注入全部 DSL 规则。
4. 小模型 API 只输出一个 `genui` 代码块。
5. `validate_generated_card.py` 校验 DSL 的三行 JSONL、DataModel 一致性、root 尺寸和组件引用。

## 3. 顶层结构

```json
{
  "schema": "taskspec/v1",
  "rulesVersion": "harmony-form-datamodel-first-rules/v1",
  "userQuery": "...",
  "task": "只输出一个 genui 代码块...",
  "card": {
    "scenario": "status",
    "size": "2x2",
    "requirements": []
  },
  "dataModel": { "value": {} },
  "assets": []
}
```

顶层只允许以上字段。旧字段 `rules`、`cardSpec`、`dataCapabilities`、`eventBindings`、`validation`、`capabilityGap` 都已移除。

## 4. 字段说明

### `card`

`card` 只承载卡片意图，不承载布局方案。

```json
{
  "scenario": "device",
  "size": "2x4",
  "requirements": [
    {
      "id": "device_name",
      "type": "identity",
      "label": "Free Clip 2",
      "dataPath": "/device/name",
      "required": true
    },
    {
      "id": "daily_30",
      "type": "action",
      "label": "每日30首",
      "onClick": [
        {
          "call": "clickToDeeplink",
          "args": {
            "bundleName": "",
            "abilityName": "",
            "uri": "..."
          }
        }
      ]
    }
  ],
  "constraints": ["简洁高级，磨砂玻璃质感"]
}
```

- `scenario`: 用于告诉小模型卡片的主要意图，影响信息优先级、视觉语气和交互密度。
  - `status`: 状态展示卡，突出当前状态或实时结果，例如天气、健康、设备在线状态。
  - `reminder`: 提醒/待办卡，突出时间、截止点、下一步动作，例如日程、服药、缴费提醒。
  - `action`: 快捷操作卡，核心价值是点击入口，例如拨号、打开应用、执行一个服务动作。
  - `device`: 设备信息卡，突出设备名称、指标、连接状态和快捷入口，例如耳机电量、家电状态。
  - `summary`: 摘要概览卡，展示多项信息的汇总，例如今日概览、消费摘要、运动摘要。
- `size`: `2x2` 或 `2x4`。按新 skill，DSL surface/root 目标尺寸为 `2x2 = 140x140`、`2x4 = 300x140`。
- `requirements`: 小模型必须表达的内容项。
- `constraints`: 可选，表达非结构化约束，例如视觉风格、信息优先级、必须完整显示的文本。

`requirements[].type` 可选值：

- `identity`: 身份/对象名，例如城市、联系人、设备名，通常作为标题或识别信息。
- `primary`: 主信息或主答案，例如当前温度、余额、最重要的状态，通常最醒目。
- `metric`: 数值指标，例如电量、步数、百分比，可用于文本或进度表达。
- `status`: 状态文本，例如感冒指数、在线/离线、风险等级。
- `context`: 辅助上下文，例如天气状况、更新时间、副标题，不应抢主信息层级。
- `media`: 图片或图标类内容，通常需要配合 `assetRef` 或静态素材。
- `action`: 可点击动作入口，必须内联 `onClick`。
- `style`: 视觉风格要求，例如磨砂玻璃、高级、温暖，用于约束视觉表达，不对应数据绑定。

### `dataModel`

`dataModel.value` 是小模型生成第 3 行 `updateDataModel.value` 时必须原样使用的初始数据，也是表达式和绑定路径的验证来源。

新 skill 是 DataModel-first：

- 展示值优先使用完整表达式 `{{ $__dataModel.xxx }}` 或 `{{ ${/json/pointer} }}`。
- `{"path":"/..."}`、相对模板 path 和 `formatString` 只作为兜底。
- TaskSpec 中的每个 `dataPath` 必须能从 `dataModel.value` 解析。

### `assets`

列出允许使用的素材路径。没有素材时必须是空数组 `[]`。未声明的图片、网络 URL、SVG 和 base64 SVG 不得使用。

## 5. 为什么移除三个旧模块

### `cardSpec`

新 skill 原文把 CardSpec 作为最终输出的一部分，但本项目当前目标是“小模型只生成 DSL”。因此 TaskSpec 不再携带 `cardSpec`，转换脚本也明确禁止小模型输出 `cardspec`。

如果未来端侧仍需要 CardSpec，应由独立链路或大模型 Agent 另行生成，不放进给小模型的 DSL-only TaskSpec。

### `dataCapabilities`

小模型只负责 DSL，不执行端侧数据能力选择，也不生成 CardSpec `dataBindings`。动态数据在 TaskSpec 中体现为 `dataModel.value` 的可绑定结构和 `card.requirements[].dataPath`。能力选择细节不再进入小模型输入。

### 顶层 `eventBindings`

事件能力仍然存在，但不再作为顶层模块。因为小模型生成 DSL 时只需要知道某个 action requirement 应挂什么 `onClick`，所以动作直接内联到 `card.requirements[type=action].onClick`，减少跨模块引用和 `eventRef` 跳转。

## 6. 校验规则

发送给小模型前：

- `schema` 必须是 `taskspec/v1`。
- `rulesVersion` 必须是 `harmony-form-datamodel-first-rules/v1`。
- 不得包含已移除字段：`rules`、`cardSpec`、`dataCapabilities`、`eventBindings`、`validation`、`capabilityGap`。
- `card.requirements[].id` 必须唯一。
- `requirements[].dataPath` 必须能从 `dataModel.value` 解析。
- `requirements[type=action].onClick` 必须存在，且 `call/args` 符合已支持事件能力。
- `requirements[].assetRef` 必须能在 `assets[].assetRef` 中找到。
- `.agents/skills/` 必须无改动。

小模型输出后：

- 只包含一个 `genui` 代码块。
- 不包含 `cardspec` 代码块。
- `genui` 恰好 3 行 JSONL。
- 第 1 行包含 `createSurface`，第 2 行包含 `updateComponents`，第 3 行包含 `updateDataModel`。
- `updateDataModel.value` 必须等于 `TaskSpec.dataModel.value`。
- `updateComponents.components` 必须是扁平组件数组，所有引用可解析。
- root 尺寸必须与新 skill 一致：`2x2 = 140x140`，`2x4 = 300x140`。

## 7. chat-completions request body

转换脚本生成的请求体必须包含 `system` 和 `user` 两条消息。

- `system`: 承载全部 DSL 硬规则，包括输出格式、组件范围、DataModel-first 绑定策略、尺寸、root shell、事件和素材约束。
- `user`: 放入完整 TaskSpec JSON。

示例：

```json
{
  "model": "glm-5.2",
  "messages": [
    {
      "role": "system",
      "content": "你是 HarmonyOS A2UI Form DSL 生成器..."
    },
    {
      "role": "user",
      "content": "{...TaskSpec JSON...}"
    }
  ]
}
```
