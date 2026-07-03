# 新增规则指南

本指南面向 AI 与人类开发者，描述如何在本框架内新增一条原子校验规则。新增规则只需三步：

1. 在 `validator/rules/<分组>.py` 中写规则函数并加 `@rule(...)` 装饰器
2. 在 `validator/cases/<新规则ID>/` 下补 fail.jsonl / pass.jsonl / expected.json
3. （可选）将规则 ID 同步到 `validator/rules-config.default.json`，便于人工查阅

完成三步后，`engine.discover_rules()` 会自动发现规则，`run_cases.py` 会自动回归。

## 1. 编号约定

- 格式：`R-{层级}-{三位序号}`
- 层级：
  - `L0` 协议与硬约束（version / catalogId / surfaceId / 组件类型 / 绑定路径 / 事件 / 禁用键）
  - `L1` 数值布局（root 尺寸 / 圆角 / 字号表 / 间距表 / 布局预算 / 文本拟合）
  - `L2` 内容与视觉（颜色 / 文本去重 / 按钮基线）
- 序号：三位零补，例如 `R-L0-002` 之后是 `R-L0-003`
- 新增时取当前同层最大序号 +1，避免与已注册 ID 冲突；注册时若重复会抛 `ValueError`

## 2. `@rule` 装饰器签名

```python
from validator.rule import rule
from validator.result import Severity

@rule(
    "R-L0-XXX",                              # rule_id, 必填
    Severity.ERROR,                          # 严重度, ERROR/WARN/INFO
    name="<人类可读短标题>",                 # 必填
    description="<完整描述，说明检查对象与判定标准>",  # 必填
    tags=("L0", "protocol"),                 # 可选, 用于分组检索
    default_enabled=True,                    # 可选, 默认 True
)
def check_xxx(ctx: CardContext) -> list[Violation]:
    ...
```

- `name` 与 `description` **必填**。`name` 用于卡片标题，`description` 用于人/AI 阅读。两者都出现在 violation 输出中。
- 规则函数签名必须是 `(ctx: CardContext) -> list[Violation]`。
- 不返回违规时返回 `[]`；命中时返回 1 个或多个 `Violation`。
- 规则不应抛异常；如有意外情况应该返回 `Violation(severity=ERROR, message=...)`。

## 3. Violation 构造

```python
from validator.result import Violation, Severity

Violation(
    rule_id="R-L0-XXX",        # 与 @rule 一致
    rule_name="",              # 留空, 引擎自动从元数据注入
    description="",            # 留空, 引擎自动从元数据注入
    severity=Severity.ERROR,   # 通常与 @rule 一致, 少数规则按命中细节可降级
    message="<具体不满足的细节>",  # 必填, 应给出定位信息(组件id/路径/数值)
    location="<组件id 或 JSON Pointer>",  # 可选, 便于 UI 跳转
)
```

- `rule_name` 和 `description` 留空即可，引擎在收集时会从注册元数据自动补全。
- `message` 应包含**可定位信息**（组件 id、字段路径、实际值、期望值），便于阅读与定位。
- `location` 是给上层 UI 用的简短定位（组件 id、JSON Pointer、line N 等）。

## 4. CardContext 数据契约

