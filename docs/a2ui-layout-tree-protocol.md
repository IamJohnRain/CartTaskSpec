# ALT（A2UI Layout Tree）协议

## 1. 目标

ALT 是面向 A2UI Form 卡片的紧凑布局树协议。它用于：

- 作为小模型从 TaskSpec 生成布局的训练目标；
- 将 A2UI GenUI DSL 中的可达组件图抽取为规范化布局树，并将节点语义抽离为 ASC；
- 将 ALT、ASC 与 TaskSpec 合并，恢复规范化的三行 GenUI JSONL；
- 在生成 DSL 前完成尺寸预算、组件能力和遮挡风险校验。

ALT 只描述组件类型、稳定节点 ID、父子层级、几何布局、排版和影响布局的视觉样式。ALT 不保存可见文案、DataModel 表达式、事件处理器、素材路径或运行时状态。业务语义由 TaskSpec 提供，原生默认行为由版本化 GenUI profile 提供。

ALT 保持纯布局；独立的 ASC（A2UI Semantic Companion，A2UI 语义伴随信息）按节点补充内容、绑定、素材和事件。ASC 不是残差或补丁，不比较基础 DSL，也不保存操作符、样式或 DataModel。

## 2. 文件与编码

- 默认文件名：`card.alt.txt`
- 默认语义伴随文件名：`card.asc.txt`
- 编码：UTF-8
- 换行：LF 或 CRLF 均可，规范化输出使用 LF
- 缩进：每层 2 个空格，禁止 Tab
- 一个非空行只能声明一个节点
- 规范化文件不输出注释和空属性

## 3. 文件结构

ALT 文件只包含一棵组件树，并直接从根节点开始：

```text
Column root box=300x140 pad=12 gap=8 main=start cross=start radius=22 clip bg=#FFFFFFFF role=shell
  Row header box=276x24 main=between cross=center role=group
    Image title_icon size=20 fit=contain radius=6 role=asset
    Text title box=248x20 font=14/700 lines=1 role=title protect
  Progress battery_ring type=ring size=64 color=#FF0A59F7 role=primary
  Button primary_action box=96x34 font=14/500 chars=5 radius=17 role=action protect
```

ALT v0.1 的解析器和转换器内部固定使用 `genui@0.7.0-alpha.7` 能力 profile，这些元信息不写入训练文本。`t2d` 以 TaskSpec 的 `size` 为唯一尺寸来源，`d2t` 以 DSL 的 `createSurface` 尺寸为来源。`2x2` 的逻辑画布为 `140x140vp`，root 圆角为 `18vp`；`2x4` 的逻辑画布为 `300x140vp`，root 圆角为 `22vp`。root 默认安全区为 `12vp`。

## 4. 语法

简化语法如下：

```text
document  ::= node newline*
node      ::= indent component id (space property)*
property  ::= flag | key "=" value
indent    ::= ("  ")*
component ::= "Text" | "Image" | "Divider" | "Progress" | "Button"
            | "Checkbox" | "Row" | "Column" | "List" | "Stack" | "Repeat"
id        ::= [A-Za-z_][A-Za-z0-9_-]*
flag      ::= "clip" | "protect"
```

属性值中不包含空格时不加引号。对象或数组使用单行紧凑 JSON，例如：

```text
gradient={"direction":"RightBottom","colors":[["#FF317AF7",0],["#FF64BB5C",1]]}
```

节点属性规范顺序为：

1. 几何：`box`、`size`、`pad`、`margin`
2. 布局流：`gap`、`main`、`cross`、`align`、`wrap`、`grow`、`shrink`
3. 组件特有排版或媒体属性
4. 外观：背景、前景、边框、圆角、阴影和裁剪
5. 语义：`role`、`protect`

解析器可以接受不同顺序，但规范化序列化必须使用固定顺序。

## 5. 通用属性

