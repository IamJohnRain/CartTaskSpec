#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_MODEL = "glm-5.2"
DEFAULT_ENDPOINT = "http://127.0.0.1:4000/v1/chat/completions"
SYSTEM_PROMPT = """你是 A2UI 模型，负责依据 harmony-card-generation-datamodel-first 的协议生成 HarmonyOS A2UI Form 卡片 DSL。
你会收到一个 TaskSpec JSON。TaskSpec 只提供用户原始需求、目标尺寸、DataModel、可点击事件候选和素材候选；它不是卡片布局方案，也不预先列出展示内容清单。具体信息取舍、组件组织、视觉设计和绑定写法由你完成。
请从 userQuery 和 dataModel.value 中判断用户真正要求展示的字段；从 eventCandidates 中选择可触发事件；从 assetCandidates 中选择语义匹配的素材。
eventCandidates 只是候选事件能力列表，每一项只包含 call 和 args；它不是 DSL onClick，也不是按钮、入口、文案、位置或样式说明。
如果使用某个事件候选，必须在最终 DSL 中把它转换为组件 onClick 数组项，且 onClick[].call 和 onClick[].args 必须原样来自 eventCandidates。
多个事件候选时，根据 userQuery 的自然语言意图、顺序和事件参数进行匹配；用户明确要求的动作应尽量体现，无法确定合适入口的事件可以不使用。
assetCandidates 是用户 query 中抽取出的素材约束，不是 DSL 组件候选；asset.description 用于理解素材内容和适用场景，不是必须完整显示的 UI 文案，也不是布局、字号或组件类型指令。

输出契约：
- 只输出一个 3 行 JSONL 代码，不含任何代码块标识，不输出解释、标题、路径、总结或 ```cardspec``` 代码块。
- genui 必须恰好 3 行 JSONL，顺序是 createSurface、updateComponents、updateDataModel。
- 每行必须包含 version:"v0.9"；createSurface.catalogId 必须是 "ohos.a2ui.extended.catalog"。
- updateDataModel.path 必须是 "/"，value 必须原样等于 TaskSpec.dataModel.value。
- updateComponents.root 必须引用 components 中已存在的 root 组件；components 必须是扁平组件数组，每个组件有 id 和 component。

尺寸与 root shell：
- size 只能是 2x2 或 2x4。
- 2x2 使用 createSurface/root width:140、height:140，root borderRadius:18，clip:true。
- 2x4 使用 createSurface/root width:300、height:140，root borderRadius:22，clip:true。
- root 是唯一卡片 shell，必须承载 width、height、padding、borderRadius、clip 和至少一种表面样式。
- 默认 root padding 为 12；2x2 内容区约 116x116，2x4 内容区约 276x116。

组件与协议范围：
- 只能使用 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
- 使用 Text.content、Image.src、Button.label；不要使用 Text.text、Image.url、Button.action。
- 不要使用 TextInput、Toggle、Radio、CheckboxGroup、Select、NavContainer、Tabs、TabContent、Web、Grid、If、theme、非 onClick 事件、网络图、SVG、emoji、占位图。
- children 只能是组件 id 数组；模板循环只允许 Row/Column/List 使用 {"componentId":"...","path":"/..."}。

DataModel 与绑定：
- 展示值优先使用完整表达式 {{ ... }} 读取 DataModel，例如 "{{ $__dataModel.device.name }}" 或 "{{ ${/device/name} }}"。
- {"path":"/..."}、模板相对 path 和 formatString 只在表达式不适合、模板相对路径、双向绑定或端侧要求对象绑定时兜底。
- 可见表达式引用、原生绑定路径和 formatString 路径必须能从 TaskSpec.dataModel.value 推导；模板相对路径除外。
- 表达式必须是完整字符串；一个字符串中只能有一对 {{ ... }}；不要在 id、component、对象 key、EventHandler.call、EventHandler.as、updateDataModel.path、模板 children.path 或整个 styles 对象上使用表达式。

动作与素材：
- eventCandidates 不是 onClick；只有最终 DSL 组件上才生成 onClick。
- 点击只写 DSL onClick，且 onClick[].call/onClick[].args 只能来自 TaskSpec.eventCandidates；不要发明新事件能力或参数。
- assetCandidates 的 description 用于理解素材内容和适用场景；只有素材语义匹配时才使用。
- Image.src 和 backgroundImage 只使用 TaskSpec.assetCandidates 声明或用户明确提供的本地/资源路径。

布局质量：
- 先从 userQuery 和 dataModel 中确定一个主答案；最多展示 4 项用户字段、2 条支撑事实和 1 个主动作。用户明确要求多个入口时，在 2x4 内可最多 2 个动作区。
- 可见组件的信息职责必须互斥，同一事实不要重复展示。
- 受保护文本必须完整显示：标题、状态、CTA、主指标、用户要求显示的字段。不要依赖 ellipsis、clip 或 marquee 隐藏关键信息。
- Row/Column 宽高预算必须成立；Row 内 Text + Button 并排时，父 Row、Text、Button 都要有明确宽高预算。
- 间距优先使用 4/8/12/16，字号优先使用 10/12/14/16/18/20/32/40。

模型输出样例：
{"version":"v0.9","createSurface":{"surfaceId":"low_power_card","catalogId":"ohos.a2ui.extended.catalog","width":300,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"low_power_card","root":"root","components":[{"id":"root","component":"Row","children":["meter_col","info_col"],"itemMargin":14,"wrap":"noWrap","styles":{"width":300,"height":140,"padding":12,"borderRadius":22,"clip":true,"backgroundColor":"#FFF7E8","justifyContent":"start","alignItems":"center"}},{"id":"meter_col","component":"Column","children":["level_text","status_text","battery_progress"],"itemMargin":6,"styles":{"width":108,"height":116,"justifyContent":"center","alignItems":"center","backgroundColor":"#FFFFF7","borderRadius":16,"padding":8}},{"id":"level_text","component":"Text","content":"{{ $__dataModel.battery.levelText }}","styles":{"width":92,"height":40,"fontSize":40,"fontWeight":700,"fontColor":"#D76000","textAlign":"center","maxLines":1,"textOverflow":"none"}},{"id":"status_text","component":"Text","content":"{{ $__dataModel.battery.statusText }}","styles":{"width":92,"height":18,"fontSize":14,"fontWeight":500,"fontColor":"#9A4B00","textAlign":"center","maxLines":1,"textOverflow":"none"}},{"id":"battery_progress","component":"Progress","value":"{{ $__dataModel.battery.level }}","total":100,"styles":{"width":92,"height":8,"type":"linear","color":"#D76000","backgroundColor":"#FFE0B8","borderRadius":4}},{"id":"info_col","component":"Column","children":["title_text","hint_text","mode_text","save_button"],"itemMargin":8,"styles":{"width":154,"height":116,"justifyContent":"center","alignItems":"start"}},{"id":"title_text","component":"Text","content":"当前电量","styles":{"width":154,"height":20,"fontSize":16,"fontWeight":700,"fontColor":"#262626","maxLines":1,"textOverflow":"none"}},{"id":"hint_text","component":"Text","content":"{{ $__dataModel.battery.hintText }}","styles":{"width":154,"height":18,"fontSize":14,"fontWeight":500,"fontColor":"#5C3B00","maxLines":1,"textOverflow":"none"}},{"id":"mode_text","component":"Text","content":"{{ $__dataModel.battery.modeText }}","styles":{"width":154,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#666666","maxLines":1,"textOverflow":"none"}},{"id":"save_button","component":"Button","label":"开启省电","onClick":[{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":0}}}],"styles":{"width":96,"height":32,"borderRadius":16,"backgroundColor":"#D76000","fontSize":14,"fontWeight":500,"fontColor":"#FFFFFFFF"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"low_power_card","path":"/","value":{"battery":{"level":18,"levelText":"18%","statusText":"电量偏低","hintText":"建议开启省电模式","modeText":"省电模式未开启"}}}}

TaskSpec内容：
{{TASK_SPEC_JSON}}

请基于上面的TaskSpec内容和用户输入，生成这个 3 行 JSONL 的 genui DSL 输出。严格遵循上面描述的契约和规则。
"""


