# CartTaskSpec

CartTaskSpec 是一个面向 HarmonyOS A2UI Form 服务卡片的「大模型 + 小模型」协作生成协议。当前版本以 `.agents/skills/harmony-card-generation-datamodel-first` 为只读依据：大模型负责把用户 query 抽取成轻量 TaskSpec，小模型只负责根据 TaskSpec 和 system prompt 生成 `genui` DSL。

> 协议版本：`taskspec/v1`  
> 规则集：`harmony-form-datamodel-first-rules/v1`

---

## 项目介绍

本项目不把完整卡片设计交给大模型写死，也不让 TaskSpec 变成半成品 DSL。TaskSpec 只携带：

- 卡片场景、尺寸和必须表达的内容项。
- 小模型必须原样写入 `updateDataModel.value` 的 `dataModel.value`。
- 可点击动作，直接内联在 `card.requirements[type=action].onClick` 中。
- 允许使用的素材白名单。

DSL 硬规则不再写进 TaskSpec 的 `rules.dsl`，而是集中放在 `taskspec_to_chat_completions.py` 生成的 system prompt 中。最终输出只有小模型生成的 `genui` DSL，不输出 `cardspec`。

---

## 协议设计原则

1. **轻量，而不是半成品 DSL**  
   TaskSpec 不描述布局树、区域划分、组件嵌套、字号、颜色或宽高预算。

2. **DataModel-first**  
   新 skill 优先使用完整表达式 `{{ ... }}` 读取 DataModel，`{"path":"/..."}` / `formatString` 只作为模板相对路径、双向绑定或端侧对象绑定的兜底。

3. **DSL-only**  
   新 skill 原文仍支持 `genui + cardspec` 两个代码块，但本项目通过 system prompt 做适配：小模型只生成 `genui`，不得输出 `cardspec`。

4. **移除冗余模块**  
   TaskSpec 不再包含 `cardSpec`、`dataCapabilities`、顶层 `eventBindings`、`rules`、`validation` 或 `capabilityGap`。

5. **skill 只读**  
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
   输出轻量 TaskSpec。TaskSpec 包含 `card.requirements`、`dataModel` 和 `assets`；动作直接内联在 action requirement 的 `onClick` 中。

2. **转换脚本：TaskSpec -> API request body**  
   `taskspec_to_chat_completions.py` 读取 TaskSpec，把 DataModel-first DSL 规则写入 `system` prompt，并把完整 TaskSpec 放入 `user` 消息。

3. **小模型 API：API request body -> DSL**  
   小模型只输出一个 `genui` 代码块，内容恰好 3 行 JSONL。输出不包含 CardSpec，不生成 DSL + CardSpec 的组合产物。

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