| ALT 属性 | DSL 来源/目标 | 说明 |
| --- | --- | --- |
| `box=WxH` | `styles.width/height` | 节点的外层布局占位；`auto` 表示不输出该轴尺寸 |
| `size=N` | 相同 width/height | 正方形 Image 或环形 Progress 的简写 |
| `pad=A` | `styles.padding` | 四边相同 |
| `pad=V/H` | `styles.padding` | 垂直/水平 |
| `pad=T/R/B/L` | `styles.padding` | 上/右/下/左 |
| `margin=...` | `styles.margin` | 与 padding 相同的简写规则 |
| `gap=N` | `itemMargin` 或 List `space` | 相邻子节点间距 |
| `main=...` | `styles.justifyContent` | `start/center/end/between/around/evenly` |
| `cross=...` | `styles.alignItems` | Row 用 `top/center/bottom`，Column 用 `start/center/end` |
| `align=...` | `styles.alignContent` | Stack 九宫格对齐 |
| `wrap` | `wrap` | `noWrap` 或 `wrap` |
| `grow=N` | `styles.layoutWeight` | 剩余空间权重 |
| `shrink=N` | `styles.flexShrink` | 收缩权重 |
| `radius=N` | `styles.borderRadius` | 圆角 |
| `bg=COLOR` | `styles.backgroundColor` | 静态背景色 |
| `fg=COLOR` | `styles.fontColor` | 静态前景色 |
| `gradient=JSON` | `styles.linearGradient` | 静态线性渐变 |
| `border=W/COLOR` | `styles.borderWidth/borderColor` | 边框宽度和颜色 |
| `shadow=JSON` | `styles.shadow` | 静态阴影 |
| `clip` | `styles.clip: true` | 裁切子内容 |
| `role=...` | ALT 元数据 | 不写入 DSL，用于训练和校验 |
| `protect` | ALT 元数据 | 受保护文本或动作不得截断、遮挡 |

当 `main=between/around/evenly` 时，不得同时声明固定 `gap`。GenUI 对应的 `spaceBetween/spaceAround/spaceEvenly` 会使 Row/Column 的固定 `itemMargin` 失去实际布局作用。

## 6. 组件属性与尺寸能力

尺寸能力由 profile 决定，不需要模型在每个节点重复输出 `sizeMode`。

| 组件 | 尺寸模式 | ALT 约束 |
| --- | --- | --- |
| Row/Column/Stack | `free-box` | 关键容器必须有可推导宽高 |
| List | `viewport-box` | List 需要明确视口，重复项需要稳定高度 |
| Text | `content-box` | box 约束文本区域，不缩放字体 |
| Image | `ratio-box` | 使用 `size=N`，或同时给出 box 与 fit/ratio |
| Button | `intrinsic-min` | box 不得小于字体和默认 padding 推导的固有尺寸 |
| Progress | `type-dependent` | ring 类必须正方形；linear/capsule 使用普通 box |
| Divider | `axis-dependent` | 使用 axis/len/stroke，不使用普通 box 表达线条几何 |
| Checkbox | `fixed-inner-composite` | 外层占位与内部固定控件必须分别理解 |

### 6.1 Text

```text
Text title box=116x20 font=14/700 lines=1 overflow=none text=start fg=#E5000000 role=title protect
```

| 属性 | 含义 |
| --- | --- |
| `font=SIZE/WEIGHT` | 字号与字重；也允许只写字号 |
| `lines=N` | 最大行数 |
| `overflow=none/clip/ellipsis/marquee` | 溢出策略 |
| `text=start/center/end/justify` | 文本对齐 |

`protect` Text 不得使用 `clip`、`ellipsis` 或 `marquee` 隐藏内容。

### 6.2 Image

```text
Image icon size=48 fit=contain role=asset
Image cover box=120x72 fit=cover ratio=1.667 role=asset
```

Image profile 默认 `aspectRatio=1`、`objectFit=cover`。承担布局职责的 Image 必须有明确尺寸。`size=N` 表示相同的 width 和 height。

### 6.3 Button

```text
Button primary_action box=96x34 font=14/500 chars=5 radius=17 bg=#19000000 role=action protect
```

GenUI profile 默认使用 `padding: 8vp 12vp`、`fontSize: 16fp`、`fontWeight: 500`。Button 必须显式声明 `font=SIZE/WEIGHT` 和 `chars=N`。`chars` 是按全宽字符保守计算的最大可见字符数：`floor((width - 24) / fontSize)`。实际标签长度不得超过 `chars`；主 CTA 高度不得低于 `max(32, fontSize + 16)`。ALT 不保存按钮标签和 `onClick`，这些语义进入 ASC。

### 6.4 Progress

```text
Progress battery type=ring size=64 color=#FF0A59F7 role=primary
Progress usage type=linear box=180x8 color=#FF0A59F7 role=metric
```

| 属性 | 含义 |
| --- | --- |
| `type` | `linear/ring/eclipse/scaleRing/capsule` |
| `color` | 静态进度色 |

