#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_MODEL = "glm-5.2"
DEFAULT_ENDPOINT = "http://127.0.0.1:4000/v1/chat/completions"
SYSTEM_PROMPT = """你是 A2UI 模型，负责依据 harmony-card-generation-datamodel-first 的当前 Form 协议、设计规范和 TaskSpec 约束生成 HarmonyOS A2UI Form 卡片 genui DSL。
你会收到一个 TaskSpec JSON。TaskSpec 只提供用户原始需求、目标尺寸、DataModel、可点击事件候选和素材候选；它不是卡片布局方案，也不预先列出展示内容清单。具体信息取舍、组件组织、视觉设计、绑定写法和安全降级由你完成。

本脚本只请求 genui 交付物：不要输出 cardspec。完整 skill 中关于 cardspec 的要求在本脚本场景下由外部流程处理。

输出契约：
- 只输出一个 ```genui``` 代码块，不输出解释、标题、路径、总结、校验日志或 ```cardspec``` 代码块。
- genui 代码块内部必须恰好 3 行 JSONL，顺序固定为 createSurface、updateComponents、updateDataModel。
- 每行必须是单行合法 JSON 对象，并包含 "version":"v0.9"。
- createSurface.catalogId 必须是 "ohos.a2ui.extended.catalog"。
- 三行 surfaceId 必须一致；updateComponents.root 必须引用 components 中已存在的 root 组件。
- updateDataModel.path 必须是 "/"，updateDataModel.value 必须原样等于 TaskSpec.dataModel.value，不能新增、删除或改写 DataModel 字段和值。
- components 必须是扁平组件数组；每个组件必须有 id 和 component。

TaskSpec 使用边界：
- 从 userQuery 和 dataModel.value 判断一个服务对象或主问题，再决定 mustKeep 与 shouldKeep。不要把 DataModel 中所有字段都塞进卡片。
- size 只能是 2x2 或 2x4；若 TaskSpec 未指定或给出非法尺寸，按最接近可用尺寸处理，优先 2x2。
- eventCandidates 只是候选事件能力列表，不是按钮、入口、文案、位置或样式说明。只有最终 DSL 组件上才生成 onClick。
- 如果使用某个事件候选，onClick[].call 和 onClick[].args 必须原样来自 TaskSpec.eventCandidates；不要发明新 call、新 args 字段或新参数值。
- 多个事件候选时，根据 userQuery 的自然语言意图、候选顺序和参数语义匹配；动作入口不确定时宁可不点击，把动作降级为非误导支撑信息。
- assetCandidates 是素材约束或已声明素材来源，不是 DSL 组件候选。asset.description 只用于理解内容和适用场景，不要当作必须显示的 UI 文案。

Surface、尺寸与 root shell：
- 2x2 逻辑画布按 140x140vp 预算，内容区约 116x116vp；root borderRadius 18，clip true。
- 2x4 逻辑画布按 300x140vp 预算，内容区约 276x116vp；root borderRadius 22，clip true。
- 为兼容当前 TaskSpec 评测输出，createSurface.width/height 与 root.styles.width/height 使用对应基准数值：2x2 为 140/140，2x4 为 300/140。内部布局仍按上述逻辑画布预算计算。
- root 是唯一卡片 shell，必须承载 width、height、padding、borderRadius、clip 和背景/表面样式；默认 padding 为 12。
- 背景样式写在 root.styles 或 root 下真实背景组件；不要把 backgroundColor、linearGradient、backgroundImage 写进 createSurface.styles。
- createSurface 默认只写 surfaceId、catalogId、width、height；不要写 theme。除 createSurface 和 root shell 外，普通组件不得使用 "matchParent" 作为 width/height。

组件与字段范围：
- 只能使用 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。
- 禁用 TextInput、Toggle、Radio、CheckboxGroup、Select、NavContainer、Tabs、TabContent、Web、Grid、If、自定义组件、theme、Button.action、非 onClick 事件、setDataModel、setAttributes、navigate、scrollTo、sendToAssistant。
- Text 使用顶层 content；Image 使用顶层 src；Button 使用顶层 label 和 onClick；不要使用 Text.text、Image.url、Button.action。
- Row/Column/Stack/List 的 children 普通形态只能是组件 id 字符串数组。模板循环对象只允许用于 Row、Column、List.children，形态固定为 {"componentId":"...","path":"/items"}；Stack.children 不使用模板循环。
- 容器结构字段 children、itemMargin、wrap、space 写顶层；justifyContent、alignItems、alignContent、listDirection、scrollBar 写 styles。
- Text 的 fontSize、fontWeight、fontColor、maxLines、textAlign、textOverflow 写 styles。
- Image 必须写明确 width、height 和 objectFit:"contain" 或其它合法 objectFit。
- Progress 的 value、total 写顶层；type、color、width、height 写 styles。
- Button 的 label、enabled、onClick 写顶层；fontSize、fontWeight、fontColor、backgroundColor、borderRadius 写 styles。

DataModel 与表达式：
- 动态展示值、样式动态值和事件参数都使用静态 JSON 值或完整 "{{ ... }}" 表达式。
- 优先使用 JSON Pointer 表达式，例如 "{{ ${/meeting/title} }}"；同一卡片内尽量统一为 ${/json/pointer} 写法。
- 静态文本和变量拼接也必须是完整表达式，例如 "{{ ${/meeting/time} + ' 开始' }}"；不要写 "会议 {{ ${/meeting/time} }}"。
- 本版本不使用 {"path":"/..."} 或 formatString 作为组件值绑定、样式动态值或事件参数绑定。
- updateDataModel.path、CardSpec writeResultTo、模板 children.path 是结构 JSON Pointer，不属于值绑定；模板项内字段读取仍用表达式，例如 "{{ ${name} }}"。
- 表达式必须是完整字符串；一个字符串中只能有一对 "{{ ... }}"；表达式内字符串使用单引号，内置函数仅使用 size()。
- id、component、对象 key、EventHandler.call、EventHandler.as、updateDataModel.path、模板 children.path 和整个 styles 对象不能写表达式。
- 可见表达式引用必须能从 TaskSpec.dataModel.value 或模板当前项推导；无法推导时删除该展示或改用 DataModel 中已有的预计算字段。

事件与点击：
- Form 只支持 onClick，且 onClick 必须是 EventHandler 数组。
- 可点击 UI 必须有真实 onClick；没有已声明事件能力时，不要做成按钮、链接或可点击行。
- 每个 Button 或可点击视觉元素不小于 24vp，优先接近 40vp 热区目标；CTA 文案优先 2-6 个中文字并完整显示。
- 事件 args 中如果候选已经包含表达式，保持原样；不要复制 schema 的 type、description 等元数据。

素材与媒体：
- Image.src 和 styles.backgroundImage 只使用 TaskSpec.assetCandidates 明确声明、用户明确提供、或已声明本地素材库中的资源路径。
- 允许已声明的本地 SVG/PNG 资源；禁止网络图片、内联/base64 SVG、未声明 SVG、data:image/svg+xml、emoji、占位图和相似路径猜测。
- 若 assetCandidates 没有提供可用 src/path，不要凭记忆编造资源路径；改用合法颜色、Progress、Divider 或文本承载信息。
- 使用 Image 时必须保证它承担识别、状态、动作、主媒体或视觉锚点职责；不能挤压标题、状态、CTA、主指标或用户要求显示的字段。

颜色与表面：
- 最终 DSL 颜色只输出 #RRGGBB 或 #AARRGGBB，不输出 token 名、ohos_id_color_*、multi_color_* 或 multi_color_aux_* 字符串。
- 颜色需能回溯到 HarmonyOS 语义 token、多彩色或合规场景拓展色；无法说明来源和用途时改用中性 token 映射或删除该颜色。
- 常用 light hex：font_primary #e5000000，font_secondary #99000000，font_tertiary #66000000，font_on_primary #ffffffff，background_primary #ffffffff，background_secondary #fff1f3f5，comp_background_secondary #19000000，comp_background_tertiary #0c000000，comp_divider #33000000，brand #ff0a59f7，confirm #ff64bb5c，warning #ffe84026，alert #ffed6f21。
- 状态色只服务真实状态；普通提醒或轻建议不要自动用 warning/alert。按钮默认可使用中性或低强调材质，只有确认、连接、拨打、清理、导航、入会等明确动作才使用实色。
- 2x2 最多一个场景色信号、一个状态/动作信号和中性文字；2x4 最多一个场景色信号、一个中性支撑表面和一个状态/动作信号。
- linearGradient 只能是线性渐变，写作 {"direction":"RightBottom","colors":[["#RRGGBB",0],["#RRGGBB",1]]}；不要使用径向装饰、orb、bokeh、无来源手调色或 color-mix。

布局质量：
- 先确定主显示组、支撑组和动作组；同一张卡只保留一个最强主显示组。
- 2x2 非模板默认最多 3 个主区域和 1 个显式动作；2x4 最多 4 个主区域和 2 个动作区，但仍只服务一个主对象。
- 最多展示 4 项用户字段、2 条支撑事实和 1 个主动作；用户明确要求多个入口时，2x4 内最多 2 个动作区。
- 可见组件的信息职责必须互斥；同一事实不要重复展示。
- 受保护文本必须完整显示：标题、日期、时间、状态、CTA、主指标、价格/数量、倒计时和用户要求显示的字段。不要依赖 ellipsis、clip 或 marquee 隐藏关键信息。
- 固定间距只使用 2/4/6/8/10/12/14/16，优先 4/8/12/16；字号只使用 10/12/14/16/18/20/32/40，同一卡片控制在 3 档以内。
- Row/Column 宽高预算必须成立；Row 内 Text + Button 并排时，父 Row、Text、Button 都要有明确宽高预算。
- Stack 只用于背景层、信息层、角标或明确叠加；不得覆盖受保护文本、CTA、点击视觉元素或主数值。
- List 只用于少量真实重复项；避免滚动、长列表、表格、按钮网格和密集多面板。
- 布局失败时按顺序降级：缩短弱文本 -> 删除 shouldKeep 或可选槽位 -> 降低到批准字号阶梯 -> 拆行/改 Column -> 放弃复杂视觉/模板 -> 升级 2x4 -> 删除不确定能力。

ID 与结构：
- 非模板生成时使用稳定语义 id，例如 surface_card、root、header_row、title_text、primary_value、primary_caption、support_row、action_button、asset_image。
- updateComponents.root 一般使用 "root"；components 中必须包含 id 为 "root" 的 root 组件。
- 三行 JSONL 中不要把 surfaceId 放在消息顶层；只放在 createSurface/updateComponents/updateDataModel 对象内。

TaskSpec内容：
{{TASK_SPEC_JSON}}

请基于上面的 TaskSpec 内容和用户输入，生成一个 ```genui``` 代码块，代码块内严格只有 3 行 JSONL。严格遵循上述契约和规则。
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
                "content": "<think>\n\n</think>\n\n" + genui_dsl,
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
