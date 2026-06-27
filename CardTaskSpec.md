# CardTaskSpec 协议规范

> **版本**：`cardtaskspec/v1`
> **用途**：作为大模型（+ harmony-card-generation skill）与小模型之间的唯一桥接契约。小模型无法读取 skill 原始内容，仅依据本协议 JSON 生成 HarmonyOS A2UI Form 服务卡片的 DSL（JSONL）与 CardSpec（JSON）。

---

## 1. 概述

### 1.1 工作流

```
用户 Query
   │
   ▼
大模型 + harmony-card-generation skill
   │  （完成全部分析决策：场景、尺寸、能力选择、语义角色、
   │    DataModel、CardSpec、事件绑定、素材匹配、宽度预算）
   ▼
CardTaskSpec JSON  ← 本协议，小模型的唯一输入
   │
   ▼
小模型 API
   │  （机械转译：把决策落成合法 JSONL + CardSpec JSON）
   ▼
genui 代码块（DSL JSONL）+ cardspec 代码块（CardSpec JSON）
```

### 1.2 设计目标

| 目标 | 实现手段 |
| --- | --- |
| **小模型无需读 skill** | 把 DSL/CardSpec 的全部硬约束压缩进 `rules`，每次嵌入 |
| **精炼但完整** | 大模型预填可直接输出的对象（dataModel/cardSpec/onClick），只嵌入本次选中的能力与素材 |
| **小模型有布局自由度** | `card.layout` 只给布局意图（rootShell 类型、尺寸预算、区域角色 + hint、拥挤行预算），不给组件树骨架 |
| **抗模板化** | 小模型自行决定组件嵌套、颜色、字号、间距、渐变 |

### 1.3 职责边界

| 职责 | 由谁完成 |
| --- | --- |
| 场景识别、尺寸选择、能力边界判断 | **大模型** |
| 语义角色分配、DataModel 形状、CardSpec 契约 | **大模型** |
| 事件能力选择、onClick 预填（含固定参数值） | **大模型** |
| 素材语义匹配、宽度预算 | **大模型** |
| 复杂格式化/条件文案预计算到展示字段 | **大模型** |
| 组件嵌套结构、id 命名、样式颜色字号间距 | **小模型** |
| 渐变色板、半透明块、视觉锚点选择 | **小模型** |
| 落成合法 JSONL（3 行）+ CardSpec JSON | **小模型** |

---

## 2. 顶层结构

```jsonc
{
  "schema": "cardtaskspec/v1",        // 协议版本标识，固定值
  "userQuery": "...",                  // 原始用户一句话（保留上下文）
  "task": "...",                       // 给小模型的输出指令

  "card": { ... },                     // 卡片决策（场景/尺寸/语义角色/布局意图）
  "dataModel": { "value": { ... } },   // 初始 DataModel（占位/加载态，可直接输出）
  "cardSpec": { ... },                 // CardSpec 对象（可直接输出）

  "dataCapabilities": [ ... ],         // 本次选中的数据能力 + 预推导输出路径（静态卡为 []）
  "capabilityGap": "...",              // 可选：当缺少所需数据能力时的降级说明
  "eventBindings": [ ... ],            // 预填好的 onClick，按触发元素分组
  "assets": [ ... ],                   // 本次选中的素材库资源

  "rules": {                           // 压缩硬约束，每次嵌入
    "dsl": [ ... ],
    "cardSpec": [ ... ]
  }
}
```

---

## 3. 逐字段规范

### 3.1 `schema`
- **必填**。固定值 `"cardtaskspec/v1"`。

### 3.2 `userQuery`
- **必填**。用户的原始一句话请求，供小模型理解上下文。

### 3.3 `task`
- **必填**。给小模型的输出指令。标准内容：
  > 根据本协议生成两个代码块：`genui`（A2UI JSONL，每行一个 JSON object）和 `cardspec`（CardSpec JSON object）。直接输出两个代码块，不要解释、标题或总结。

### 3.4 `card`
卡片决策对象。

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `scenario` | 是 | string | 场景分类：`status`（状态速览）、`reminder`（提醒/时间）、`action`（动作卡）、`device`（设备/产品）、`summary`（信息摘要） |
| `size` | 是 | `"2x2"` \| `"2x4"` | 卡片尺寸。`2x2`=160×160vp，`2x4`=320×160vp（横版） |
| `sizeReason` | 是 | string | 选择该尺寸的一句话理由 |
| `semanticRoles` | 是 | array | 语义角色数组（见下） |
| `layout` | 是 | object | 布局意图（见下） |

#### `card.semanticRoles[]`

