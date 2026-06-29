#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_MODEL = "glm-5.2"
DEFAULT_ENDPOINT = "http://127.0.0.1:4000/v1/chat/completions"
SYSTEM_PROMPT = """你是 HarmonyOS A2UI Form DSL 生成器。
你会收到一个 TaskSpec JSON。TaskSpec 只描述卡片目标、内容项、数据模型、事件、素材、CardSpec 和 DSL 约束；具体布局、组件层级和视觉设计由你完成。
只输出一个 ```genui``` 代码块，不输出解释、标题、路径、总结或 ```cardspec``` 代码块。
genui 必须恰好 3 行 JSONL，顺序是 createSurface、updateComponents、updateDataModel。
每行必须包含 version:"v0.9"；createSurface.catalogId 必须是 "ohos.a2ui.extended.catalog"。
updateDataModel.path 必须是 "/"，value 必须原样等于 TaskSpec.dataModel.value。
updateComponents.components 必须是扁平组件数组，每个组件有 id 和 component，并包含 id 为 root 的组件。
root 尺寸按 TaskSpec.card.size：2x2=160x160，2x4=320x160。
只能使用 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
使用 Text.content、Image.src、Button.label；不要使用 Text.text、Image.url、Button.action。
onClick 只使用 TaskSpec.eventBindings 中声明的 onClick。
绑定只使用 {"path":"/..."}、相对模板 path 或 formatString；不要使用表达式。"""


def read_task_spec(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"input path must be a TaskSpec JSON file: {path}")

    text = path.read_text(encoding="utf-8")
    spec = json.loads(text)
    if spec.get("schema") != "taskspec/v1":
        raise ValueError("TaskSpec schema must be taskspec/v1")
    return text.strip()


def build_content(task_spec_json: str, raw_content: bool) -> str:
    if raw_content:
        return task_spec_json

    return (
        "根据下面的 TaskSpec JSON 生成响应。严格遵循 task 字段和 rules.dsl。\n"
        "TaskSpec 是轻量需求契约，不是布局蓝图；请自行完成具体布局和组件层级。\n"
        "只输出 ```genui``` 一个代码块，不要输出解释、标题、路径、总结或 ```cardspec``` 代码块。\n"
        "TaskSpec.cardSpec 已由大模型生成，小模型不得生成、补全或修改 CardSpec。\n"
        "genui 代码块必须恰好 3 行 JSONL，外层结构必须严格是：\n"
        "{\"version\":\"v0.9\",\"createSurface\":{\"surfaceId\":\"card\",\"catalogId\":\"ohos.a2ui.extended.catalog\"}}\n"
        "{\"version\":\"v0.9\",\"updateComponents\":{\"surfaceId\":\"card\",\"components\":[...]}}\n"
        "{\"version\":\"v0.9\",\"updateDataModel\":{\"surfaceId\":\"card\",\"path\":\"/\",\"value\":{...}}}\n"
        "不要把 surfaceId 放在消息顶层；不要把 components 写成 root/components 字典；components 必须是扁平组件数组，每个组件都有 id 和 component。\n\n"
        f"{task_spec_json}"
    )


def build_request(task_spec_json: str, model: str, raw_content: bool) -> dict:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_content(task_spec_json, raw_content),
            },
        ],
    }


def write_json(path: Path, payload: dict | str) -> None:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")


def invoke_with_curl(endpoint: str, request_path: Path) -> str:
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--fail-with-body",
        "--location",
        endpoint,
        "--header",
        "Content-Type: application/json",
        "--data-binary",
        f"@{request_path}",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"curl failed with exit code {result.returncode}: {detail}")
    return result.stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert TaskSpec JSON into a chat-completions request body."
    )
    parser.add_argument("input_path", type=Path, help="Path to a *.taskspec.json file.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write the generated chat-completions request JSON to this file. Defaults to stdout.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name. Default: {DEFAULT_MODEL}")
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Chat completions endpoint. Default: {DEFAULT_ENDPOINT}",
    )
    parser.add_argument(
        "--raw-content",
        action="store_true",
        help="Use the raw TaskSpec JSON as the user message content without the extra instruction prefix.",
    )
    parser.add_argument(
        "--invoke",
        action="store_true",
        help="POST the generated request to --endpoint using curl.",
    )
    parser.add_argument(
        "--response-output",
        type=Path,
        help="When --invoke is used, write the response body to this file. Defaults to stdout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        task_spec_json = read_task_spec(args.input_path)
        request_payload = build_request(task_spec_json, args.model, args.raw_content)

        if args.output:
            write_json(args.output, request_payload)
        else:
            print(json.dumps(request_payload, ensure_ascii=False, indent=2))

        if args.invoke:
            request_path = args.output
            temporary_file = None
            if request_path is None:
                temporary_file = tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    suffix=".json",
                    delete=False,
                )
                try:
                    json.dump(request_payload, temporary_file, ensure_ascii=False, indent=2)
                    temporary_file.close()
                    request_path = Path(temporary_file.name)
                finally:
                    if not temporary_file.closed:
                        temporary_file.close()

            response = invoke_with_curl(args.endpoint, request_path)
            if args.response_output:
                args.response_output.write_text(response, encoding="utf-8")
            else:
                print(response)

            if temporary_file is not None:
                Path(temporary_file.name).unlink(missing_ok=True)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