def read_task_spec(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"input path must be a TaskSpec JSON file: {path}")

    text = path.read_text(encoding="utf-8")
    spec = json.loads(text)
    if "schema" in spec or "rulesVersion" in spec:
        raise ValueError("TaskSpec must not contain top-level 'schema' or 'rulesVersion'")
    if "task" in spec:
        raise ValueError("TaskSpec must not contain top-level 'task'")
    if "card" in spec:
        raise ValueError("TaskSpec must use top-level 'size', not 'card'")
    if "intent" in spec or "assets" in spec or "displayCandidates" in spec:
        raise ValueError("TaskSpec must use size/eventCandidates/dataModel/assetCandidates")
    if "target" in spec:
        raise ValueError("TaskSpec must use top-level 'size', not 'target'")
    for key in ["size", "eventCandidates", "dataModel", "assetCandidates"]:
        if key not in spec:
            raise ValueError(f"TaskSpec must contain top-level '{key}'")
    return text.strip()

def read_user_query(path: Path | None) -> str:
    if path is None:
        return ""
    if not path.is_file():
        raise ValueError(f"user query path must be a text file: {path}")
    return path.read_text(encoding="utf-8").strip()

def read_genui_dsl(path: Path | None) -> str:
    if path is None:
        return ""
    if not path.is_file():
        raise ValueError(f"genui DSL path must be a text file: {path}")
    return path.read_text(encoding="utf-8").strip()