每个角色对象：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `role` | 是 | `identity`（标识）/ `primaryAnswer`（主答案）/ `metric`（指标）/ `context`（上下文）/ `status`（状态标签）/ `media`（媒体）/ `action`（动作） |
| `label` | 是 | 该角色的中文标签（如"电量百分比"） |
| `dataPath` | 否 | 绑定的 DataModel 路径（绝对 JSON Pointer，如 `/battery/percentText`）。静态字面量可省略 |
| `protected` | 否 | boolean。为 true 时该值是受保护内容，必须完整显示，不得用 ellipsis/clip |
| `eventRef` | 否 | 引用 `eventBindings[].eventRef`，表示该角色元素点击时触发对应 onClick |
| `assetRef` | 否 | 引用 `assets[].assetRef`，表示该角色使用的素材 |
| `layoutHint` | 否 | 一句话布局提示（如"视觉主导，大字号"），供小模型参考 |

> `primaryAnswer` 必须在视觉上占主导。`context` 必须短于 `primaryAnswer`。

#### `card.layout`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `rootShell` | 是 | root 组件类型：`Column` \| `Row` \| `Stack`。文本/指标为主用 Column；左右面板用 Row；图片/光晕叠层用 Stack |
| `root` | 是 | `{ width, height, borderRadius, clip, padding }`。2x2: 160×160；2x4: 320×160；borderRadius 20-24；clip:true；padding 10-12 |
| `regions` | 是 | 区域数组。每项 `{ role, hint }`。2x2 ≤3 个区域，2x4 ≤4 个区域。hint 是一句话中文布局意图 |
| `crowdedRows` | 否 | 拥挤行预算数组。每项 `{ row, protectedItems[], availableWidth, note }`。对每个含 2+ 受保护文本的行给出可用宽度 |

> **小模型自由度**：`card.layout` 只给意图，不给组件树骨架。小模型自行决定组件嵌套层次、id、样式颜色字号间距。

### 3.5 `dataModel`
- **必填**。对象，包含 `value` 字段。

`dataModel.value` 是初始 DataModel 的完整 JSON 对象，直接用于 `updateDataModel` 的 `value`。
- **静态卡**：放占位/演示值（非真实隐私数据），按语义分组键（如 `battery`、`earphone`、`weather`、`action`、`asset`）。
- **动态卡**：放空对象、空数组和加载态占位（如 `{ "weather": { "current": {}, "daily": [] }, "state": { "loading": true } }`）。
- 复杂格式化/条件文案由大模型**预计算**为展示字符串字段（如 `percentText: "85%"`），小模型直接绑定。

### 3.6 `cardSpec`
- **必填**。CardSpec JSON 对象，可直接作为输出。

```jsonc
// 静态卡
{ "suggestSize": "2x2" }

// 动态卡
{
  "suggestSize": "2x2",
  "dataBindings": [
    { "capabilityId": "ViewWeather", "arguments": { "districtName": "青浦区" }, "writeResultTo": "/data/weather" }
  ]
}
```

- `suggestSize` 必须与 `card.size` 一致。
- 静态卡不虚构 `dataBindings`。动态卡必须包含 `dataBindings`。
- `capabilityId` / `arguments` 来自 `dataCapabilities` 声明。
- 事件能力**不进** CardSpec。

### 3.7 `dataCapabilities[]`
本次选中的数据能力清单。**静态卡为空数组 `[]`。** 每项：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `capabilityId` | 是 | 能力 manifest 的 `id`（如 `ViewWeather`、`calendar.events.search`） |
| `arguments` | 是 | 该能力 `inputSchema` 声明的参数对象 |
| `writeResultTo` | 是 | `/data` 下的 JSON Pointer（如 `/data/weather`） |
| `usedOutputPaths[]` | 是 | 预推导的 UI 访问路径数组。每项 `{ field, path, desc }`，`path` = `writeResultTo + outputSchema字段`。小模型直接用这些路径做组件绑定 |

**示例（天气动态卡）：**

```jsonc
{
  "capabilityId": "ViewWeather",
  "arguments": { "districtName": "青浦区", "forecastDays": 1 },
  "writeResultTo": "/data/weather",
  "usedOutputPaths": [
    { "field": "temperatureText", "path": "/data/weather/current/temperatureText", "desc": "温度文本如29°C" },
    { "field": "condition", "path": "/data/weather/current/condition", "desc": "天气现象如多云" },
    { "field": "airQuality", "path": "/data/weather/current/airQuality", "desc": "空气质量等级" }
  ]
}
```

> 大模型已做 `writeResultTo + outputSchema` 路径推导，小模型无需理解 manifest，直接用 `usedOutputPaths[].path` 绑定。

### 3.8 `capabilityGap`（可选）
当用户请求的动态数据能力不在已声明清单中时，说明降级策略。例如：
> 当前无电池电量数据能力，使用静态占位值；端侧如需实时电量需补充 capability manifest。