`ctx` 由 `CardContext.from_messages(messages, token_colors=...)` 构造，提供 DSL 的全部解析结果与常用 helper。规则**不应再自行解析 JSONL**，应全部从 `ctx` 取值。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ctx.messages` | `list[dict]` | 三行原始消息 |
| `ctx.create_surface` | `dict` | 第一行 createSurface 对象 |
| `ctx.update_components` | `dict` | 第二行 updateComponents 对象 |
| `ctx.update_data_model` | `dict` | 第三行 updateDataModel 对象 |
| `ctx.components` | `list[dict]` | `update_components["components"]` 中所有 dict 元素 |
| `ctx.by_id` | `dict[str, dict]` | `id -> component` 索引 |
| `ctx.root_id` | `str` | `update_components["root"]` |
| `ctx.data_model` | `Any` | `update_data_model["value"]`，可能是 dict / list / 标量 |
| `ctx.size` | `str` | 从 `create_surface.width` 推断，"2x2" / "2x4" / "WxH" |
| `ctx.token_colors` | `set[str]` | 大写 token 色板，未加载时为空集 |
| `ctx.token_color_source` | `str` | token 色板源文件路径，未加载时为空 |

辅助方法（写在 `validator/context.py`，规则内可直接调用）：

- `ctx.walk(value, path="$")`：深度优先遍历 dict / list，yield `(path_str, value)`，路径形如 `$.a.b[0]`。
- `ctx.resolve_pointer(data, pointer)` / `ctx.read_pointer(data, pointer)`：按 JSON Pointer 解析；`resolve_pointer` 返回 `bool`，`read_pointer` 返回命中值或 `None`。
- `ctx.expression_body(value)`：若 `value` 是完整 `{{ ... }}` 表达式，返回内部字符串；否则 `None`。
- `ctx.expression_pointers(value)`：从表达式中抽取所有 `/${path}` 与 `$__dataModel.a.b` 对应指针。
- `ctx.suffix_to_pointer(suffix)`：将 `$__dataModel.a.b` 后缀转成 `/a/b`。
- `ctx.numeric(value)`：将 `"14"`, `"14fp"`, `14`, `14.0` 等统一转 `float`，无法解析返回 `None`。
- `ctx.padding_tuple(value)`：把 `"8"` / `8` / `{top:8,right:4,...}` 规范为 `(t,r,b,l)` 四元组。
- `ctx.estimate_text_width(text, font_size)`：估算字符串像素宽（中文=CJK 宽 1×fp、英文/数字=0.6×fp 等）。
- `ctx.content_to_string(value)`：把 Text `content` / Button `label`（字符串/表达式/`{path}`/`formatString`）解析为可读字符串；无法解析返回 `None`。
- `ctx.normalize_text(text)`：去除空白与标点，供「语义重复」类规则使用。

常量（同样从 `validator.context` 导入）：

- `WIDTH_2x2=140`, `WIDTH_2x4=300`, `HEIGHT=140`
- `FONT_SIZES={10,12,14,16,18,20,32,40}`
- `SPACING={0,2,4,6,8,10,12,14,16}`
- `ALLOWED_COMPONENTS`, `BANNED_COMPONENTS`, `BANNED_KEYS`
- `COLOR_RE`, `COLOR_KEYS`
- `EVENT_CAPABILITIES`, `EXPECTED_MESSAGE_KEYS`

## 5. 规则分组与归档

按检查对象选合适的 `rules/<分组>.py`：

| 分组文件 | 主题 |
| --- | --- |
| `protocol.py` | L0 行数 / version / catalogId / surfaceId / 尺寸 / components 是否数组 / 模板 children 键 |
| `components.py` | L0 组件 id / 类型 / 禁用键 / 禁用事件 / 网络 URL / SVG / children 类型与存在性 |
| `bindings.py` | L0 表达式完整性 / 表达式路径 / `{path}` / `formatString` |
| `events.py` | L0 onClick 数组 / handler 类型 / 事件能力 / args 校验 |
| `style.py` | L1 fontSize / textOverflow / padding / margin / itemMargin / linearGradient / Image |
| `layout.py` | L1 root 尺寸 / 圆角 / padding / Row / Column 预算 / 底部间距 |
| `text_fit.py` | L1 Text 内容宽度估算 / Button 高度 / Button label 估算 |
| `color.py` | L2 颜色格式 / 颜色未在 token 色板 / 渐变 stop 颜色 |
| `content.py` | L2 文本字面重复 / 语义重复 / Button-Text 基线 |

新规则与已有规则明显不属同一类时新建文件；否则追加到现有文件。

## 6. 反例与正例

每个新规则必须有 `validator/cases/<RULE_ID>/` 目录，含三个文件：

- `fail.jsonl`：3 行 JSONL，**必须**触发该规则
- `pass.jsonl`：3 行 JSONL，**不应**触发该规则
- `expected.json`：
  ```json
  {
    "rule_id": "R-L0-XXX",
    "should_fire_on_fail": true,
    "should_fire_on_pass": false
  }
  ```
- `README.md`：规则名、描述、严重度、标签、fail/pass 说明（运行 `generate_cases.py` 会自动生成）

### 6.1 复用 generate_cases.py

最快的做法：

1. 在 `validator/generate_cases.py` 的 `MUTATORS` 字典里加一个 `R-L0-XXX: <mutator 函数>`
2. 若规则依赖特定尺寸（2x2 / 2x4），把 `R-L0-XXX` 加入 `USE_2x4_FOR_PASS`（默认 2x2）
3. 写一个最小化 mutator：传入 `GOOD_CARD_2x2` / `GOOD_CARD_2x4`，返回只破坏本规则的卡片
4. 运行 `python validator/generate_cases.py`，`cases/<RULE_ID>/` 自动生成

```python
def _mutate_R_L0_XXX(card):
    return _set_path(card, 1, "updateComponents.components.1.id", "")

