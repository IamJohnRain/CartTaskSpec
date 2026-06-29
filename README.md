# CartTaskSpec

## 项目硬约束

- 禁止修改 `.agents/skills/` 目录下的任何内容。
- `harmony-card-generation` skill 在本项目中视为外部只读依赖。
- 协议变更只能发生在项目自有文件中，例如 `TaskSpec.md`、`taskspec.schema.json`、`examples`、校验脚本或转换脚本。
- 如果现有 skill 文档与本项目的 TaskSpec 流程存在冲突，应在项目协议和适配脚本中解决，不要编辑 skill。

交付前运行项目约束检查：

```powershell
python validate_project_constraints.py
```

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

请求模型后，可以校验并提取模型生成的 DSL：

```powershell
python validate_generated_card.py --response response.json --spec examples\parent-care.taskspec.json --out-dir generated --name parent-care
```