### 3.9 `eventBindings[]`
预填好的 onClick，按触发元素分组。每项：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `eventRef` | 是 | 引用标识，与 `semanticRoles[].eventRef` 对应 |
| `on` | 是 | 触发元素的中文描述（如"切换省电模式按钮"） |
| `onClick` | 是 | **完整的 EventHandler 数组**，小模型直接挂到对应组件的 `onClick` 上 |

**`onClick` 已包含：**
- `call`：能力函数名（如 `clickToIntent`、`clickToDeeplink`、`clickToCallPhone`）
- `args`：完整参数对象，含固定值或 DataModel 路径绑定

**示例（开启省电模式）：**

```jsonc
{
  "eventRef": "togglePowerSaving",
  "on": "切换省电模式按钮",
  "onClick": [
    {
      "call": "clickToIntent",
      "args": {
        "intentName": "SetSettingSwitch",
        "params": {
          "appBundleName": "com.huawei.hmos.settings",
          "itemName": "battery_saving_mode",
          "switchFlag": 0
        }
      }
    }
  ]
}
```

**示例（打开音乐歌单）：**

```jsonc
{
  "eventRef": "dailyRecommend",
  "on": "每日推荐入口",
  "onClick": [
    {
      "call": "clickToDeeplink",
      "args": {
        "bundleName": "",
        "abilityName": "",
        "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"
      }
    }
  ]
}
```

> 大模型已校验 `call` 来自已声明能力、`args` 符合 parameters、跳转目标在 supportedTargets 中。小模型无需理解能力 manifest，直接引用。

### 3.10 `assets[]`
本次选中的素材库资源。每项：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `assetRef` | 否 | 引用标识，与 `semanticRoles[].assetRef` 对应 |
| `src` | 是 | 素材库声明的本地/资源路径（如 `resource/battery_widget/icon_electricity.png`） |
| `use` | 是 | 用途说明（如"电池图标"） |
| `bindTo` | 否 | 若素材由 DataModel 管理，给出绑定路径（如 `/asset/batteryIcon`），且 `dataModel.value` 中已初始化为该 src |
| `static` | 否 | boolean。为 true 时可直接写入 `Image.src` |

> 小模型只能使用 `assets` 中声明的 `src`，不得编造路径。无素材匹配时大模型省略 assets，小模型用渐变/半透明块/字形/Progress 等非媒体技法。

