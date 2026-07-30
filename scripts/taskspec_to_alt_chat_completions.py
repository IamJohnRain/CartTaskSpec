#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_ALT_NAME = "card.alt.txt"
DEFAULT_ASC_NAME = "card.asc.txt"
DEFAULT_REJECTED_ALT_NAME = "card.MiniMax-M3.alt.txt"
DEFAULT_REJECTED_ASC_NAME = "card.MiniMax-M3.asc.txt"
REQUIRED_TOP_LEVEL = {
    "userQuery",
    "size",
    "eventCandidates",
    "dataModelSchema",
    "assetCandidates",
}
ALLOWED_TOP_LEVEL = REQUIRED_TOP_LEVEL | {"presentationSlots"}
FORBIDDEN_EVENT_FIELDS = {
    "description",
    "eventRef",
    "id",
    "label",
    "note",
    "onClick",
    "required",
}


SYSTEM_PROMPT = """你是 A2UI 卡片规划模型。你负责根据 TaskSpec 同时生成 ALT（A2UI Layout Tree）和 ASC（A2UI Semantic Companion），不直接生成 GenUI DSL、CardSpec 或解释。

ALT 的职责：
- 描述组件类型、稳定节点 ID、父子层级、几何布局、排版和影响布局的视觉样式。
- 不保存 Text.content、Button.label、Image.src、Progress.value/total、Checkbox.select/group、onClick、表达式或 DataModel。
- TaskSpec 决定展示内容、数据、素材和事件；ALT 决定怎样布局；genui@0.7.0-alpha.7 profile 决定原生默认值。

输出契约：
- 只输出一个 <alt>...</alt> 段和紧随其后的一个 <asc>...</asc> 段，不使用 Markdown 代码围栏，不输出思考、解释、标题、总结或日志。
- <alt> 内直接从根节点开始且只输出一棵树；不输出 @alt 头、size、profile 或其他元信息。
- <asc> 使用与 ALT 相同的 Component node_id key=value 单行语法，只列出有语义补充的节点，顺序必须与 ALT 前序一致。
- 卡片尺寸由 TaskSpec.size 决定，根节点 box 必须与该尺寸对应；genui@0.7.0-alpha.7 profile 由编译器内部固定使用。
- 每层使用 2 个空格缩进，禁止 Tab。
- 每个节点一行：Component node_id key=value flag
- 组件只允许 Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack；Repeat 只作为列表模板的虚拟节点。
- 节点 ID 必须唯一，并使用 [A-Za-z_][A-Za-z0-9_-]*。优先使用 TaskSpec.presentationSlots 的 key；没有 presentationSlots 时，使用能与 schema 字段名稳定匹配的语义 ID。
- 不输出任何未挂载节点。

输出示例：
<alt>
Column root box=300x140 pad=12 gap=8 main=start cross=start radius=22 clip bg=#FFFFFFFF role=shell
  Row header box=276x24 main=between cross=center role=group
    Image title_icon size=20 fit=contain radius=6 role=asset
    Text title box=248x20 font=14/700 lines=1 role=title protect
  Progress battery_ring type=ring size=64 color=#FF0A59F7 role=primary
  Button primary_action box=96x34 font=14/500 chars=5 radius=17 role=action protect
</alt>
<asc>
Image title_icon asset=0
Text title bind=/data/title
Button primary_action label=立即查看 event=0
</asc>

属性语法：
- box=WIDTHxHEIGHT；size=N 是等宽高简写。
- pad/margin 使用 A、V/H 或 T/R/B/L。
- gap 是 Row/Column itemMargin 或 List space。
- main=start|center|end|between|around|evenly。
- cross：Row 使用 top|center|bottom；Column 使用 start|center|end。
- align 是 Stack 的 topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd。
- grow/shrink 表示 layoutWeight/flexShrink。
- Text：font=SIZE/WEIGHT、lines、overflow、text。
- Button：必须声明 font=SIZE/WEIGHT 和 chars=N；chars 是按全宽字符保守计算的最大可见字符数。
- Image：size 或 box、fit、ratio。
- Progress：type、size/box、color。
- Divider：axis=h|v、len、stroke、color，不使用 box 表达线条几何。
- Checkbox：box、shape、selected、unselected、mark=size/strokeWidth/strokeColor。
- appearance：radius、bg、fg、gradient、border、shadow、clip。
- role 推荐 shell/group/item/collection/title/primary/support/meta/status/metric/action/asset/selection/separator/background/overlay。
- protect 标记必须完整显示的标题、日期、时间、状态、CTA、主指标、价格/数量和用户明确要求字段。

画布和 root：
- 2x2：逻辑画布 140x140，root box=140x140、pad=12、radius=18、clip，内容区约 116x116。
- 2x4：逻辑画布 300x140，root box=300x140、pad=12、radius=22、clip，内容区约 276x116。
- root 必须是 Row、Column 或 Stack，并且必须有静态 bg 或 gradient。
- 背景层可以贴边，但可读内容必须留在安全区内。

原生尺寸能力：
- Row/Column/Stack 是自由容器；关键容器必须有明确可推导宽高。
- List 必须有明确视口，重复项必须有稳定高度；Repeat.visible 表示可见项数量，不保存集合路径。
- Text 的 box 只约束文本区域，不会缩放字体。
- Image 默认 aspectRatio=1、objectFit=cover；承担布局职责时必须声明 size，或声明完整 box 和 fit/ratio。
- Button 默认 padding=8vp/12vp、fontSize=16fp、fontWeight=500。Button 必须显式声明 font 和 chars；chars=floor((width-24)/fontSize)，实际标签字符数不得超过 chars。主 CTA 高度通常不小于 32vp。
- ring/eclipse/scaleRing Progress 必须正方形，优先使用 size=N。
- Divider 的长度和厚度必须通过 axis/len/stroke 表达。
- Checkbox 是外层 Row + 固定 20x20 控件 + 内部单行省略 Text。固有外层高度 48vp；控件 margin=2vp；标签前固定占用约 36vp。box 不能缩放内部控件，height 不得小于 48，width 不得小于 36。Checkbox 禁止 font、lines、overflow；mark.size 不得大于 20。
- 默认不要使用 Checkbox。2x2 禁止使用 Checkbox；2x4 默认最多一个。只有用户明确要求勾选、选择或布尔设置状态时才可使用；只展示状态时使用 Text/Row，表达动作时使用 Button。无法证明 48vp 高度和标签宽度预算成立时删除 Checkbox，不得缩小它。

布局质量：
- Row 横向预算：子项 width、左右 margin、父 padding 和 gap 总和不得超过父宽。
- Column 纵向预算：子项 height、上下 margin、父 padding 和 gap 总和不得超过父高。
- 使用 main=between|around|evenly 时禁止再写固定 gap。
- 普通流中禁止重叠；Stack 只用于背景、进度环、角标或明确叠加，不得遮挡 protect 节点。
- 固定间距只使用 2/4/6/8/10/12/14/16，优先 4/8/12/16；组间距大于组内距。
- 字号只使用 10/12/14/16/18/20/32/40，同一卡片控制在 3 档以内。
- 中文文本宽度约为 fontSize * 字符数；英文和数字约为 0.6 * fontSize * 字符数；垂直高度按 fontSize + 2~4 预算。
- protect Text 不使用 clip、ellipsis 或 marquee。
- 2x2 非模板默认最多 3 个主区域和 1 个动作；2x4 最多 4 个主区域和 2 个动作，但仍只服务一个主对象。
- 同一事实只由一个组件主承载；不通过增加同义标签、重复值或装饰组件填空。
- 连续超过 18vp 的空白必须服务媒体、进度、场景背景或热区。
- 布局放不下时依次：缩短弱文本、删除可选内容、降低到批准字号、拆行或改 Column、简化视觉、必要时才使用 2x4。不得靠裁剪或覆盖解决。

颜色与表面：
- ALT 只使用静态 #RRGGBB 或 #AARRGGBB，不输出颜色 token 名或动态颜色表达式。
- 常用颜色：主文字 #E5000000、次文字 #99000000、弱文字 #66000000、反白 #FFFFFFFF、主背景 #FFFFFFFF、次背景 #FFF1F3F5、弱背板 #0C000000、分隔线 #33000000、品牌色 #FF0A59F7、确认色 #FF64BB5C、警示色 #FFE84026、提醒色 #FFED6F21。
- 状态色只能服务真实状态；同一卡片只保留一个主场景色族。
- gradient 必须是单行紧凑 JSON，例如 gradient={\"direction\":\"RightBottom\",\"colors\":[[\"#FF0A59F7\",0],[\"#FF64BB5C\",1]]}。

TaskSpec 使用边界：
- userQuery 用于判断唯一服务对象、主问题、必需字段和动作存在性。
- dataModelSchema 用于判断字段类型、样例长度和布局容量，不要把所有 schema 字段都塞进卡片。
- eventCandidates 只说明潜在动作能力；ALT 只布局 action 节点，不输出 call、args 或 onClick。
- assetCandidates 只说明可用素材语义；ALT 只布局 Image 节点，不输出 src。
- presentationSlots 若存在，其 key 必须直接作为对应 ALT 节点 ID；source、eventCandidate、assetCandidate 等内容仍不得写进 ALT。

ASC 规则：
- ASC 是 ALT 的语义伴随信息，不是残差或补丁；不得输出版本、profile、origin、操作符或路径操作。
- ASC 节点必须映射到同类型、同 ID 的 ALT 节点；无补充信息的节点不输出。
- Text 使用 text=静态文案、bind=/数据路径，复杂表达式才使用 expr=完整表达式。
- Image 优先使用 asset=N 引用 assetCandidates；必要时使用 src、bind 或 expr。
- Progress 使用 value=/路径、total=/路径。
- Button 使用 label 和 event=N；Checkbox 使用 label、value、group、bind、event=N。
- event=N 引用 eventCandidates，禁止重复输出完整事件；asset=N 引用 assetCandidates，禁止重复资源路径。
- ASC 禁止 id、component、children、styles、尺寸、颜色、字体、圆角、间距和任何 DataModel 内容。
- DataModel 完全由 TaskSpec.dataModelSchema 的 sampleValue 递归生成。

下面给出 TaskSpec。只返回符合上述规则的 ALT+ASC 双段内容：
{{TASK_SPEC_JSON}}
"""