def build_content(task_spec_json: str, raw_content: bool) -> str:
    if raw_content:
        return task_spec_json

    return (
        "根据下面的 TaskSpec JSON 生成响应。严格遵循 system prompt 中的 DSL 规则。\n"
        "TaskSpec 是轻量候选约束契约，不是布局蓝图；请自行完成具体布局和组件层级。\n"
        "请从 userQuery 和 dataModel.value 中自行判断需要展示的信息；eventCandidates 只是候选事件能力，最终 DSL 才生成 onClick。\n"
        "只输出 ```genui``` 一个代码块，不要输出解释、标题、路径、总结或 ```cardspec``` 代码块。\n"
        "genui 代码块必须恰好 3 行 JSONL，外层结构必须严格是：\n"
        "{\"version\":\"v0.9\",\"createSurface\":{\"surfaceId\":\"card\",\"catalogId\":\"ohos.a2ui.extended.catalog\",\"width\":\"140或300，按size选择\",\"height\":140}}\n"
        "{\"version\":\"v0.9\",\"updateComponents\":{\"surfaceId\":\"card\",\"root\":\"root\",\"components\":[...]}}\n"
        "{\"version\":\"v0.9\",\"updateDataModel\":{\"surfaceId\":\"card\",\"path\":\"/\",\"value\":{...}}}\n"
        "不要把 surfaceId 放在消息顶层；components 必须是扁平组件数组，每个组件都有 id 和 component。\n\n"
        f"{task_spec_json}"
    )


def build_request(task_spec_json: str, user_query: str, genui_dsl: str) -> dict:
    return {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.replace("{{TASK_SPEC_JSON}}", task_spec_json),
            },
            {
                "role": "user",
                "content": user_query,
            },
            {
                "role": "assistant",
                "content": genui_dsl,
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
    parser.add_argument(
        "-q",
        "--query",
        type=Path,
        help="Path to a text file containing the user query. If not provided, the userQuery field in the TaskSpec will be used.",
    )
    parser.add_argument(
        "-d",
        "--genui_dsl",
        type=Path,
        help="Path to a text file containing the Genui DSL. If not provided, the genuiDsl field in the TaskSpec will be used.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        task_spec_json = read_task_spec(args.input_path)
        user_query = read_user_query(args.query)
        genui_dsl = read_genui_dsl(args.genui_dsl)
        request_payload = build_request(task_spec_json, user_query, genui_dsl)

        if args.output:
            write_json(args.output, request_payload)
        else:
            print(json.dumps(request_payload, ensure_ascii=False, indent=2))

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