`ring`、`eclipse`、`scaleRing` 必须使用相同 width/height，规范化输出优先使用 `size=N`。

### 6.5 Divider

```text
Divider separator axis=h len=276 stroke=1px color=#33000000 role=separator
Divider separator axis=v len=72 stroke=1px color=#33000000 role=separator
```

`axis=h` 时 `len` 映射到 width，`stroke` 决定厚度；`axis=v` 时 `len` 映射到 height。若 DSL 显式提供厚度轴尺寸，该尺寸优先于 `strokeWidth`。

### 6.6 Checkbox

Checkbox 是复合组件：外层为 Row，内部包含固定 Checkbox 和内部 Text。`genui@0.7.0-alpha.7` profile 固定：

```text
intrinsicHeight=48
controlSize=20x20
controlMargin=2
labelGap=12
labelLines=1
labelOverflow=ellipsis
labelGrow=1
```

ALT 示例：

```text
Checkbox accept_terms box=132x48 shape=rounded_square selected=#FF64BB5C unselected=#33000000 mark=10/2/#FFFFFFFF role=selection protect
```

约束：

- `box` 表示外层布局占位，不能用来缩放内部 `20x20vp` 控件；
- 默认按 `48vp` 高度参与父 Column/Row 预算；小于 48 时报告裁切风险；
- 标签前固定横向开销约为 `20 + 2 + 2 + 12 = 36vp`；
- `protect` 标签估算宽度必须小于等于 `checkboxWidth - 36 - horizontalPadding`；
- Checkbox 不接受 ALT `font`、`lines`、`overflow`，因为这些属性不能可靠控制内部 Text；
- `mark` 格式为 `size/strokeWidth/strokeColor`，它只控制勾形；`mark.size > 20` 报告裁切风险。

模型生成规则比转换规则更严格：`2x2` 默认禁止 Checkbox，`2x4` 默认最多一个；只有用户明确要求勾选、选择或布尔设置时才使用。只展示状态时优先使用 Text/Row，表达动作时优先使用 Button。DSL 转换时仍可忠实抽取和恢复既有 Checkbox。

### 6.7 Repeat

`Repeat` 是 ALT 虚拟节点，不写入 GenUI components。它表达重复项模板的结构和可见数量，不保存集合路径：

```text
List schedule_list box=276x72 gap=6 direction=vertical role=collection
  Repeat schedule_items visible=3 role=collection
    Row schedule_item box=276x20 gap=6 cross=center role=item
      Text item_time box=44x18 font=12/500 lines=1 role=meta protect
      Text item_title box=226x18 font=12/400 lines=1 role=primary protect
```

| 属性 | 含义 |
| --- | --- |
| `visible=N` | 用于高度或宽度预算的可见重复项数量 |

集合来源必须由 TaskSpec `presentationSlots` 提供。没有集合槽位时，`ALT + TaskSpec -> DSL` 只能进行降级推断。

## 7. role 与 protect

`role` 只用于布局训练和验证，不导出到 GenUI DSL。推荐值：

```text
shell group item collection title primary support meta status metric action asset selection separator background overlay
```

以下节点默认属于受保护内容：标题、日期、时间、状态、CTA、主指标、倒计时、价格/数量，以及用户明确要求显示的字段。规范化抽取器可以依据稳定 ID 和组件类型补充 `role`、`protect`。

## 8. TaskSpec 展示槽位

ALT 不保存内容、绑定、事件和素材。TaskSpec 继续保持现有格式；若已有可选 `presentationSlots`，基础编译器优先使用它，否则使用稳定 ID、schema、事件和素材候选进行确定性降级：

```json
{
  "presentationSlots": {
    "title": {
      "kind": "text",
      "source": "/data/calendar/title"
    },
    "schedule_list": {
      "kind": "collection",
      "source": "/data/calendar/items"
    },
    "item_time": {
      "kind": "text",
      "source": "dtStart"
    },
    "schedule_icon": {
      "kind": "image",
      "assetCandidate": 0
    },
    "primary_action": {
      "kind": "action",
      "label": "立即查看",
      "eventCandidate": 0
    }
  }
}
```

ALT 节点 ID 与 `presentationSlots` key 相同。槽位属于 TaskSpec，不属于 ALT。

未提供 `presentationSlots` 时，转换器按以下顺序降级：

