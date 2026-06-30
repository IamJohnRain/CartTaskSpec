# TaskSpec 协议规范

> 结构依据：`taskspec.schema.json`  
> DSL 规则来源：`taskspec_to_chat_completions.py` 的 system prompt  
> skill 依据：`.agents/skills/harmony-card-generation-datamodel-first`

TaskSpec 是大模型 Agent 与 A2UI 模型之间的轻量桥接契约。大模型 Agent 不替 A2UI 模型设计卡片，也不预先整理显示内容清单；它只保留用户原始需求、目标尺寸、DataModel、动作候选和素材候选。A2UI 模型根据 system prompt 中的 skill 摘要规则自行完成信息取舍、组件组织、视觉表达和最终 `genui` DSL。

## 1. 设计原则

- TaskSpec 只提供 DSL 生成所需输入。
- 不出现 `component`、`position`、`fontSize`、区域划分、组件嵌套或布局树。
- 不提供 `displayCandidates` 或 `role`；展示内容由 A2UI 模型从 `userQuery` 和 `dataModel.value` 中判断。
- `target` 只记录目标尺寸。
- `eventCandidates` 是候选事件能力，不是 DSL `onClick`，也不是按钮或入口描述。
- `assetCandidates` 是素材约束，不是 DSL 组件候选。
- DSL 硬规则统一写入转换脚本的 system prompt。
- 交付物是 `genui` DSL。

## 2. 顶层结构

```json
{
  "userQuery": "...",
  "target": {
    "size": "2x4"
  },
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

`target` 描述目标卡片尺寸。

```json
{
  "size": "2x4"
}
```

- `size`: 必须，`2x2` 或 `2x4`。

### `eventCandidates`

候选事件能力。它不规定最终是 Button、可点击容器还是图文入口，也不直接表达 DSL `onClick`。

```json
[
  {
    "call": "clickToDeeplink",
    "args": {
      "bundleName": "",
      "abilityName": "",
      "uri": "..."
    }
  }
]
```

字段说明：

- `call`: 必须，事件能力名，例如 `clickToCallPhone`、`clickToDeeplink`。
- `args`: 可选，事件参数对象。参数必须符合对应事件能力。

A2UI 模型应从 `userQuery` 判断哪些事件需要变成可点击入口。最终 DSL 中如果使用事件，才把候选事件转换为组件的 `onClick` 数组项。

### `dataModel`

`dataModel.value` 是 A2UI 模型生成第 3 行 `updateDataModel.value` 时必须原样使用的初始数据，也是表达式和绑定路径的验证来源。A2UI 模型从 `userQuery` 和 `dataModel.value` 中自行判断需要展示的信息。

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

- `assetRef`: 可选，素材引用名。
- `src`: 必须，素材路径。
- `use`: 必须，素材用途短标签。
- `description`: 必须，说明素材内容、视觉语义和适用场景；A2UI 模型依据该字段判断是否使用素材。
- `bindTo`: 可选，素材路径绑定到 `dataModel.value` 的 JSON Pointer。
- `static`: 可选，是否为静态素材。

## 4. System Prompt

转换脚本生成 chat-completions request body 时，会把 DSL 规则和 skill 摘要放入 `system` 消息。TaskSpec 不重复携带这些规则。

当前 system prompt 主要包含：

- **角色定义**：A2UI 模型，负责生成 HarmonyOS A2UI Form 卡片 DSL。
- **输入边界**：TaskSpec 不是布局蓝图，也不提供展示内容清单。
- **输出契约**：输出一个 `genui` 代码块，恰好 3 行 JSONL。
- **尺寸规则**：`target.size=2x2` 对应 140x140，`2x4` 对应 300x140。
- **组件范围**：只允许 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
- **DataModel-first 绑定**：展示值优先使用完整表达式读取 DataModel。
- **动作与素材**：最终 DSL 的 onClick 只能由 `eventCandidates` 转换而来；图片和背景只能来自 `assetCandidates` 或用户明确提供的本地/资源路径。
- **取舍规则**：先从 `userQuery` 和 `dataModel.value` 确定主答案，控制支撑事实和动作区数量，避免信息重复。

## 5. 校验规则

发送给 A2UI 模型前：

- JSON 结构必须符合 `taskspec.schema.json`。
- 不允许出现 `displayCandidates`、`role`、`cardSpec`、`rules` 等非当前协议字段。
- `eventCandidates[].call/args` 必须符合已支持事件能力。
- `eventCandidates[]` 不允许出现 `id`、`label`、`description`、`required` 或 `onClick`。
- `assetCandidates[].description` 必须非空。
- `assetCandidates[].bindTo` 必须能从 `dataModel.value` 解析，且值等于 `assetCandidates[].src`。
- `.agents/skills/` 必须无改动。

A2UI 模型输出后：

- 包含一个 `genui` 代码块。
- `genui` 恰好 3 行 JSONL。
- 第 1 行包含 `createSurface`，第 2 行包含 `updateComponents`，第 3 行包含 `updateDataModel`。
- `updateDataModel.value` 必须等于 `TaskSpec.dataModel.value`。
- `updateComponents.components` 必须是扁平组件数组，所有引用可解析。
- root 尺寸必须与新 skill 一致：`2x2 = 140x140`，`2x4 = 300x140`。
