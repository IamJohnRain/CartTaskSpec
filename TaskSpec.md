# TaskSpec 协议规范

> 结构依据：`taskspec.schema.json`  
> DSL 规则来源：`taskspec_to_chat_completions.py` 的 system prompt  
> skill 依据：`.agents/skills/harmony-card-generation-datamodel-first`

TaskSpec 是大模型 Agent 与 A2UI 模型之间的轻量桥接契约。大模型 Agent 不替 A2UI 模型设计卡片，只从用户 query 中抽取内容、事件、素材和目标约束；A2UI 模型根据这些候选约束完成视觉组织、组件选择和最终 `genui` DSL。

## 1. 设计原则

- TaskSpec 只描述候选约束。
- `displayCandidates`、`eventCandidates`、`assetCandidates` 是语义候选，不是 DSL 组件候选。
- `label` 是可显示短文案，`description` 是给 A2UI 模型理解候选项语义、用途和使用重点的说明。
- 不出现 `component`、`position`、`fontSize`、区域划分、组件嵌套或布局树。
- `target` 记录目标尺寸、场景提示、风格提示和业务约束。
- DSL 硬规则统一写入转换脚本的 system prompt。
- 交付物是 `genui` DSL。

## 2. 顶层结构

```json
{
  "userQuery": "...",
  "task": "生成一个 genui DSL。",
  "target": {
    "size": "2x4",
    "sceneHints": ["device", "music"],
    "styleHints": ["简洁高级", "磨砂玻璃质感"]
  },
  "displayCandidates": [],
  "eventCandidates": [],
  "dataModel": {
    "value": {}
  },
  "assetCandidates": []
}
```

顶层只允许以上字段。

## 3. 字段说明

### `target`

`target` 描述生成目标。

```json
{
  "size": "2x4",
  "sceneHints": ["device", "music"],
  "styleHints": ["简洁高级", "磨砂玻璃质感"],
  "constraints": ["关键内容必须完整显示。"]
}
```

- `size`: 必须，`2x2` 或 `2x4`。
- `sceneHints`: 可选弱提示，例如 `device`、`music`、`weather`、`care`。
- `styleHints`: 可选风格提示，例如 `简洁高级`、`磨砂玻璃质感`。
- `constraints`: 可选补充约束，只写用户明确要求或业务硬约束。

### `displayCandidates`

可显示的信息候选。它不规定最终使用 Text、Progress、Image 还是组合组件。

```json
[
  {
    "id": "device_name",
    "role": "identity",
    "label": "Free Clip 2",
    "description": "耳机设备名称，用于明确这张桌面卡片服务的对象。",
    "dataPath": "/device/name",
    "required": true
  },
  {
    "id": "left_battery",
    "role": "metric",
    "label": "左耳电量",
    "description": "左耳机当前电量文本，用户要求必须显示并保持可读。",
    "dataPath": "/device/leftBatteryText",
    "required": true
  }
]
```

字段说明：

- `id`: 必须，候选项唯一标识。
- `role`: 必须，信息角色，帮助 A2UI 模型判断信息优先级。
- `label`: 必须，可显示短文案或字段名称。
- `description`: 必须，说明该内容的语义、用途、展示重点；不要写位置、字号、组件类型。
- `dataPath`: 可选，指向 `dataModel.value` 的 JSON Pointer。
- `assetRef`: 可选，引用 `assetCandidates[].assetRef`。
- `required`: 可选，是否必须体现在最终 DSL 中。
- `note`: 可选，补充约束；只写必要提醒。

`role` 可选值：

- `identity`: 身份/对象名，例如城市、联系人、设备名。
- `primary`: 主信息或主答案，例如当前温度、余额、最重要状态。
- `metric`: 数值指标，例如电量、步数、百分比。
- `status`: 状态文本，例如感冒指数、在线/离线、风险等级。
- `context`: 辅助上下文，例如天气状况、更新时间、副标题。
- `media`: 图片或图标类内容，通常配合 `assetRef`。

### `eventCandidates`

可点击事件候选。它不规定最终是 Button、可点击容器还是图文入口。