1. 用稳定节点 ID 与 schema 字段名匹配；
2. 用节点 role 与字段类型匹配；
3. Image 按 ID、素材文件名和 description 匹配 assetCandidates；
4. Button 使用第一个可用事件候选，并生成最短非误导标签；
5. 无法匹配的 Text 使用由节点 ID 生成的静态短标签。

所有降级必须输出控制台警告。节点的确定语义由 ASC 补充，因此不需要修改 TaskSpec。

### 8.1 ASC 语义伴随信息

`card.asc.txt` 使用与 ALT 相同的单行语法，只输出存在语义信息的节点，并严格遵循 ALT 前序顺序：

```text
Image battery_icon asset=0
Text title_text text=当前电量
Text primary_value bind=/battery/levelText
Progress battery_progress value=/battery/levelValue total=/battery/levelTotal
Button primary_action label=立即查看 event=0
```

每行仍为 `Component node_id key=value`。component 与 node_id 必须映射到同类型、同 ID 的 ALT 节点。无语义补充的容器不输出，因此 ASC 不是另一棵重复布局树。

- Text：`text`、`bind`，复杂表达式使用 `expr`；
- Image：优先用 `asset=N` 引用 `assetCandidates`，必要时使用 `src`、`bind` 或 `expr`；
- Progress：`value`、`total`；
- Button：`label`、`event=N`；
- Checkbox：`label`、`value`、`group`、`bind`、`event=N`；
- `event=N` 引用 `eventCandidates`，不得重复完整事件；
- ASC 禁止 `id`、`component`、`children`、`styles`、布局/视觉字段和 DataModel。

ASC 文件不携带版本、profile、origin 或其他元信息。协议版本和 GenUI profile 属于转换器实现契约，而不是训练内容。

## 9. DSL 到 ALT 与 ASC

抽取流程：

1. 解析三行 GenUI JSONL；
2. 校验 `createSurface`、`updateComponents` 和 `updateDataModel`；
3. 从 `updateComponents.root` 开始遍历组件引用图；
4. 只输出从 root 可达的组件；
5. 检测缺失引用、环、多父节点和重复 ID；
6. 去除 content、label、src、value、total、select、group、enabled、onClick 和 DataModel，使 ALT 保持纯布局；
7. 将 DSL 字段归一化为 ALT 属性；
8. 从每个可达组件抽取非布局语义，压缩为 ASC 节点属性；
9. 按固定属性顺序输出 ALT 和 ASC 文本。

未挂载组件不属于规范化 DSL；抽取时发现未挂载组件必须报错，不进入 ALT 或 ASC。

## 10. ALT、ASC 与 TaskSpec 到 DSL

编译流程：

1. 解析 ALT 为规范 AST；
2. 加载 TaskSpec，并生成 sample DataModel；
3. 应用转换器内部固定的 GenUI profile；
4. 检查 root、画布、安全区、Row/Column 预算和组件尺寸能力并输出诊断；
5. 通过 `presentationSlots` 或降级匹配补充内容、绑定、素材和事件；
6. 将 `Repeat` 编译为 `{ "componentId": "...", "path": "..." }`；
7. 按节点 ID 将 ASC 语义合并到 ALT 组件；
8. 从 TaskSpec `sampleValue` 递归生成 DataModel，输出规范化的三行 JSONL。

编译器只输出 ALT 显式声明的样式覆盖。profile 默认值用于预算和验证，不应为了“看起来完整”而重复写回 DSL。

## 11. 布局验证

至少执行以下检查：

- root 尺寸、padding、圆角、clip 和背景；
- Row 横向预算与 Column 纵向预算；
- 子项 margin、父 padding 和 gap 全部计入预算；
- 普通流中禁止重叠，Stack 中叠加不得遮挡 protect 节点；
- Text 字号、行数和宽度能够容纳受保护内容；
- Button 按原生 padding/font 计算固有最小尺寸；
- Button 必须声明 `font` 和 `chars`，实际标签不得超过容量；
- Checkbox 按固定内部控件和 48vp 固有高度计算；
- Divider 按方向区分长度和厚度；
- 环形 Progress 等宽高；
- Image 的尺寸、ratio 和 fit 不冲突；
- `main=between/around/evenly` 与固定 gap 不同时存在；
- 没有无语义的连续 `>18vp` 空洞。

警告和错误属于转换日志或独立诊断结果，不写入 ALT 训练正文。