MUTATORS["R-L0-XXX"] = _mutate_R_L0_XXX
```

### 6.2 手工编写

如果 mutator 太复杂（比如要新增整棵子树、调整 onClick 列表），可以手写 `fail.jsonl`。要点：

- 复制 `GOOD_CARD_2x2` 或 `GOOD_CARD_2x4`，最小化修改让其触发本规则
- 验证：`python -m validator validator/cases/R-L0-XXX/fail.jsonl` 输出必须包含本规则
- 验证：`python -m validator validator/cases/R-L0-XXX/pass.jsonl` 输出**不得**包含本规则（其他规则可允许触发）
- 写 `expected.json` 和简短 `README.md`

## 7. 同步默认配置（可选）

`rules-config.default.json` 是「所有规则一览表」，方便人工查看。运行：

```python
python -c "from validator import engine, registry; engine.discover_rules(); import json, pathlib; rs=sorted(registry.all_rules(), key=lambda r: r.rule_id); cfg={'rules':{r.rule_id:{'enabled':True,'severity':r.severity.value,'name':r.name} for r in rs}}; pathlib.Path('validator/rules-config.default.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')"
```

即可重新生成。

## 8. 端到端示例：新增 `R-L0-005 surfaceId一致性`

**Step 1**：在 `validator/rules/protocol.py` 末尾追加：

```python
@rule(
    "R-L0-005",
    Severity.ERROR,
    name="surfaceId一致性",
    description="三行消息的 surfaceId 必须完全相等，否则卡片无法正确关联渲染。",
    tags=("L0", "protocol"),
)
def check_surface_id(ctx: CardContext) -> list[Violation]:
    ids = [
        ctx.create_surface.get("surfaceId"),
        ctx.update_components.get("surfaceId"),
        ctx.update_data_model.get("surfaceId"),
    ]
    if len({i for i in ids if i is not None}) > 1:
        return [Violation(
            rule_id="R-L0-005", rule_name="", description="",
            severity=Severity.ERROR,
            message=f"surfaceId 不一致：createSurface={ids[0]!r}, "
                    f"updateComponents={ids[1]!r}, updateDataModel={ids[2]!r}",
            location="surfaceId",
        )]
    return []
```

**Step 2**：在 `validator/generate_cases.py` 的 `MUTATORS` 加：

```python
def _mutate_R_L0_005(card):
    return _set_path(card, 1, "updateComponents.surfaceId", "other_surface")
MUTATORS["R-L0-005"] = _mutate_R_L0_005
```

**Step 3**：运行：

```bash
python validator/generate_cases.py
python validator/run_cases.py
```

`run_cases.py` 会断言 `R-L0-005` 在 `fail.jsonl` 中触发、在 `pass.jsonl` 中不触发。

## 9. 完成清单

- [ ] `RULE_ID` 唯一、符合 `R-{L0|L1|L2}-{三位}`
- [ ] `name` / `description` 必填且通顺，能让人/AI 30 秒内看懂
- [ ] 函数签名 `(ctx: CardContext) -> list[Violation]`
- [ ] 归到正确的 `rules/<分组>.py`
- [ ] `cases/RULE_ID/fail.jsonl` 跑 `python -m validator ...` 必含 `RULE_ID`
- [ ] `cases/RULE_ID/pass.jsonl` 跑 `python -m validator ...` 不含 `RULE_ID`
- [ ] `cases/RULE_ID/expected.json` 与上面一致
- [ ] `run_cases.py` 全绿
- [ ] 已同步 `rules-config.default.json`

## 10. 运行与集成

```bash
# 校验单个文件
python -m validator path/to/card.jsonl -c path/to/config.json

# 跑全部反例回归
python validator/run_cases.py
```

- 默认输出 JSON 到 stdout，passed=true/false 与 violations 列表
- 退出码：`passed=true` → 0，有 error/warn → 1
- Windows PowerShell 用户注意：`>` 重定向默认写 UTF-16，建议：
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  python -m validator card.jsonl | Out-File -Encoding utf8 out.json
  ```
  或在 Python 内调用 `validator.engine.run(...)` 直接写文件