```json
[
  {
    "id": "daily_30",
    "label": "每日30首",
    "description": "打开每日30首音乐歌单的快捷入口，是用户要求保留的入口之一。",
    "required": true,
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
]
```

字段说明：

- `id`: 必须，候选项唯一标识。
- `label`: 必须，入口短文案。
- `description`: 必须，说明动作意图、触发结果和展示优先级；不要写按钮样式或位置。
- `required`: 可选，是否必须体现在最终 DSL 中。
- `onClick`: 必须，A2UI DSL 可使用的点击事件链。
- `note`: 可选，补充约束。

### `dataModel`

`dataModel.value` 是 A2UI 模型生成第 3 行 `updateDataModel.value` 时必须原样使用的初始数据，也是表达式和绑定路径的验证来源。

### `assetCandidates`

素材候选白名单。它不规定素材最终做背景、图标、插图还是封面。

```json
[
  {
    "assetRef": "earbuds_icon",
    "src": "assets/freeclip2-earbuds.png",
    "use": "device illustration",
    "description": "Free Clip 2 耳机图形素材，适合用于设备识别或轻量装饰。",
    "static": true
  },
  {
    "assetRef": "cover",
    "src": "/music/cover.png",
    "use": "album cover",
    "description": "音乐封面图，可用于表达当前播放内容。",
    "bindTo": "/music/cover"
  }
]
```

字段说明：

- `assetRef`: 可选，素材引用名，供 `displayCandidates[].assetRef` 使用。
- `src`: 必须，素材路径。
- `use`: 必须，素材用途短标签。
- `description`: 必须，说明素材内容、视觉语义和适用场景；A2UI 模型依据该字段判断是否使用素材。
- `bindTo`: 可选，素材路径绑定到 `dataModel.value` 的 JSON Pointer。
- `static`: 可选，是否为静态素材。

## 4. System Prompt

转换脚本生成 chat-completions request body 时，会把完整 DSL 规则放入 `system` 消息。TaskSpec 不重复携带这些规则。

当前 system prompt 主要包含：

- **角色定义**：A2UI 模型，负责生成 HarmonyOS A2UI Form 卡片 DSL。
- **输入边界**：TaskSpec 是候选约束契约，不是布局蓝图；candidate 不是 DSL 组件候选。
- **输出契约**：输出一个 `genui` 代码块，恰好 3 行 JSONL。
- **尺寸规则**：`target.size=2x2` 对应 140x140，`2x4` 对应 300x140。
- **组件范围**：只允许 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
- **DataModel-first 绑定**：展示值优先使用完整表达式读取 DataModel。
- **动作与素材**：onClick 只能来自 `eventCandidates`；图片和背景只能来自 `assetCandidates` 或用户明确提供的本地/资源路径。
- **布局质量**：控制主答案、支撑事实和动作区数量；关键文本必须完整显示。

## 5. 校验规则

发送给 A2UI 模型前：

- `displayCandidates` 必须非空。
- `displayCandidates[].description`、`eventCandidates[].description`、`assetCandidates[].description` 必须非空。
- `displayCandidates[].id` 与 `eventCandidates[].id` 必须全局唯一。
- `displayCandidates[].dataPath` 必须能从 `dataModel.value` 解析。
- `displayCandidates[].assetRef` 必须能在 `assetCandidates[].assetRef` 中找到。
- `eventCandidates[].onClick` 必须存在，且 `call/args` 符合已支持事件能力。
- `assetCandidates[].bindTo` 必须能从 `dataModel.value` 解析，且值等于 `assetCandidates[].src`。
- `.agents/skills/` 必须无改动。

A2UI 模型输出后：

- 包含一个 `genui` 代码块。
- `genui` 恰好 3 行 JSONL。
- 第 1 行包含 `createSurface`，第 2 行包含 `updateComponents`，第 3 行包含 `updateDataModel`。
- `updateDataModel.value` 必须等于 `TaskSpec.dataModel.value`。
- `updateComponents.components` 必须是扁平组件数组，所有引用可解析。
- root 尺寸必须与新 skill 一致：`2x2 = 140x140`，`2x4 = 300x140`。
