# CartTaskSpec

CartTaskSpec 是一个面向 HarmonyOS A2UI Form 服务卡片的「大模型 Agent + A2UI 模型」协作生成协议。大模型 Agent 负责把用户 query 抽取成轻量 TaskSpec，A2UI 模型负责根据 TaskSpec 和 system prompt 生成 `genui` DSL。

> 协议结构：`taskspec.schema.json`  
> DSL 规则：`taskspec_to_chat_completions.py` 的 system prompt

---

## 项目介绍

TaskSpec 是给 A2UI 模型的候选约束输入，只携带生成 DSL 必要的信息：

- `target`：目标尺寸、场景提示、风格提示和业务约束。
- `displayCandidates`：可显示的信息候选，包含 `label` 和给 A2UI 模型理解语义的 `description`。
- `eventCandidates`：可触发的事件候选，包含入口文案、动作说明和可直接使用的 `onClick`。
- A2UI 模型必须原样写入 `updateDataModel.value` 的 `dataModel.value`。
- `assetCandidates`：允许使用的素材候选白名单，必须描述素材内容和适用场景，便于 A2UI 模型判断是否使用。

DSL 硬规则集中放在 `taskspec_to_chat_completions.py` 生成的 system prompt 中。TaskSpec 本身不描述组件树、布局区域、字号、颜色或组件类型。

---

## 协议设计原则

1. **候选约束，而不是半成品 DSL**  
   TaskSpec 只抽取内容、事件、素材、数据和目标约束。

2. **DataModel-first**  
   新 skill 优先使用完整表达式 `{{ ... }}` 读取 DataModel，`{"path":"/..."}` / `formatString` 只作为模板相对路径、双向绑定或端侧对象绑定的兜底。

3. **DSL-only**  
   交付物是 `genui` DSL。

4. **skill 只读**  
   `.agents/skills/` 是外部只读依赖。协议、schema、样例、转换脚本和校验脚本可以演进，但不得修改 skill 内容。

---

## 项目结构

```text
CartTaskSpec/
├── README.md
├── TaskSpec.md
├── taskspec.schema.json
├── taskspec_to_chat_completions.py
├── validate_taskspec.py
├── validate_generated_card.py
├── validate_project_constraints.py
├── examples/
│   ├── parent-care.taskspec.json
│   └── freeclip2-earbuds.taskspec.json
├── references/
└── .agents/skills/harmony-card-generation-datamodel-first/  外部只读 skill，禁止修改
```

---

## 作业流

1. **大模型 Agent：用户 Query -> TaskSpec**  
   输出轻量 TaskSpec。TaskSpec 包含 `target`、`displayCandidates`、`eventCandidates`、`dataModel` 和 `assetCandidates`；动作直接内联在 event candidate 的 `onClick` 中。

2. **转换脚本：TaskSpec -> API request body**  
   `taskspec_to_chat_completions.py` 读取 TaskSpec，把 DataModel-first DSL 规则写入 `system` prompt，并把完整 TaskSpec 放入 `user` 消息。

3. **A2UI 模型 API：API request body -> DSL**  
   A2UI 模型输出一个 `genui` 代码块，内容恰好 3 行 JSONL。

---

## TaskSpec 转 Chat Completions 请求体

基础用法：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json
```

写入请求体文件：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json -o request.json
```

请求本地 chat-completions 接口：

```powershell
python taskspec_to_chat_completions.py examples\parent-care.taskspec.json -o request.json --invoke --response-output response.json
```

常用参数：

- `--model`：模型名称，默认值为 `glm-5.2`。
- `--endpoint`：chat-completions 接口地址，默认值为 `http://127.0.0.1:4000/v1/chat/completions`。
- `--raw-content`：在 `user` 消息中只放原始 TaskSpec JSON；`system` prompt 仍保留。
- `--invoke`：使用 `curl` 把生成的请求体发送到 `--endpoint`。
- `--response-output`：把模型响应写入指定文件。

---

## 校验

校验 TaskSpec：

```powershell
python validate_taskspec.py examples
```

校验项目硬约束：

```powershell
python validate_project_constraints.py
```

校验并提取模型生成的 DSL：

```powershell
python validate_generated_card.py --response response.json --spec examples\parent-care.taskspec.json --out-dir generated --name parent-care
```

`validate_generated_card.py` 会拒绝 `cardspec` 代码块，提取唯一 `genui` 代码块，并校验 JSONL 行数、组件引用、root 尺寸、DataModel 一致性和表达式/绑定路径。
