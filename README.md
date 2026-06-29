# CartTaskSpec

CartTaskSpec 是一个面向 HarmonyOS A2UI Form 服务卡片的「大模型 + 小模型」协作生成协议。大模型负责理解用户意图、确定卡片目标、数据能力和最终 CardSpec，并产出一个轻量的 TaskSpec；小模型只依据 TaskSpec 负责把卡片「画」出来，生成 A2UI Form 的 `genui` DSL。

> 协议版本：`taskspec/v1`
> 规则集：`harmony-form-rules/v1`

---

## 项目介绍

很多卡片生成任务可以拆成两层：一层需要强理解力（场景识别、信息取舍、能力选择、端侧契约），另一层是确定性的结构化输出（按规则把卡片落成 DSL JSONL）。本项目用 TaskSpec 把这两层解耦：

- 大模型读用户的一句请求和只读的 `harmony-card-generation` skill，产出 TaskSpec。
- TaskSpec 只携带「要显示什么、要调用什么、必须遵守什么」，不携带具体布局树、区域划分、宽度预算或组件嵌套。布局和视觉实现交回给小模型。
- 小模型收到 chat-completions 请求体（含 system prompt + TaskSpec），只输出一个 `genui` 代码块（3 行 JSONL）。
- 最终输出只有小模型生成的 `genui` DSL；`cardSpec` 是 TaskSpec 中的端侧契约，不由小模型生成，也不作为小模型最终输出的一部分。

小模型不再生成 `cardspec`，大模型也不再越界把整棵组件树写进 TaskSpec。

---

## 协议设计原则

1. **轻量，而不是半成品 DSL**
   TaskSpec 只描述卡片目标、内容项、数据/事件/素材能力和 DSL 硬约束，不描述布局方案。具体区域、根 shell、宽度预算、组件嵌套都属于小模型的实现职责。

2. **职责单向收窄**
   - 场景识别、尺寸选择、能力边界判断：大模型。
   - 语义内容项、DataModel 形状、CardSpec、事件能力预填：大模型。
   - 布局、组件层级、id 命名、样式与视觉表达：小模型。
   - CardSpec：大模型生成，直接交付端侧，小模型不得生成或改写。

3. **系统提示承载通用约束**
   chat-completions 请求体包含 `system` prompt，集中说明协议关键信息和输出规则，避免每个 TaskSpec 重复一大段 DSL 教程；TaskSpec 的 `rules.dsl` 只放本次需要的硬约束补充。

4. **可校验**
   - 结构形状用 `taskspec.schema.json`（JSON Schema Draft 2020-12）。
   - 引用一致性（dataPath / eventRef / assetRef / dataBindings）用 `validate_taskspec.py`。
   - 模型输出（只输出 genui、恰好 3 行、DataModel 一致、root 尺寸一致）用 `validate_generated_card.py`。
   - 项目约束（不得修改 `.agents/skills/`）用 `validate_project_constraints.py`。

5. **skill 只读**
   `harmony-card-generation` skill 在本项目中是外部只读依赖。协议、schema、转换脚本和校验脚本可以在项目层演进，但不得通过编辑 skill 来消除冲突。如果 skill 原文与本项目流程不一致，以 `TaskSpec.md`、`taskspec.schema.json` 和项目脚本为准。

---

## 项目结构

```text
CartTaskSpec/
├── README.md                          项目说明
├── TaskSpec.md                        TaskSpec 协议规范（项目权威）
├── taskspec.schema.json               TaskSpec JSON Schema（Draft 2020-12）
├── taskspec_to_chat_completions.py    TaskSpec -> chat-completions 请求体
├── validate_taskspec.py               TaskSpec 结构 + 引用一致性校验
├── validate_generated_card.py         小模型生成的 genui 输出校验
├── validate_project_constraints.py    项目硬约束检查（.agents/skills 只读）
├── update_skill.sh                    初始化/更新只读 skill 的脚本
├── .gitignore
├── examples/                          TaskSpec 样例
│   ├── parent-care.taskspec.json          父母关怀卡片（动态天气 + 拨号）
│   └── freeclip2-earbuds.taskspec.json    耳机桌面卡片（静态设备 + 音乐入口）
├── references/                        参考资料与本地接口示例
│   ├── chat-completions-api.md            chat-completions API 参考
│   └── test_api.sh                        本地接口调用示例
└── .agents/skills/harmony-card-generation/   外部只读 skill（禁止修改）
```