## 12. 可逆性约定

- `TaskSpec + ALT + ASC -> DSL` 的“完全还原”正式定义为规范化 DSL 等价；
- 样式、内容、绑定、素材、事件、DataModel、组件类型、节点 ID 和挂载层级必须语义一致；
- 组件数组按 ALT 前序规范化，不保留无效未挂载组件；
- padding 数组/对象等同义 JSON 表达统一为转换器规定的规范形式；
- JSON 对象键顺序、空白和换行不属于等价性要求；
- TaskSpec 无法推导被引用字段的 DataModel 初值时必须报错，不能放入 ASC 兜底；
- 不支持的组件、未知样式或无法证明成立的布局必须报错，不得伪造近似组件。

## 13. 批量转换工具

转换器位于 `scripts/alt_converter.py`。`-o` 指向数据集目录，该目录的每个直接子目录视为一个 Case。

DSL 转 ALT 与 ASC：

```powershell
python scripts/alt_converter.py `
  -o references/datasets `
  --mode d2t
```

ALT、ASC 与 TaskSpec 转 DSL：

```powershell
python scripts/alt_converter.py `
  -o references/datasets `
  --mode t2d
```

完整参数：

| 参数 | 必需 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `-o DATASET_DIR` | 是 | 无 | 数据集目录 |
| `--mode d2t/t2d` | 是 | 无 | 转换方向 |
| `--dsl_name` | 否 | `card.dsl.jsonl` | Case 内 DSL 文件名 |
| `--alt_name` | 否 | `card.alt.txt` | Case 内 ALT 文件名 |
| `--asc_name` | 否 | `card.asc.txt` | Case 内 ASC 语义伴随文件名 |
| `--layout_report_name` | 否 | `card.layout-report.txt` | `t2d` 输出的 JSON 布局检测报告文件名 |
| `--taskspec_name` | 否 | `task.taskSpec.json` | Case 内 TaskSpec 文件名 |

`d2t` 会覆盖同名 ALT 和 ASC；`t2d` 会读取两者并覆盖同名 DSL，同时输出布局报告。TaskSpec、ALT、ASC 都是反向转换的必需输入。写入使用临时文件替换，单个 Case 失败不会阻止其余 Case 继续处理，进程在存在失败 Case 时返回非零退出码。

布局报告只记录静态检测结果，不修改 ALT、ASC、DSL 或 GenUI 组件默认参数。报告内容是 JSON，扩展名保留为 `.txt`，包含 Case、尺寸、输入输出文件、检测状态、问题数量以及按节点列出的稳定问题代码、严重级别、组件类型和说明。没有发现问题时仍输出报告，`status` 为 `pass` 且 `issues` 为空数组。存在布局问题不会阻止非严格模式生成 DSL。

控制台日志格式：

```text
[2026-07-30 14:50:33] [INFO] [3/21] [Case-01-low-power-003] START
[2026-07-30 14:50:33] [WARNING] [3/21] [Case-01-low-power-003] ...
[2026-07-30 14:50:33] [INFO] [3/21] [Case-01-low-power-003] DONE dsl=card.dsl.jsonl alt=card.alt.txt asc=card.asc.txt nodes=6
[2026-07-30 14:50:33] [INFO] SUMMARY mode=d2t total=21 success=21 failed=0
```

## 14. 训练 RequestBody 工具

TaskSpec 到 ALT+ASC 训练请求的组装脚本位于：

```text
.agents/skills/harmony-card-generation-datamodel-first/scripts/taskspec_to_alt_chat_completions.py
```

默认读取 TaskSpec 同目录下的 `card.alt.txt` 和 `card.asc.txt` 组装 Assistant 内容：

```powershell
python .agents/skills/harmony-card-generation-datamodel-first/scripts/taskspec_to_alt_chat_completions.py `
  references/datasets/Case-01-low-power-001/task.taskSpec.json `
  -o references/datasets/Case-01-low-power-001/task.alt.request.json
```

可用 `-a/--alt` 和 `-s/--asc` 指定其他文件。Assistant 内容固定为：

```text
<think>

</think>

<alt>
Column root ...
</alt>
<asc>
Text title_text bind=/data/title
Button action_button label=立即查看 event=0
</asc>
```

脚本生成的 system message 要求模型同时输出纯布局 ALT 和节点语义 ASC，并明确限制 Checkbox、要求 Button 的 `font` 与 `chars` 容量。