### 3.11 `rules`
压缩硬约束，每次嵌入。详见 [第 4 节](#4-rules-块全文)。

---

## 4. `rules` 块全文

### 4.1 `rules.dsl`（DSL 硬约束）

```
01 输出 JSONL，每行一个完整 JSON object，恰好 3 行，顺序：createSurface → updateComponents → updateDataModel。
02 version 恒为 "v0.9"；createSurface.catalogId 恒为 "ohos.a2ui.extended.catalog"。
03 createSurface 不含 theme；所有消息使用同一个 surfaceId。
04 updateComponents 紧跟 createSurface，同一 surface 只发一次完整组件树，不增量追加。
05 updateDataModel.path 用 "/"；value 直接用本协议 dataModel.value。
06 组件用扁平邻接表：每个组件 { id, component, ... }，children 是 id 字符串数组；不在 children 内联组件对象。
07 必须有 root 组件；所有 children 引用可解析；id 不重复。
08 只允许 10 个组件：Text、Image、Divider、Progress、Button、Checkbox、Row、Column、List、Stack。不用 TextInput/Toggle/Radio/Select/Tabs/Web/Grid/If 等。
09 属性名用 extended 写法：Text.content（非 text）、Image.src（非 url）、Button.label（非 child）；不用 Button.action。
10 布局对齐放 styles 内：Row/Column 的 justifyContent、alignItems；Stack 的 alignContent；List 的 listDirection、scrollBar。
11 只支持 onClick 事件；不用 onAppear/onChange/onSelect/onReachStart/onReachEnd。
12 onClick 是 EventHandler 数组，每项必须有 call；直接使用 eventBindings 中预填的 onClick 对象，不改 call 名和参数结构。
13 禁用表达式：不写 {{...}}、$__dataModel、$context、size()、$__widthBreakpoint、$__colorMode。
14 动态绑定：单值用 {"path":"/绝对路径"}；字符串拼接用 {"call":"formatString","args":{"value":"...${/path}..."}}；复杂值用 dataModel 中预计算展示字段。
15 模板循环仅用于 Row/Column/List 的 children：{"componentId":"模板id","path":"/数组路径"}；模板组件内相对路径不以/开头解析到当前项。
16 Image.src 只用 assets 中声明的本地路径；不用网络 URL、SVG、base64 SVG、占位图域名。
17 静态素材可直接写 Image.src；DataModel 管理时绑定 /asset/... 并确保 dataModel.value 中该字段已初始化为声明的 src。
18 样式键用 camelCase（如 backgroundColor 非 background-color；borderRadius 非 border-radius）。
19 Root 尺寸：2x2 为 width:160 height:160；2x4 为 width:320 height:160；borderRadius 用 20-24；clip:true。
20 2x2 主区域≤3，2x4 主区域≤4；横向 Row 直接子节点≤3。
21 关键信息（日期/星期/时间/CTA/状态/百分比/价格/主指标值/主标题/用户要求字段）必须完整显示，不用 ellipsis/clip/marquee。
22 textOverflow:"ellipsis" 只能用于可压缩次要文本（可选地点、副标题、建议文案）。
23 拥挤 Row 写前参考 crowdedRows 宽度预算；受保护值放不下时先减 padding/itemMargin/分隔线/字号，再拆行或选 2x4。
24 DataModel 键按语义分组（如 battery/earphone/weather/action/asset），不用 topText1 这类视觉位置命名。
25 颜色用 #RRGGBB 或 #AARRGGBB（半透明用 8 位 alpha 前缀）；渐变用 styles.linearGradient，colors 是 [["#RRGGBB",stop],...]。
```

### 4.2 `rules.cardSpec`（CardSpec 硬约束）

```
01 cardspec 是一个 JSON object，suggestSize 与 card.size 完全一致，只能是 "2x2" 或 "2x4"。
02 静态卡片：只含 suggestSize，不虚构 dataBindings。
03 动态卡片：必须含 dataBindings[]，每项 { capabilityId, arguments, writeResultTo }。
04 capabilityId 和 arguments 来自 dataCapabilities 声明；writeResultTo 在 /data 下。
05 事件能力（onClick/clickTo*/functionCall）不进 CardSpec，只进 DSL 的 onClick。
06 DSL 中 UI 绑定路径必须能从 dataCapabilities.usedOutputPaths 或 dataModel.value 推导。
07 默认用简洁形态：capabilityId、arguments、writeResultTo；不加 bindingId 或 capabilityVersion 除非端侧需要。
08 不编造未声明的 capabilityId、参数、权限或端侧函数。
```

---

## 5. 大模型生成职责清单

大模型在输出 CardTaskSpec 前须确认：

- [ ] 已识别 `scenario` 并判断是否在能力范围内（超出则 `capabilityGap` 降级）
- [ ] 已选择 `size`（2x2 / 2x4）并给出 `sizeReason`
- [ ] 已分配 `semanticRoles`，`primaryAnswer` 视觉主导
- [ ] 已给 `layout`（rootShell + root 尺寸 + regions + crowdedRows），**不给组件树骨架**
- [ ] 已设计 `dataModel.value`（静态占位或加载态），复杂文案已预计算为展示字符串
- [ ] 已确定 `cardSpec`（静态/动态），动态卡的 `dataBindings` 来自已声明能力
- [ ] 已选 `dataCapabilities`（仅选中项 + 预推导 usedOutputPaths），静态卡为 `[]`
- [ ] 已预填 `eventBindings`（完整 onClick，含 call + args + 固定值），校验 call/参数/目标合法
- [ ] 已匹配 `assets`（语义匹配的素材库 src），无匹配则省略
- [ ] 已计算拥挤行 `crowdedRows` 宽度预算
- [ ] 缺能力时已加 `capabilityGap` 说明
- [ ] `rules` 块完整嵌入

---

## 6. 小模型输出格式

小模型收到 CardTaskSpec 后，直接输出两个代码块，**不输出**解释、标题、路径或总结：

~~~
```genui
{"version":"v0.9","createSurface":{"surfaceId":"card","catalogId":"ohos.a2ui.extended.catalog"}}
{"version":"v0.9","updateComponents":{"surfaceId":"card","components":[...]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{...}}}
```

```cardspec
{
  "suggestSize": "2x2"
}
```
~~~

**小模型工作步骤：**

1. 读 `card.layout.rootShell` 和 `root` 尺寸 → 设计 root 组件
2. 读 `card.layout.regions` → 决定组件嵌套、id、样式、颜色、字号、间距
3. 读 `card.semanticRoles` → 把 dataPath/eventRef/assetRef 绑定到对应组件
4. 读 `dataModel.value` → 作为 `updateDataModel` 的 value
5. 读 `eventBindings` → 把预填 onClick 挂到对应触发组件
6. 读 `assets` → 把 src 用于 Image 组件（static 直接写，bindTo 绑定路径）
7. 读 `rules` → 校验输出合规
8. 输出 `genui` + `cardspec` 两个代码块

---

## 7. 协议样例

| 样例 | 文件 | 尺寸 | 类型 |
| --- | --- | --- | --- |
| 电量提醒卡 | `examples/battery-reminder.cardtaskspec.json` | 2x2 | 静态 |
| 耳机快捷操作卡 | `examples/earphone-quick-action.cardtaskspec.json` | 2x4 | 静态 |
