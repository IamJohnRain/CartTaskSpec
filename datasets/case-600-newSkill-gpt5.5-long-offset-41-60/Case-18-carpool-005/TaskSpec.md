# TaskSpec 协议规范

> 结构依据：`taskspec.schema.json`  
> DSL 规则来源：`taskspec_to_chat_completions.py` 的 system prompt  
> skill 依据：`skills/harmony-card-generation-NewSkill` 与云侧方案设计

TaskSpec 是云侧微服务与 A2UI 模型之间的轻量桥接契约。主 Agent 不替 A2UI 模型设计卡片，也不生成最终 CardSpec；它只根据用户需求和能力 `outputSchema` 筛选候选展示字段路径。微服务完成能力裁决后，基于最终 CardSpec、能力注册表和主 Agent 候选字段投影构造 TaskSpec。A2UI 模型根据 system prompt 中的规则、用户原始需求、目标尺寸、`dataModelSchema`、动作候选和素材候选生成最终 `genui` DSL。

## 1. 设计原则

- TaskSpec 只提供 DSL 生成所需输入。
- 不出现 `component`、`position`、`fontSize`、区域划分、组件嵌套或布局树。
- 不提供 `displayCandidates` 或 `role`；展示内容由 A2UI 模型从 `userQuery` 和 `dataModelSchema` 中判断。
- `size` 记录目标尺寸。
- `eventCandidates` 是候选事件能力，不是 DSL `onClick`，也不是按钮或入口描述。
- `assetCandidates` 是素材约束，不是 DSL 组件候选。
- DSL 硬规则统一写入转换脚本的 system prompt。
- 交付物是 `genui` DSL。

## 2. 顶层结构

```json
{
  "userQuery": "...",
  "size": "2x4",
  "eventCandidates": [],
  "dataModelSchema": {},
  "assetCandidates": []
}
```

顶层只允许以上字段。

## 3. 字段说明

### `size`

`size` 描述目标卡片尺寸。

```json
"2x4"
```

必须，取值为 `2x2` 或 `2x4`。

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

### `dataModelSchema`

`dataModelSchema` 是微服务传给 A2UI 模型的参考数据结构，也是 DSL 动态绑定路径的验证来源之一。它不是真实运行时数据，也不要求覆盖能力 `outputSchema` 的全部字段。

`dataModelSchema` 来源：

- 主 Agent 在 `candidateDataBindings[].candidateOutputFields` 中只传候选展示字段路径。
- 微服务校验这些字段路径必须存在于对应能力 `outputSchema`。
- 微服务基于能力注册表还原字段 `type`、`description`，并维护 `sampleValue`。
- 不通过校验的候选字段不得进入 `dataModelSchema`。

字段节点示例：

```json
{
  "type": "string",
  "description": "当前温度展示文本",
  "sampleValue": "26℃"
}
```

字段说明：

- `type`: 必须，A2UI 模型可用于判断展示形式的字段类型。
- `description`: 必须，字段语义说明。
- `sampleValue`: 必须，给 A2UI 模型理解展示形态的实例值，优先使用接近 UI 展示的字符串，例如 `"26℃"`、`"多云"`、`"09:30 产品评审"`。

约束：

- `sampleValue` 由微服务内部维护或生成，不由主 Agent 传入。
- `sampleValue` 不代表用户真实运行时数据，不改变最终 CardSpec 的动态数据契约。
- 对敏感或私密字段，`sampleValue` 必须使用脱敏样例或占位样例。
- DSL 绑定路径必须来自最终 CardSpec、能力 `outputSchema` 或 `dataModelSchema` 可推导的动态路径，不能因为 `sampleValue` 存在而改写为静态文案。

示例：

```json
{
  "data": {
    "weather": {
      "location": {
        "name": {
          "type": "string",
          "description": "城市或区县名称",
          "sampleValue": "上海"
        }
      },
      "current": {
        "temperatureText": {
          "type": "string",
          "description": "当前温度展示文本",
          "sampleValue": "26℃"
        },
        "weatherText": {
          "type": "string",
          "description": "当前天气现象",
          "sampleValue": "多云"
        }
      }
    }
  }
}
```