def load_task_spec(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"input path must be a TaskSpec JSON file: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("TaskSpec must be a JSON object")
    validate_task_spec(data)
    return data


def validate_task_spec(spec: dict[str, Any]) -> None:
    extra = sorted(set(spec) - ALLOWED_TOP_LEVEL)
    if extra:
        raise ValueError(
            "TaskSpec contains unsupported top-level field(s): "
            + ", ".join(repr(key) for key in extra)
        )
    missing = sorted(REQUIRED_TOP_LEVEL - set(spec))
    if missing:
        raise ValueError(
            "TaskSpec must contain top-level field(s): "
            + ", ".join(repr(key) for key in missing)
        )
    if not isinstance(spec["userQuery"], str) or not spec["userQuery"].strip():
        raise ValueError("TaskSpec.userQuery must be a non-empty string")
    if spec["size"] not in {"2x2", "2x4"}:
        raise ValueError("TaskSpec.size must be '2x2' or '2x4'")
    if not isinstance(spec["dataModelSchema"], dict):
        raise ValueError("TaskSpec.dataModelSchema must be an object")
    validate_data_model_schema(spec["dataModelSchema"], "/dataModelSchema")
    validate_event_candidates(spec["eventCandidates"])
    validate_asset_candidates(spec["assetCandidates"], spec["dataModelSchema"])
    slots = spec.get("presentationSlots")
    if slots is not None:
        validate_presentation_slots(slots)


def validate_data_model_schema(value: Any, location: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    if "sampleValue" in value:
        for key in ("type", "description", "sampleValue"):
            if key not in value:
                raise ValueError(f"{location} field schema must contain {key!r}")
        if not isinstance(value["type"], str) or not value["type"].strip():
            raise ValueError(f"{location}.type must be a non-empty string")
        if not isinstance(value["description"], str) or not value["description"].strip():
            raise ValueError(f"{location}.description must be a non-empty string")
        return
    if value.get("type") == "array" and isinstance(value.get("items"), dict):
        validate_data_model_schema(value["items"], f"{location}/items")
        return
    if value.get("type") == "object" and isinstance(value.get("properties"), dict):
        validate_data_model_schema(value["properties"], f"{location}/properties")
        return
    if is_field_schema(value):
        raise ValueError(f"{location} field schema must contain 'sampleValue'")
    for key, child in value.items():
        if key in {"properties", "items"} and isinstance(child, dict):
            validate_data_model_schema(child, f"{location}/{key}")
        elif isinstance(child, dict):
            validate_data_model_schema(child, f"{location}/{key}")


def is_field_schema(value: dict[str, Any]) -> bool:
    if "sampleValue" in value:
        return True
    return "type" in value and (
        "description" in value or "properties" in value or "items" in value
    )


def validate_event_candidates(value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError("TaskSpec.eventCandidates must be an array")
    for index, candidate in enumerate(value):
        location = f"TaskSpec.eventCandidates[{index}]"
        if not isinstance(candidate, dict):
            raise ValueError(f"{location} must be an object")
        forbidden = sorted(FORBIDDEN_EVENT_FIELDS & set(candidate))
        if forbidden:
            raise ValueError(f"{location} contains removed field(s): {', '.join(forbidden)}")
        call = candidate.get("call")
        if not isinstance(call, str) or not call.strip():
            raise ValueError(f"{location}.call must be a non-empty string")
        args = candidate.get("args", {})
        if args is not None and not isinstance(args, dict):
            raise ValueError(f"{location}.args must be an object when present")


def validate_asset_candidates(value: Any, data_model_schema: dict[str, Any]) -> None:
    if not isinstance(value, list):
        raise ValueError("TaskSpec.assetCandidates must be an array")
    for index, asset in enumerate(value):
        location = f"TaskSpec.assetCandidates[{index}]"
        if not isinstance(asset, dict):
            raise ValueError(f"{location} must be an object")
        src = asset.get("src")
        if not isinstance(src, str) or not src.strip():
            raise ValueError(f"{location}.src must be a non-empty string")
        description = asset.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{location}.description must be a non-empty string")
        bind_to = asset.get("bindTo")
        if bind_to is not None:
            if not isinstance(bind_to, str) or not bind_to.startswith("/"):
                raise ValueError(f"{location}.bindTo must be a JSON Pointer")
            if read_schema_sample(data_model_schema, bind_to) != src:
                raise ValueError(f"{location}.bindTo must resolve to the same src in dataModelSchema")


def validate_presentation_slots(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("TaskSpec.presentationSlots must be an object")
    for slot_id, slot in value.items():
        if not isinstance(slot_id, str) or not slot_id:
            raise ValueError("presentationSlots keys must be non-empty strings")
        if not isinstance(slot, dict):
            raise ValueError(f"presentationSlots.{slot_id} must be an object")
        source = slot.get("source")
        if source is not None and not isinstance(source, str):
            raise ValueError(f"presentationSlots.{slot_id}.source must be a string")
        for index_key in ("assetCandidate", "eventCandidate"):
            index = slot.get(index_key)
            if index is not None and (not isinstance(index, int) or index < 0):
                raise ValueError(f"presentationSlots.{slot_id}.{index_key} must be a non-negative integer")


def read_schema_sample(schema: Any, pointer: str) -> Any:
    target = read_pointer(schema, pointer)
    if isinstance(target, dict) and "sampleValue" in target:
        return target["sampleValue"]
    return target


def read_pointer(root: Any, pointer: str) -> Any:
    if pointer in {"", "/"}:
        return root
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    current = root
    for raw_part in pointer.strip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def canonical_task_spec_json(spec: dict[str, Any]) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=2)


def read_user_query(path: Path | None, spec: dict[str, Any]) -> str:
    if path is None:
        return str(spec["userQuery"]).strip()
    if not path.is_file():
        raise ValueError(f"user query path must be a text file: {path}")
    text = path.read_text(encoding="utf-8-sig").strip()
    return text or str(spec["userQuery"]).strip()


def read_alt(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"ALT answer file does not exist: {path}")
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError(f"ALT answer file is empty: {path}")
    if text.startswith("```"):
        raise ValueError("ALT answer must be raw ALT text without a Markdown code fence")
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line.startswith("@alt"):
        raise ValueError("ALT answer must start directly with the root node, without an @alt header")
    first_tokens = first_line.split()
    if len(first_tokens) < 2:
        raise ValueError("ALT answer must start with a root component and node ID")
    return text


def read_asc(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"ASC answer file does not exist: {path}")
    text = path.read_text(encoding="utf-8-sig").strip()
    for line_number, line in enumerate(text.splitlines(), 1):
        tokens = line.split()
        if len(tokens) < 3 or any(token.startswith(("styles=", "style=")) for token in tokens[2:]):
            raise ValueError(f"invalid ASC answer line {line_number}")
    return text


def format_assistant_answer(alt_answer: str, asc_answer: str) -> str:
    return f"<alt>\n{alt_answer}\n</alt>\n<asc>\n{asc_answer}\n</asc>"


def build_request(
    spec: dict[str, Any],
    user_query: str,
    alt_answer: str,
    asc_answer: str,
    rejected_response: str | None = None,
) -> dict[str, Any]:
    task_spec_json = canonical_task_spec_json(spec)
    messages: list[dict[str, str]] = [
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
            "content": "<think>\n\n</think>\n\n" + format_assistant_answer(alt_answer, asc_answer),
        },
    ]
    request: dict[str, Any] = {"messages": messages}
    if rejected_response is not None:
        request["rejected_response"] = rejected_response
    return request


def write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an ALT+ASC chat-completions training request from TaskSpec."
    )
    parser.add_argument("input_path", type=Path, help="Path to task.taskSpec.json.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write the generated request JSON to this file. Defaults to stdout.",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=Path,
        help="Optional original user query text file. Defaults to TaskSpec.userQuery.",
    )
    parser.add_argument(
        "-a",
        "--alt",
        type=Path,
        help=f"ALT assistant answer. Defaults to the sibling {DEFAULT_ALT_NAME}.",
    )
    parser.add_argument(
        "-s",
        "--asc",
        type=Path,
        help=f"ASC assistant answer. Defaults to the sibling {DEFAULT_ASC_NAME}.",
    )
    parser.add_argument(
        "--hfrl",
        action="store_true",
        help="Add a top-level rejected_response for HFRL training.",
    )
    parser.add_argument(
        "--rejected-alt",
        type=Path,
        help=f"Rejected ALT answer for --hfrl. Defaults to sibling {DEFAULT_REJECTED_ALT_NAME}.",
    )
    parser.add_argument(
        "--rejected-asc",
        type=Path,
        help=f"Rejected ASC answer for --hfrl. Defaults to sibling {DEFAULT_REJECTED_ASC_NAME}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        spec = load_task_spec(args.input_path)
        user_query = read_user_query(args.query, spec)
        alt_path = args.alt or args.input_path.parent / DEFAULT_ALT_NAME
        alt_answer = read_alt(alt_path)
        asc_path = args.asc or args.input_path.parent / DEFAULT_ASC_NAME
        asc_answer = read_asc(asc_path)

        rejected_response: str | None = None
        output_path = args.output
        if args.hfrl:
            rejected_path = args.rejected_alt or args.input_path.parent / DEFAULT_REJECTED_ALT_NAME
            rejected_asc_path = args.rejected_asc or args.input_path.parent / DEFAULT_REJECTED_ASC_NAME
            if not rejected_path.is_file() or not rejected_asc_path.is_file():
                print(
                    f"skip: rejected ALT/ASC file does not exist: {rejected_path}, {rejected_asc_path}",
                    file=sys.stderr,
                )
                return 0
            rejected_alt = read_alt(rejected_path)
            rejected_asc = read_asc(rejected_asc_path)
            rejected_response = (
                "<think>\n\n</think>\n\n"
                + format_assistant_answer(rejected_alt, rejected_asc)
            )
            if output_path is None:
                output_path = args.input_path.parent / "task.request.hfrl.json"

        request = build_request(spec, user_query, alt_answer, asc_answer, rejected_response)
        if output_path is not None:
            write_json(output_path, request)
        else:
            print(json.dumps(request, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