说明：

- `examples/*-request.json`：用 `taskspec_to_chat_completions.py -o` 生成的请求体产物，便于核对，可按需重新生成或删除。
- `__pycache__/`：Python 字节码缓存，已在 `.gitignore` 中忽略。

---

## 作业流

完整链路由三个中间模块串起来，重点看每一层的输入和输出。

1. **大模型 Agent：用户 Query -> TaskSpec**
   输入是用户自然语言需求，以及 Form 协议 / 只读 skill 参考规则；输出是 TaskSpec JSON。TaskSpec 需要包含 `card.requirements`、`dataModel`、`dataCapabilities`、`eventBindings`、`rules.dsl` 和 `cardSpec`，但不写具体布局树。结构以 [`taskspec.schema.json`](taskspec.schema.json) 为准，生成后使用 `validate_taskspec.py` 做 schema 与协议一致性校验。

2. **转换脚本：TaskSpec -> API request body**
   `taskspec_to_chat_completions.py` 读取 TaskSpec，把协议关键信息写入 `system` prompt，并把完整 TaskSpec 放入 `user` 消息，生成 OpenAI 兼容的 chat-completions 请求体。

3. **小模型 API：API request body -> DSL**
   小模型只负责根据 request body 生成一个 `genui` 代码块，内容恰好 3 行 JSONL。最终输出只有 DSL，不包含 CardSpec，不输出 `cardspec` 代码块，也不生成 DSL + CardSpec 的组合产物。请求模型后可用 `validate_generated_card.py` 校验 DSL 的行数、DataModel、root 尺寸和事件绑定一致性。

---

## TaskSpec 转 Chat Completions 请求体

`taskspec_to_chat_completions.py` 用于把 `*.taskspec.json` 文件转换成 OpenAI 兼容的 chat-completions 请求体。

生成的请求体包含两条消息：

- `system`：简要说明 TaskSpec 协议、小模型职责和 DSL 输出规则。
- `user`：TaskSpec JSON，以及一段简短的生成指令。

基础用法：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json
```

把请求体写入文件：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json -o request.json
```

指定模型：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json -o request.json --model glm-5.2
```

使用 `curl` 请求本地 chat-completions 接口：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json -o request.json --invoke --response-output response.json
```

使用自定义接口地址：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json -o request.json --endpoint http://127.0.0.1:4000/v1/chat/completions --invoke --response-output response.json
```

常用参数：

- `--model`：模型名称，默认值为 `glm-5.2`。
- `--endpoint`：chat-completions 接口地址，默认值为 `http://127.0.0.1:4000/v1/chat/completions`。
- `--raw-content`：在 `user` 消息中只放原始 TaskSpec JSON，不追加额外指令；`system` prompt 仍会保留。
- `--invoke`：使用 `curl` 把生成的请求体发送到 `--endpoint`。
- `--response-output`：把模型响应写入指定文件。

## 校验并提取模型生成的 DSL

请求模型后，可以校验并提取模型生成的 DSL：

```powershell
python validate_generated_card.py --response response.json --spec examples\parent-care.taskspec.json --out-dir generated --name parent-care
```

该脚本会：

- 拒绝包含 `cardspec` 代码块的输出。
- 提取唯一的 `genui` 代码块。
- 校验 JSONL 恰好 3 行、version、catalogId、surfaceId、组件扁平结构、root 尺寸、`updateDataModel.value` 与 TaskSpec 一致。
- 校验通过后保存提取出的 DSL；`cardSpec` 保持为 TaskSpec 内的端侧契约，不作为小模型输出。

---

## 项目硬约束

- 禁止修改 `.agents/skills/` 目录下的任何内容。
- `harmony-card-generation` skill 在本项目中视为外部只读依赖。
- 协议变更只能发生在项目自有文件中，例如 `TaskSpec.md`、`taskspec.schema.json`、`examples`、校验脚本或转换脚本。
- 如果现有 skill 文档与本项目的 TaskSpec 流程存在冲突，应在项目协议和适配脚本中解决，不要编辑 skill。

`validate_project_constraints.py` 会通过 git 状态检查 `.agents/skills/` 是否被改动；任何改动都会导致交付失败。