对应的DataModel：

```json
{
  "data": {
    "weather": {
      "location": {
        "name": "上海"
      },
      "current": {
        "temperatureText": "26℃",
        "weatherText": "多云"
      }
    }
  }
}
```
生成的DSL要将sampleValue作为默认值填入最后的updateDataModel中，作为样例数据保证直接渲染结果的美观

### `assetCandidates`

素材候选白名单。它不规定素材最终做背景、图标、插图还是封面。

```json
[
  {
    "src": "assets/freeclip2-earbuds.png",
    "description": "Free Clip 2 耳机图形素材，适合用于设备识别或轻量装饰。",
  },
  {
    "src": "/music/cover.png",
    "description": "音乐封面图，可用于表达当前播放内容。",
  }
]
```

字段说明：
- `src`: 必须，素材路径。
- `description`: 必须，说明素材内容、视觉语义、适用场景以及主配色。svg后续可以支持自定义颜色，png颜色固定。A2UI 模型依据该字段判断是否使用素材。

## 4. System Prompt

转换脚本生成 chat-completions request body 时，会把 DSL 规则和 skill 摘要放入 `system` 消息。TaskSpec 不重复携带这些规则。

当前 system prompt 主要包含：

- **角色定义**：A2UI 模型，负责生成 HarmonyOS A2UI Form 卡片 DSL。
- **输入边界**：TaskSpec 不是布局蓝图，也不提供展示内容清单。
- **输出契约**：输出一个 `genui` 代码块，恰好 3 行 JSONL。
- **尺寸规则**：`size=2x2` 对应 140x140，`2x4` 对应 300x140。
- **组件范围**：只允许 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
- **Schema-first 绑定**：展示值优先使用完整表达式绑定动态数据路径，路径必须可从 `dataModelSchema`、最终 CardSpec 或能力 `outputSchema` 推导。
- **动作与素材**：最终 DSL 的 onClick 只能由 `eventCandidates` 转换而来；图片和背景只能来自 `assetCandidates` 或用户明确提供的本地/资源路径。
- **取舍规则**：先从 `userQuery` 和 `dataModelSchema` 确定主答案，控制支撑事实和动作区数量，避免信息重复。

## 5. 校验规则

发送给 A2UI 模型前：

- JSON 结构必须符合 `taskspec.schema.json`。
- 不允许出现 `displayCandidates`、`role`、`cardSpec`、`rules`、`dataModel` 等非当前协议字段。
- `dataModelSchema` 字段必须来自微服务校验后的能力输出字段投影。
- `dataModelSchema` 中字段节点必须包含 `type`、`description`、`sampleValue`。
- `sampleValue` 不得使用未脱敏的真实用户隐私数据。
- `eventCandidates[].call/args` 必须符合已支持事件能力。
- `eventCandidates[]` 不允许出现 `id`、`label`、`description`、`required` 或 `onClick`。
- `assetCandidates[].description` 必须非空。
- `assetCandidates[].bindTo` 必须能从最终 CardSpec、能力 `outputSchema` 或 `dataModelSchema` 推导。
- `.agents/skills/` 必须无改动。

A2UI 模型输出后：

- 包含一个 `genui` 代码块。
- `genui` 恰好 3 行 JSONL。
- 第 1 行包含 `createSurface`，第 2 行包含 `updateComponents`，第 3 行包含 `updateDataModel`。
- `updateDataModel.value` 不要求等于 `TaskSpec.dataModelSchema`；它只能包含模型生成 DSL 所需的受控静态辅助字段、加载态或空态字段，不得在动态数据能力输出路径下新增未授权字段。
- DSL 绑定路径必须能从 `TaskSpec.dataModelSchema`、最终 CardSpec、能力 `outputSchema` 或微服务允许的展示字段中推导。
- `updateComponents.components` 必须是扁平组件数组，所有引用可解析。
- root 尺寸必须与新 skill 一致：`2x2 = 140x140`，`2x4 = 300x140`。