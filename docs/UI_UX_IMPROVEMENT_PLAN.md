# ShowPsiSi UI/UX 改进分析与方案

> 基线：`main` @ `a1f754d`（v0.3.0 发布后）。范围：Qt Quick 前端 `ui/qt/Main.qml`、`DvbiWorkspace.qml`、`UpdateDialog.qml`，以及 Tauri/Web 前端 `ui/tauri/web/app.js`、`style.css`、`workbench.js`、`dvbi.js`。
>
> **验证边界**：§0–§13 基于源码与 `docs/` 文档的静态分析，当时本机重新构建失败（见 §12.4）。构建问题已修复，本轮落地的改动和测试结果见 §14。文中“现状”描述的是代码行为，不代表 Windows UI 交互已经验证通过。每条方案的“验收”需要按 AGENTS.md 用真实引擎和真实样本做功能验证，不能用截图或模拟数据代替。

优先级定义：
- **P0**：影响正确理解或核心工作流，或者是两端功能不一致。
- **P1**：明显的效率或可读性问题。
- **P2**：打磨与长期工程项。

---

## 0. 总体结论

ShowPsiSi 的“证据优先”内核做得扎实：保留来源、显式未知、区分 Section 与 Merged、不臆测私有描述符。UI 也已经有一套编辑器式的设计令牌（4px 间距、12px 字段、28px 树行、焦点环、WCAG 对比度测试）。主要问题不在缺功能，而在**信息架构与信息密度**：

1. **检查器（Inspector）头部堆叠太多元数据**。用户最常看的结构树只剩很少的垂直空间。
2. **Metadata 视图是一个“杂物抽屉”**：协议卡片、标识符查询、卫星查询、多语言 EPG、ID 名称、文本诊断都在一个长滚动区里，结果以原始 JSON `<pre>` 输出。
3. **两端密度和交互不一致**。Qt 服务行高 94px、表格行 100px，Web 用紧凑列网格；快捷键、源栏字段顺序、Hex ASCII 列、时间线键盘操作也各不相同。
4. **开发/调试动作与用户动作混在主标题栏**（Agent API、Save diagnostics、Reset layout、主题、About 并列）。
5. **证据之间的导航还不够“编辑器化”**：字段到字节没有高亮，PID/SID 字段不能跳转到被引用的 section，列表不能排序，也没有拖放打开和最近文件。
6. **工程层面**：Qt 生产 QML 内嵌 25 个测试 Timer；Qt 中约有 5 处颜色绕过令牌，`style.css` 中有 193 处十六进制字面量，组件颜色层层覆盖；没有 i18n（`qsTr` 为 0）；Web 整页 `innerHTML` 重渲染；中文 Windows 上构建失败。

建议路线：
- 先做 **P0“检查器减负 + Metadata 拆分 + 两端一致性”**。
- 再做 **P1“导航与列表效率”**。
- 最后做 **P2“工程与国际化”**。

---

## 1. 已修复的上一轮交接缺口（核对 `docs/OPERATIONS_PARITY_HANDOFF.md`）

| 缺口 | 现状 | 依据 |
|---|---|---|
| Web 只能导出 TS | ✅ 已有 TS/BIN 选择 | `app.js:394`、`app.js:1909-1955`（`#export-format`） |
| Web 没有 “Use snapshot” | ✅ 已添加 | `app.js:1225`、`app.js:1247`（`data-use-comparison`） |
| Qt 编辑对话框不能选服务 | ✅ `renameDialog` 已有 `editService` 选择 | Main.qml renameDialog |
| Qt 对比只能打开 `evidence[0]` | ✅ 已有 `comparisonSource` 选择 | Main.qml inspector 变更控件 |
| Qt 退出对比后丢失原选择 | ⚠️ 已有 `restoreComparisonWorkspace`（Main.qml:864），需要交互验证 | — |
| A/B 快捷键不一致 | ❌ 仍不一致（见 §10） | — |
| 保存成功后 Qt 对话框保持打开，Web 自动关闭 | ❌ 仍不一致（见 §8） | — |
| 只能对单 section SDT 改名；没有“按原样导出当前快照” | ❌ 仍存在（见 §8） | — |

---

## 2. 全局外壳（标题栏 / 源栏 / 统计 / 状态栏）

### 2.1 标题栏动作分组 — P1
- **现状**：
  - Web 标题栏依次是 Input kind 选择、Reset layout、Light theme、About、Agent API、Save diagnostics。
  - Qt 标题栏有 inputKind、“PSI / SI INSPECTOR”（宽度 ≥1400 才显示）、以 “· Qt Quick” 结尾的状态文字，以及 Light/Dark、Reset layout、About / Updates、Agent API、Save diagnostics。
- **问题**：6 个同等权重的按钮里，只有输入类型和主题是日常操作。Agent API 和 Save diagnostics 是集成/排障功能，Reset layout 是低频的恢复操作。状态文字中的 “· Qt Quick” 对用户没有信息量。
- **理由**：编辑器类工具（VS Code、Wireshark）通常把低频和开发者功能收进“菜单/齿轮”，让主栏只保留与当前工作相关的控件，减少视觉噪音和误点。
- **方案**：
  - 主栏只保留：`Input kind`（改为分段控件 TS | DVB-I）、主题切换（图标按钮 + tooltip）、`⋯` 溢出菜单。
  - 溢出菜单分组：
    - 视图：Reset layout。
    - 帮助：About / Updates、Keyboard shortcuts。
    - 开发者：Agent API、Save diagnostics。
  - 删除状态文字里的 “· Qt Quick”，把前端/版本信息放进 About。
- **验收**：两端主栏控件数 ≤ 3。所有原动作都能通过菜单和键盘到达（菜单遵循 APG Menu Button 模式）。原功能测试仍通过。

### 2.2 源栏字段顺序与 Default charset 位置 — P0（一致性）
- **现状**：
  - Web 顺序：路径 → Standards → Default charset → Extra PIDs → Open file… → Analyze → Cancel。
  - Qt 顺序：SOURCE → Standards → Extra PIDs → 路径。Qt 的 **Default charset 放在 Metadata 视图里**（`defaultCharset`，Main.qml:4363），但它影响的是*下一次扫描*。
- **问题**：
  - 同一产品两端字段顺序不同，切换前端的用户需要重新学习。
  - 把影响扫描的参数放在“查看已解析结果”的检查器里，属于位置错误：用户改了以后看不到即时效果，容易误以为它会重新解码当前 section。
- **理由**：扫描参数应与“Analyze”放在一起，形成 “输入 → 参数 → 执行” 的线性流程。
- **方案**：
  - 两端统一为：`[源路径 + Open…] [Standards] [Charset] [Extra PIDs] [Analyze ▶] [Cancel]`。
  - 不常改的 Charset 和 Extra PIDs 收进 “Scan options ▾” 折叠区。折叠时以摘要标签显示非默认值（例如 `charset: ISO-8859-5 · +PID 0x0123`）。
  - 从 Qt Metadata 视图移除 charset 输入，或者只保留一个“在源栏修改”的链接。
  - 当前结果所用的参数与源栏参数不同时，显示“参数已更改，需重新分析”的提示条。
- **验收**：两端字段顺序一致。修改 charset 后出现重新分析提示。Qt 的 Metadata 视图不再出现扫描参数。

### 2.3 统计行 — P1
- **现状**：Web 显示 SERVICES / SECTIONS / ISSUES / SCAN 的纯数字。Qt 是纯文本，并且完整拼写 “cyclic redundancy check failures”。
- **问题**：数字不可点击。Qt 的长拼写占宽且难扫读。Issues 数字没有严重度区分。
- **方案**：
  - 把统计项做成可点击的“徽章”：点击 SERVICES 跳到 Services 标签，点击 ISSUES 跳到 Issues 标签并按严重度过滤。
  - 统一缩写为 `CRC ✕ n`，在 tooltip 中展开为 “Cyclic Redundancy Check failures”（符合 AGENTS.md 的“可读的缩写解释”）。
  - Issues 按 error/warning 用语义色分开计数。
- **验收**：每个徽章都有 `aria-label`，并可通过键盘激活。两端文案一致。

### 2.4 状态栏与错误呈现 — P0
- **现状**：
  - Web 的错误只写进单行页脚 `notice()`，诊断保存失败时不显示错误样式。
  - Qt 状态栏高 26px，错误背景硬编码为 `#5a1d1d`。
- **问题**：
  - 单行页脚很容易被下一条消息覆盖，用户会错过错误。
  - 没有历史记录，用户无法回看“刚才那条错误”。
  - 硬编码颜色在浅色主题下对比不足。
- **理由**：分析工具的错误常常决定结果是否可信（例如扫描截断、后端断开），不能只是一闪而过。
- **方案**：
  1. 分三级显示消息：
     - info：状态栏，几秒后淡出。
     - warning：状态栏常驻，带 `⚠` 和次数，直到用户确认。
     - error：在内容区顶部显示可关闭的横幅（banner），并放入状态栏的消息历史。
  2. 状态栏右侧加“消息”按钮，弹出最近 50 条消息（Web 已有 `recentResponses` 环形缓冲，`app.js:189`，可以复用）。
  3. 诊断保存失败使用 error 级别。
  4. 颜色改用 `errorSurface` / `errorInk` 令牌。
- **验收**：触发后端断开、诊断写入失败时，错误在下一条消息出现后仍可见。屏幕阅读器通过 `aria-live="assertive"` 朗读 error（目前 Web 只有 3 处 `aria-live`）。

---

## 3. Explorer（左侧 PID / 表类型导航）

### 3.1 帮助文字与 “DESCRIPTOR EXTENSION” 占用侧栏 — P1
- **现状**：Explorer 底部常驻帮助文字和一个 “DESCRIPTOR EXTENSION” 框。
- **问题**：侧栏是窄而长的稀缺空间，常驻说明会把真正的 PID 树挤短。熟练用户不需要每次都看到说明。
- **方案**：
  - 说明文字改成标题旁的 `ⓘ` 弹出说明。
  - Descriptor extension 移到溢出菜单 “Extensions…”，或者做成可折叠的 section，并记住折叠状态（复用布局持久化）。
- **验收**：在 900px 窗口高度下，Explorer 至少能显示 20 行 PID 树。

### 3.2 树的可读性 — P1
- **方案**：
  - 每个 PID 节点固定显示 `0x` + 4 位十六进制，同时显示十进制的灰色辅助值，例如 `0x0100 · 256`。
  - 表类型显示缩写和 tooltip 全称（PAT → Program Association Table）。
  - 有 CRC 错误或 issue 的节点加语义色角标。
  - 支持输入字母快速定位（type-ahead，APG Tree 模式要求的功能）。
- **验收**：键盘 type-ahead 可用，角标颜色来自令牌。

---

## 4. 记录区各标签

### 4.1 Services — P0（Qt 密度）/ P1（排序）
- **现状**：
  - Web 是列网格 `LCN / SERVICE / TYPE / PMT PID / V/A PIDs`，100 条/页，用 ← → 翻页。列不能排序（代码中没有 `aria-sort`）。
  - Qt 行高 **94px**、4 行文字，表头只有 “LCN / SERVICE / STREAM DETAILS”。
- **问题**：
  - Qt 一屏只能显示约 6 个服务，Web 能显示约 25 个。两端体验差距很大，也不符合 “compact” 的规范。
  - 不能按 LCN、SID 或类型排序，查找困难。
  - 翻页箭头没有文字标签，没有“第 x / y 页”，也不能直接跳页。
- **方案**：
  1. Qt 改用与 Web 相同的列式 `TableView` / `HorizontalHeaderView`，行高 28px，列与 Web 一致。
  2. 两端都支持点击表头排序，并带 `aria-sort` 或 Qt Accessible 属性。排序逻辑放进 `workbench.js`，两端共享。
  3. 分页器已经显示 `101–200 of 240`，按钮也有 `aria-label`（更正原稿）。可以再加“首页/末页”；条目超过阈值时可以考虑虚拟滚动，替代分页。
  4. SID 和 PMT PID 等 ID 用等宽字体和固定位宽十六进制显示。
- **验收**：在 1440×900 窗口下 Qt 一屏可见服务数 ≥ 20。两端排序结果一致，由共享 `workbench.js` 的单元测试覆盖。

### 4.2 Topology — P1
- **现状**：拓扑行由 `workbench.js` 共享生成，支持 Alt+Left 返回，对比时可以 “Topology at A”。
- **问题**：返回只有快捷键，没有可见的面包屑，用户不知道自己“在哪一层”。
- **方案**：在拓扑视图顶部加面包屑 `Network 0x0001 › TS 0x0003 › Service 0x0101`，每一级都可以点击。Alt+Left 的行为保持不变。
- **验收**：面包屑与 Alt+Left 的结果一致，两端都有。

### 4.3 Tables — P1
- **现状**：
  - 分组用 `<details>` 分支，有 Bad CRC 复选框、Sections/Tables 切换和 Type 选择。
  - **切换按钮显示的是目标模式**，而不是当前模式。
  - Qt 逻辑表行高 100px，section 行高 58px。
- **问题**：标签显示目标模式是常见的反模式。用户看到 “Tables” 会以为当前就在 Tables 模式。
- **方案**：
  - 把切换按钮改成分段控件 `[Sections | Tables]`，用 `aria-pressed` 或选中样式标明当前模式。
  - “Bad CRC”改成 “Show bad-CRC evidence”，避免被理解成“只看坏 CRC”。
  - Qt 行高压缩到 28–40px，次要信息放进 tooltip 或检查器。
- **验收**：可用性检查时，用户能一眼说出当前模式。两端控件形式一致。

### 4.4 EPG — P1
- **现状**：EPG 以列表显示，每行是 SID · start UTC · 时长。UI_UX_REFRESH.md 明确把时间网格推迟了。
- **问题**：没有频道 × 时间的视图，很难看出节目重叠或空档。这些恰恰是 EIT 排查的重点。
- **方案**：
  - 第一阶段：列表按 SID 分组，可按开始时间排序，相邻事件重叠或有间隙时显示语义色标记。这些都可以由 `workbench.js` 计算。
  - 第二阶段：加只读的“时间网格”视图（行 = 服务，列 = 时间，可缩放），点击事件块跳到对应 EIT section。
  - 时间统一标注 UTC，可选显示本地时区。
- **验收**：重叠/间隙检测有共享测试。网格中的每个块都能跳回证据 section。

### 4.5 Issues — P1
- **现状**：Qt 行高 88px；两端都不能按严重度或类型过滤、排序。
- **方案**：
  - 加严重度过滤芯片（Error / Warning / Info）和类型下拉。
  - 每行显示 `[严重度图标] 规则 · PID · 次数`，点击跳到第一条证据，“下一条/上一条”可以在同类 issue 之间跳转。
  - Qt 行高压缩。
- **验收**：从统计行点击 ISSUES 后，Issues 标签已按对应条件过滤。

### 4.6 Changes（A/B 快照对比）— P0
- **现状**：
  - Web 每一侧都有许多小按钮：Topology at A、Use snapshot，外加每个 evidence 一个按钮。对象值直接用 `JSON.stringify` 显示。
  - Qt 记录区有 A/B packet 输入框、“Use current”、A/B 历史预设、kind、Swap A/B、Compare，一个带 `+/−/~` 的摘要文字，以及 Previous/Next。
- **问题**：
  1. 原始 JSON 对象值对用户来说是“不可读的 diff”。
  2. 按钮太多太小，主次不分。
  3. 摘要里的 `+/−/~` 符号没有图例。
- **方案**：
  1. 对象值改成结构化 diff：
     - 字段级显示 `name: "A" → "B"`，嵌套对象可展开。
     - 数值字段同时显示十六进制和十进制。
     - 新增/删除/修改分别用 `addedColor` / `removedColor` / `changedColor` 令牌着色（这些令牌已经存在）。
  2. 每侧只保留一个主动作 “Use snapshot”。“Topology at A” 和逐条 evidence 按钮收进行内 `⋯` 菜单，或改为“来源”下拉（Qt 已有 `comparisonSource`，Web 应对齐）。
  3. 摘要改成 `+3 added · −1 removed · ~5 changed` 三个可点击过滤芯片。
  4. A/B 选择改成在时间线上拖动两个标记（见 §7），并保留数字输入。
- **验收**：对比结果中不再出现原始 JSON。两端 A/B 控件模型一致。快捷键一致（见 §10）。

---

## 5. 检查器（Inspector）

### 5.1 头部堆叠 — P0（最影响日常使用）
- **现状**：
  - Web 在视图标签之上依次有：CRC 行、截断说明、解码器注释、Arrival 详情、Section group 详情、Scope 按钮 + 帮助行，然后才是 6 个视图标签。
  - Qt 结构类似：头部有 “▸ Arrival”“▸ Sections” 折叠开关、选中变更控件、标题、PID 行、CRC、arrivals、Section/Merged（各 50px），最后才是视图标签。
- **问题**：在 900px 高的窗口里，结构树可能只剩 1/3 的检查器高度。最常用的视图被低频元数据压缩了。
- **理由**：编辑器的“文档区”应该优先占满空间，元数据放在可折叠的“信息条”或侧面板中。
- **方案**：
  1. 头部压缩成**一行摘要条**：`PAT · PID 0x0000 · v3 · sec 0/0 · CRC ✓ · 12 arrivals · [Section|Merged]`。每一项都是可点击的 chip，展开对应的详情 popover。
  2. 截断说明和解码器注释改成单行警示条（带 `⚠` 和次数），点击展开。只有存在时才显示。
  3. Scope 帮助行改成 Scope 控件旁的 `ⓘ` tooltip。
  4. 视图标签紧接在摘要条下方。两端都把折叠状态写入布局持久化。
- **验收**：900px 高时，结构树可用高度 ≥ 检查器的 65%。所有原有信息仍然可以到达。

### 5.2 Structure 视图 — P1
- **现状**：
  - Qt 有树搜索和 `+/−` 展开折叠按钮。树行高亮使用硬编码颜色 `#4ec9b0`、`#d6a089`、`#3794ff`。
  - 字段到字节高亮被推迟（UI_UX_REFRESH.md）。
- **方案**：
  1. **字段 ↔ 字节联动**：选中树节点时，在 Hex 视图里高亮对应的字节区间；在 Hex 中点击字节时，反向定位字段。引擎需要在 JSONL 字段中输出 `byte_offset` / `bit_offset` / `bit_length`（属于引擎职责，前端不推断）。
  2. **引用跳转**：`PMT_PID`、`service_id`、`network_id` 等字段旁显示 “→” 链接，跳到被引用的 section。Alt+Left 返回。
  3. 字段值颜色改成语义令牌：`fieldName`、`fieldValue`、`fieldNumber`、`fieldUnknown`、`fieldReserved`，两端共享同一份颜色表。
  4. “未知/私有”字段统一用斜体和 “unknown” 徽章，强化“显式未知”原则。
- **验收**：联动高亮由真实样本 `lab.ts` 的功能测试覆盖。没有前端推断的偏移量。

### 5.3 Hex 视图 — P0（一致性）
- **现状**：Qt 只显示 offset + bytes，**没有 ASCII 列**；Web 有 ASCII 列。
- **方案**：
  - Qt 补上 ASCII 列，不可打印字符显示为 `·`。
  - 两端都把每行 16 字节分成 8+8 两组，加列标尺。
  - 支持选区复制（hex 或 C 数组格式），配合 §5.2 的字段高亮。
- **验收**：两端 Hex 视图输出逐字节一致。

### 5.4 XML / Decoded 视图 — P2
- **方案**：
  - XML 视图加“复制”“折叠元素”和“查找”功能。
  - Decoded 视图对长文本描述符（如 extended event）提供换行开关。
  - 字符集解码失败时显示原始字节和失败原因，不能静默替换。

### 5.5 Metadata 视图（拆分）— P0
- **现状**：
  - 一个长滚动区里依次是：协议卡片、标识符查询、卫星查询、多语言 EPG、ID 名称、文本诊断。
  - 结果是原始 JSON `<pre>`。命名空间下拉显示 `original_network_id` 这类原始键名。
  - Qt 是一串 TextArea，带 “Original values and source” 开关，还有放错位置的 Default charset 输入。
- **问题**：
  - “当前 section 的元数据”和“全局查询工具”混在一起，用户不知道哪些内容随选择变化、哪些不随选择变化。
  - 原始 JSON 与“可读的缩写解释”原则相违背。
- **方案**：
  1. 把 Metadata 拆成两部分：
     - **Section metadata**（随选择变化）：协议卡片、ID 名称、文本诊断。
     - **Lookup 工具**（与选择无关）：标识符查询、卫星查询。移到独立的 “Lookup” 侧面板或命令面板（Ctrl+K 下的 `>` 命令），并支持从字段右键 “Look up this ID”。
  2. 多语言 EPG 移到 EPG 标签内，作为事件详情的语言切换。
  3. 查询结果改成键值表：键名显示可读名称加 tooltip 原始键，值用等宽字体，来源单独一列（保留证据来源）。原始 JSON 放进 “Raw” 折叠区。
  4. 命名空间下拉显示 `Original Network ID (original_network_id)`。
- **验收**：Metadata 中不再出现原始 JSON 主视图。所有查询都能从字段上下文菜单发起。原有查询的功能测试仍通过。

### 5.6 References 视图与 specificationDialog 重复 — P2
- **现状**：Qt 既有 References 视图标签，又有单独的 `specificationDialog`，内容重复。
- **方案**：保留视图标签，删除对话框。或者让对话框只作为“在新窗口打开”的入口，内容共用同一个组件。

---

## 6. 选择、导航与搜索 — P1
- **现状**：
  - Ctrl+K 是记录搜索（两端都有）。Qt 还有 Ctrl+Shift+K 树搜索和 Ctrl+O 打开文件，Web 没有 Ctrl+O。
  - 没有快捷键帮助浮层。
  - 不能拖放打开文件，也没有最近文件（代码里的 `recent` 只指诊断响应缓冲）。
- **方案**：
  1. 把 Ctrl+K 升级为**命令面板**：默认搜索记录；`>` 前缀执行命令（Analyze、Export、Toggle theme…）；`#` 前缀按 PID/SID 跳转（例如 `#0x0100`）。
  2. 加 `?` 或 Ctrl+/ 打开快捷键帮助浮层，两端内容由同一份表生成。
  3. 支持拖放打开文件：Qt 用 `DropArea`，Web/Tauri 用 `onDragDropEvent`。
  4. 加最近文件列表，最多 10 条，放在 Open… 下拉中，并与布局一起持久化。不能记录 owner-machine 绝对路径到测试夹具中。
  5. 前进/后退历史：选择变化时入栈，Alt+Left / Alt+Right 跨标签导航。
- **验收**：两端快捷键表一致，并由测试读取同一份定义。

---

## 7. 时间线与历史 — P1
- **现状**：
  - Web 有密度滑杆（80 bins，Arrow/Home/End）、history-scope 选择、每页 40 个历史芯片、Compare snapshots 和 Latest state。
  - Qt 的密度条**只有 TapHandler、没有键盘支持**。Qt 有 cursor、5 个刻度标签和横向滚动的历史芯片，标题是 “ALL ARRIVALS · PACKET INDEX · NO CLOCK”。
- **问题**：
  - Qt 不能用键盘操作时间线，违反可访问性规范，也与 Web 不一致。
  - “NO CLOCK” 对新用户来说含义不明（没有 PCR/TDT 时钟，所以以包序号为轴）。
  - A/B 只能通过按钮设置，不能直接在时间轴上操作。
- **方案**：
  1. Qt 密度条实现 Slider 语义：方向键、Home/End、PageUp/PageDown，以及 Accessible role 和数值。
  2. 轴标签说明改成 `Axis: packet index (no PCR/TDT clock available) ⓘ`。有时钟时可以切换为时间轴，但时间轴必须来自引擎证据，不能由前端推算。
  3. 在时间线上显示可拖动的 A/B 两个标记，与 Changes 标签的 A/B 输入双向同步。
  4. 历史芯片支持“按表类型过滤”，并在芯片上标注版本变化，例如 `SDT v3→4`。
- **验收**：Qt 时间线可以完全用键盘操作。A/B 拖动与数字输入保持一致。

---

## 8. 编辑与导出 — P0/P1
- **现状**：
  - 只能对**单 section SDT**改服务名。改名按钮在检查器底部，非 SDT 时**显示为禁用但不说明原因**；查看对比证据时也不可用。
  - Qt 对话框宽 500px，有服务选择、名称、Preview、版本变化文本、格式选择和 Save；保存的 FileDialog 使用 `DontConfirmOverwrite`。但引擎会拒绝已存在的目标（`core/main.cpp:1199`，报 “Output already exists; choose a new path”），所以**不会静默覆盖**。
  - 保存成功后 Qt 对话框保持打开，Web 自动关闭。
  - 没有“按原样导出当前快照”。
- **问题**：
  - 禁用按钮没有说明，用户不知道怎样才能编辑。
  - 选中已存在的文件时，用户要等到引擎报错才知道不能写（原生对话框不预先提示）。
  - 两端保存后的行为不一致。
- **方案**：
  1. **P1**（更正：原稿列为 P0“静默覆盖”风险，经核实不成立）：默认文件名带 `-edited` 后缀和版本号，减少撞名；保留引擎的拒绝覆盖作为权威保护。
  2. **P0**：禁用时给出原因 tooltip，例如 “Only single-section SDT supports rename · current: PMT” 或 “Unavailable while viewing comparison evidence”。
  3. **P1**：统一保存后的行为：两端都在保存后保持对话框打开并显示 “Saved to … · Open folder · Close”。这样用户能确认 manifest 路径，再自己关闭。
  4. **P1**：编辑入口从检查器底部移到 Services 行的上下文菜单 “Rename service…”，并在检查器摘要条中保留一个入口。
  5. **P1**：Preview 用 §4.6 的结构化 diff 展示 `name` 和 `version_number` 的变化（Web 已显示 3→4，Qt 也应显示）。
  6. **P2**：加 “Export snapshot as-is (TS/BIN + manifest)”，复用现有导出管线，不做编辑。
- **验收**：引擎继续拒绝已存在的目标。禁用状态都有说明。两端保存后的行为一致，并有功能测试。

---

## 9. 其他工作区与对话框

### 9.1 DVB-I XML 工作区 — P1
- **现状**：
  - Qt `DvbiWorkspace.qml` 有 Open…、Service list / XML tree、Root / Parent / Back、Previous/Next children、Previous/Next bytes 和 “Load more objects (n)”。说明文字很长，例如 “ETSI TS 103 770 V1.2.1 · local metadata declarations · no network fetch, playback or TS association · bounded import without asynchronous cancel”。
  - Web `dvbi.js` 结构类似，包括 Import XML、Unknowns and conflicts 等。
- **问题**：
  - 范围声明是很长的一句话，用户难以扫读。
  - 分页式的 “Previous/Next children/bytes” 很像调试工具，不像编辑器。
  - 搜索只覆盖已加载的对象，虽然有提示，但不够醒目。
- **方案**：
  - 范围声明改成 3 个 chip（`Local only` `No playback` `No TS association`），tooltip 显示完整说明。
  - XML 树用懒加载展开（展开节点时请求子节点），取代 Previous/Next 分页按钮。字节分页改成可滚动的虚拟 hex 视图。
  - 搜索框内显示 “Searching 120 / 3,400 loaded objects”，并提供 “Load all to search” 动作。
  - 把 “Unknowns and conflicts” 做成带计数的徽章，放在顶部。
- **验收**：原有的分页 API 仍然可用（作为懒加载的实现细节）。两端结构一致。

### 9.2 About / Updates（仅 Qt `UpdateDialog.qml`）— P2
- **现状**：对话框以长段落说明手动下载 ZIP、核对 SHA-256、解压到新目录的流程，提供 Download installer / Portable ZIP / Install and quit 等按钮。
- **方案**：
  - 把步骤改成带编号的步骤列表，SHA-256 旁加复制按钮。
  - “My work is saved · Install and quit” 的确认改成复选框加主按钮。
  - Web/Tauri 端至少在 About 中显示版本号和 Release page 链接，保持功能对等的说明。

### 9.3 Agent API / Save diagnostics — P2
- 移到“开发者”菜单（见 §2.1）。
- Save diagnostics 完成后显示保存路径和 “Open folder”；失败时按 error 级别显示（见 §2.4）。

---

## 10. 键盘与可访问性 — P0（一致性）/ P1

| 动作 | Qt | Web | 建议（两端统一） |
|---|---|---|---|
| 记录搜索 / 命令面板 | Ctrl+K | Ctrl+K | Ctrl+K |
| 树搜索 | Ctrl+Shift+K | 无 | Ctrl+F（检查器内），保留 Ctrl+Shift+K 作别名 |
| 打开文件 | Ctrl+O | 无 | Ctrl+O |
| 分析 | Ctrl+Return | 无 | Ctrl+Return |
| 取消 | Ctrl+. | 无 | Ctrl+. / Esc（扫描中） |
| 焦点轮转 | F6 | 无 | F6 / Shift+F6 |
| 返回 | Alt+Left（与调整检查器尺寸**重载**） | Alt+Left | 只用于导航返回；尺寸调整改为 Ctrl+Alt+方向键 |
| 时间线 | 无键盘 | 方向键/Home/End | 两端相同 |
| 帮助 | 无 | 无 | `?` / Ctrl+/ |

其他：
- **Alt+Left 重载**（P0）：同一个快捷键既用于“返回”又用于“调整面板尺寸”，结果取决于焦点，难以预测。应该拆开。
- **焦点可见**：已有 2px 焦点环。需要检查所有自定义 `<div>` 按钮是否都可以 Tab 到达。
- **屏幕阅读器、缩放、强制颜色模式**：UI_UX_STANDARDS.md 已列为待办。建议使用 Windows Narrator 和 NVDA 各做一轮手工验证，并把结果作为环境限定的验证记录写进文档。
- **对比度**：浅色主题下仍有硬编码深色背景（如 `#5a1d1d`）。需要改成令牌并纳入现有 WCAG 测试。

---

## 11. 主题、布局与视觉令牌 — P1
- **现状**：
  - Qt 在 `Main.qml:18-53` 定义了令牌。文件中共有 62 处 `"#rrggbb"`，但大多数是两端共享、由测试约束的表类型色板。真正绕过令牌的只有约 5 处：密度条 `#3794ff`、游标描边 `#181818`、错误状态栏 `#5a1d1d` / `#ffffff`，以及主按钮 `#006fb9` / `#086fae`（更正原稿的“62 处硬编码”）。
  - `style.css` 有 56 个 CSS 变量，但有 **193 处**十六进制字面量。
  - Web 的 `index.html` 把 `color-scheme` 固定为 dark，主题状态存在 localStorage。
- **问题**：新增浅色主题或高对比度主题时，必须逐处修改，很容易漏掉。两端颜色值也可能漂移。
- **方案**：
  1. 建立一份共享的 `tokens.json`：surface、panel、raised、divider、ink、muted、accent，加上语义字段色、diff 色、严重度色。构建时生成 QML 单例 `Theme.qml` 和 CSS 变量。
  2. 加一个 lint 规则：`Main.qml` 和 `style.css` 中禁止新增十六进制字面量，只有 tokens 文件例外。
  3. 精简 surface/border 层级（UI_UX_REFRESH.md 已提出），目标是 3 级表面和 2 级边框。
  4. `color-scheme` 跟随当前主题动态设置，避免浅色主题下滚动条和表单控件仍然是深色。
  5. 增加“跟随系统”主题选项。
- **验收**：lint 通过，两端颜色由同一来源生成，WCAG 对比度测试覆盖所有令牌组合。

---

## 12. 工程层面（影响 UX 的长期质量）

### 12.1 QML 测试脚手架混在生产文件中 — P1
- **现状**：`Main.qml`（约 4900 行，302 KB）内有 25 个测试 Timer（`smokeTimer`、`exportTestTimer`、`comparisonTestTimer` 等）。
- **问题**：AGENTS.md 要求“测试专用门控必须在编译期从生产二进制中排除”。QML Timer 即使由环境变量门控，也会打包进生产 qrc。同时文件过大，难以维护和评审。
- **方案**：
  - 把测试驱动移到 `ui/qt/test/` 下的独立 QML 或 C++ 测试工具。只在测试构建时通过 CMake 把它加入 qrc（例如 `if(SHOWPSISI_UI_TESTS)`）。
  - 同时把 `Main.qml` 拆成 `Shell.qml`、`Explorer.qml`、`RecordPane.qml`、`Inspector.qml`、`Timeline.qml`、`RenameDialog.qml`。
- **验收**：生产 qrc 不包含测试 Timer。原有 UI 测试在测试构建中仍然通过。

### 12.2 Web 整页 `innerHTML` 重渲染 — P2
- **现状**：`app.js` 中有 25 处 `innerHTML`，`render()` 每次都重建整个页面。
- **问题**：
  - 重建后焦点和滚动位置可能丢失，代码需要额外恢复。
  - 大表格的重渲染成本高。
  - 字符串拼接 HTML 需要处处转义，存在注入风险，尤其是 XML 和服务名这类不可信数据。
- **方案**：渐进式改为按区域局部更新。只在数据变化的面板上重建，并用 `textContent` 或模板元素写入不可信文本。不需要引入框架。
- **验收**：切换标签后焦点保持不变。通过专门构造的恶意服务名样本验证没有 HTML 注入。

### 12.3 i18n — P2
- **现状**：`qsTr` 使用次数为 0，Web 也没有消息表。
- **方案**：
  - 先把用户可见的字符串集中到 `strings.json`（两端共享键）。Qt 用 `qsTr`，Web 用一个简单的查表函数。
  - 规范缩写（PAT、SDT、CRC…）和十六进制格式不翻译，只翻译说明文字。
  - 首个目标语言建议为简体中文。

### 12.4 中文 Windows 构建失败（开发者体验）— P1
本次在 code page 936 的系统上执行 `scripts/build.ps1 -SkipTauri`，观察到两个问题：
1. MSVC 按 GBK 解析 UTF-8 源文件 `third_party/expat/lib/random_rand_s.c`，报 `C4819` 和 `fatal error C1020: 意外的 #endif`。
2. 通过 `CFLAGS/CXXFLAGS=/utf-8` 规避后，Qt 目标的资源编译 `assets/icons/showpsisi.rc` 失败，报 `RC1107: invalid usage`。命令行中出现了本地化的依赖前缀 `"注意: 包含文件:  "`，怀疑是 CMake/Ninja 的 RC 依赖扫描在本地化的 MSVC 输出下出了问题（也可能与注入的 CFLAGS 有关，未进一步隔离）。

- **方案**：
  - 在 CMake 中对 MSVC 统一添加 `add_compile_options($<$<COMPILE_LANG_AND_ID:C,MSVC>:/utf-8> $<$<COMPILE_LANG_AND_ID:CXX,MSVC>:/utf-8>)`，只作用于 C/C++，不影响 RC。
  - 在 `build.ps1` 中设置 `VSLANG=1033`，让 MSVC 输出英文，避免本地化的 `/showIncludes` 前缀。
  - 在 `docs/CLOUD_DEVELOPMENT.md` 或 README 中记录这一环境限制。
- **验收**：在中文区域设置的 Windows 上，从干净目录执行 `build.ps1` 可以成功（需要在该环境实测并记录）。
- **状态（已落地，见 §14.3）**：根因已隔离。`/utf-8` 必须在 expat 之前、并且只作用于 C/C++；RC1107 与编译选项无关，是 Ninja 的 `cmcldeps` 包装器把本地化前缀转发给了 rc.exe（手动运行 rc.exe 正常）。本机未安装英文语言包，`VSLANG=1033` 不生效，所以改为关闭 RC 的 cmcldeps 依赖扫描。

---

## 13. 实施路线建议

| 阶段 | 内容 | 主要风险 |
|---|---|---|
| **P0（1–2 迭代）** | §5.1 检查器摘要条；§5.5 Metadata 拆分；§2.2 源栏统一；§4.1 Qt 服务列表压缩；§5.3 Qt Hex ASCII；§4.6 结构化 diff；§8 禁用原因；§10 快捷键统一与 Alt+Left 去重载；§2.4 错误分级 | 改动 Main.qml 的大块区域。建议先做 §12.1 拆文件，以降低冲突 |
| **P1（2–3 迭代）** | 排序/过滤（共享 `workbench.js`）、命令面板、拖放与最近文件、时间线键盘与 A/B 拖动、字段↔字节联动（需要引擎输出偏移）、引用跳转、DVB-I 懒加载树、令牌统一、构建修复、测试脚手架迁出 | 字段偏移需要扩展引擎 JSONL 协议，要同步 PROTOCOL_COVERAGE.md |
| **P2** | EPG 时间网格、i18n、Web 局部渲染、Update 对话框改版、导出原样快照、References 去重 | — |

**每项落地时都应满足**：两端功能不回退；在真实引擎上用 `samples/generated/lab.ts` 做功能测试；不使用 owner-machine 路径；Windows 交互结论只在实际交互验证后写入 STATUS.md。

---

## 14. 按“高级且易用、美观且克制”复盘，以及本轮落地

### 14.1 标准拆解

对一个协议分析工作台来说，这四个词可以落成可检查的规则：

| 标准 | 含义 | 可检查的规则 |
|---|---|---|
| **高级** | 质感来自秩序和一致，不靠装饰 | 颜色全部来自令牌，两种主题成对定义；圆角、字号、间距只用少数几档；状态色只表达语义 |
| **易用** | 下一步做什么一眼可见；不可用时说明原因 | 被禁用的动作必须给出原因；统计数字可以直接跳转；常用动作有快捷键，并且帮助里写明 |
| **美观** | 密度适中，对齐稳定 | 等宽 Hex 列固定宽度；列表行高收紧；层级靠字号和字重区分，不靠边框堆叠 |
| **克制** | 次要信息不抢主信息 | 帮助文字默认折叠；次级按钮安静、分组；说明文字放进 tooltip；不新增颜色和动效 |

### 14.2 复盘结论（相对 §0–§13 的调整）

1. **“克制”优先于加功能。** 原方案里的命令面板、EPG 时间网格、拖放等属于加法，延后处理。本轮先做减法：去掉硬编码颜色，把常驻的帮助和说明文字收起来，把次级按钮降级。
2. **“易用”的最大缺口是沉默的禁用。** Rename / 编辑按钮在大多数 Section 上是灰的，但没有说明原因。这是本轮的首要修复（§8）。
3. **“高级”的最大破坏者是浅色主题里的暗色硬编码。** 例如对比摘要、变更徽标、搜索高亮在浅色主题下仍然是暗色块。统一改为令牌，并纳入 WCAG 对比度测试。
4. **Qt 端的“美观”问题集中在密度。** 服务行 94px、Hex 没有 ASCII 列、密度条不能用键盘操作。

### 14.3 本轮已实施的改动

**构建（§12.4）**
- `CMakeLists.txt`：MSVC 下 `/utf-8` 和 `/W3` 用 `$<$<COMPILE_LANGUAGE:C,CXX>:...>` 限定为只作用于 C/C++，并移到 expat 之前；Windows 下设置 `CMAKE_NINJA_CMCLDEPS_RC OFF`。在 code page 936 的本机上，`build.ps1 -SkipTauri` 可以完成构建。

**Web（`ui/tauri/web/app.js`、`style.css`）**
- **令牌化**：新增浅色和深色主题成对的令牌，包括 `--label-text`、`--value-text`、`--changed-text`、`--changed-strong`、`--warn-text`、`--private-text`、`--danger-bg/-text`、`--density-fill`、`--match-bg`、`--placeholder`、`--scrollbar`。对比摘要、变更徽标、对比侧栏和上下文、变更值、搜索高亮、占位符、滚动条、密度条、到达摘要等不再写死暗色。
- **标题栏分组**（§2.1）：“主题 / 重置布局”为一组，“About / API / 诊断”为安静的三级组，中间用细分隔线隔开。按钮 id 不变，按钮始终可见（测试要求 `#reset-layout` 可以直接点击，所以没有做溢出菜单）。
- **统计可跳转**（§2.3）：Services / Tables / Issues 统计改成按钮，点击后切换到对应的标签页；SCAN 仍然是纯文本。
- **快捷键**（§10）：新增 `Ctrl/⌘+O`（Browse）和 `Ctrl/⌘+Enter`（Scan）。对话框打开或 DVB-I 工作区激活时不触发；源路径输入框保留它自己的 Enter 扫描行为。
- **侧栏帮助折叠**（§3.1）：常驻的帮助段落改为 `<details>`“Keyboard shortcuts”，用 `<kbd>` 列出导航、Ctrl K、Ctrl O、Ctrl Enter、Alt ←。
- **禁用原因**（§8）：新增 `editBlockReason()`，按优先级给出原因：后端断开、分析进行中、正在查看对比证据、不是 SDT、CRC 无效、SDT 未列出服务。原因显示为编辑按钮的 `title`。
- **Scope 说明收进 tooltip**：原来常驻的 `.meta` 说明移到 `.scope-tabs` 分组和各按钮的 `title`。
- **结构化对比值**（§4.6）：对象值不再显示为整段 JSON，而是逐行 `key: value`；嵌套对象和数组压缩显示，超过 2 层时回退到 JSON。标识符查询结果也用同样的格式。
- **可读的命名空间选项**：例如 `CA system ID (conditional access)`、`OUI (organizationally unique identifier)`。`value` 仍然是原始键，保持与引擎协议一致。
- **节奏统一**：圆角统一为 4px，对话框为 8px；最小字号 11px；统计数字 15px；检查器 `h2` 15px；空状态图标改小、改淡。

**Qt（`ui/qt/Main.qml`）**
- 新增成对的令牌 `errorSurface` / `errorInk`，状态栏在出错时用它们；密度条和游标的硬编码颜色改为 `blue` / `surface`。
- **禁用原因**：新增 `editBlockReason()` 和 `renameBlockedReason` 标签，语义与 Web 一致。
- **统计**：文案改为 “CRC failures”，悬停时用 tooltip 解释 CRC。
- **服务行**（§4.1）：行高从 94 降到 72；类型和 V/A PID 合并成一行 11px 的元信息。
- **Hex**（§5.3）：每行改为“偏移 + 16 字节（固定 47 列）+ ASCII”，与 Web 对齐；拓扑高亮的行跨度同步改为 72 字符。
- **密度条键盘**（§10）：可以用 Tab 聚焦，`Accessible.Slider`；←/→ 单步，Home/End 跳到两端，PageUp/PageDown 跨约 1/10；有可见的焦点环。

**测试**
- `tests/test_ui_contrast.py`：新增的 Web 文本令牌全部纳入 6 种背景下 ≥4.5 的检查；成对检查 `danger-text` 在 `danger-bg` 上、`changed-strong` 在 `match-bg` 上的对比度；Qt 检查 `errorInk` 在 `errorSurface` 上的对比度。

### 14.4 验证结果与边界

在本机（Windows 11，code page 936，真实 `showpsisi-core` 引擎 + `samples/generated/lab.ts`）上，改动前后用同一套命令对比：

| 套件 | 改动前基线 | 改动后 | 结论 |
|---|---|---|---|
| `test_ui_contrast.py` | — | 6/6 OK（含新增令牌） | 通过 |
| `test_web_ui.py`（Playwright + Chrome） | 59 个测试：7 个 failure、3 个 error、2 个 skip | 完全相同的 10 个用例失败 | 无新增回归 |
| `test_qt_resource_paths.py` + `test_qt_evidence.py` | OK | 18/18 OK | 通过 |
| `test_qt_ui` / `dvbi` / `topology` / `protocol_cards` | 几乎全部超时（Qt 没有写出结果 JSON） | 未重跑完整套件 | 本机环境无法运行，见下文 |

- Web 的 10 个基线失败与本轮改动无关：7 个取消测试依赖过期的 `showpsisi-core-test.exe`（2026-10-18 构建，需要 `SHOWPSISI_BUILD_CANCELLATION_TESTS=ON` 重建）；3 个导出测试是 Windows 上的独占创建或超时问题。
- Qt scripted 测试在**改动前的基线二进制上**就已经超时：进程存活，但不写跟踪、日志或结果。所以这些测试不能作为本轮 Qt 改动的通过或失败依据。
- Web 端另外用 Playwright 观察：点击 Issues 统计后切换到 Issues 标签页；编辑按钮的 `title` 显示禁用原因；没有页面错误。这一项只是观察，不替代测试。

**未验证、仍需单独确认的内容**：
- 没有在原生 Windows 桌面上做 Qt 或 Tauri/WebView2 的人工交互。Web 结论来自真实引擎 + Playwright（Chrome），不等于 Tauri 通过。
- Qt 的服务行、Hex ASCII、密度条键盘、禁用原因标签，目前只确认了 `Main.qml` 能通过 qmlcachegen 编译。本机 offscreen 启动后进程存活，但不产生日志、跟踪或测试结果；改动前的基线二进制也是这样，所以还不能确认 QML 运行时加载正确，需要在能运行 Qt 测试的环境（CI 或干净 Windows）复验。
- 截图只用于观察视觉，不作为功能结论。

### 14.5 第二阶段：由 Codex 执行、逐轮审查（分支 `ui/ux-refinement`）

第二阶段由 Claude 规划并审查，Codex CLI 负责实现。每一轮都按同一个流程走：
1. 写出任务说明。所有轮次共享同一份规则：遵守 AGENTS.md、两端同步、颜色只用令牌、保留测试依赖的 id 和 objectName、保持 CRLF。
2. Codex 实现。
3. 审查 diff，重点看删掉的测试行和新增的硬编码颜色。
4. 构建 Qt，跑对比度测试和完整的 Web 测试套件，结果与基线比较。
5. 如果出现回归，退回 Codex 修复；修好并通过后，单独提交。

| 轮次 | 提交 | 内容（对应章节） | 审查发现并退回修复的问题 |
|---|---|---|---|
| R1 | `bbcc75c` | §2.2 源栏统一为 路径 → Standards → Scan options ▾（Charset、Extra PIDs）→ Analyze；折叠时显示非默认值的摘要；参数变化后提示重新分析；Qt 的 charset 从 Metadata 移到源栏。§2.3 Qt 统计可点击跳转；Issues 按严重度计数。§10 Web 加 `Ctrl+.` 和 `F6` / `Shift+F6` | 无 |
| R2 | `6bf8e96` | §10 Alt+←/→ 只用于导航，面板尺寸改为 Ctrl+Alt+方向键。§2.4 消息分三级：info 4 秒后淡出；warning 常驻并计数；error 显示可关闭横幅。另有最近 50 条消息的历史（Esc 关闭）和 `aria-live` 分级 | DVB-I 工作区下 TS 页脚重新显示（`test_dvbi_independent_session…`）→ 已修复 |
| R3 | `ca10fff` | §5.1 检查器头部压缩成一行摘要条（表、PID、版本、section、CRC、到达次数、标准、Scope）；详情可展开且会持久化；截断和解码器注释合并为一行警示条 | 标准上下文被折叠后不可见（`test_standards_context…`）→ 已加常驻标准 chip；摘要辅助函数补上空值保护 |
| R4 | `0a5a87d` | §5.5 Metadata 拆成 Section metadata 和 Lookup 两组；查询结果改为键值表，带来源列，原始 JSON 收进 Raw 折叠区；“not verified” 等标记保留；Qt 命名空间显示可读名称 | 无 |
| R5 | `7da52c0` | §4.6 字段级 A → B 差异，数值同时显示十六进制和十进制，嵌套可展开；`+N / −N / ~N` 改为过滤芯片；每侧的次级动作收拢。§7 时间轴标注改为 “Axis: packet index” 并加说明。新增 `--added-text` / `--removed-text` 令牌，已纳入对比度测试 | 无 |
| R6 | `b70ee96` | §6 拖放文件（只填入路径，不自动分析；浏览器预览会明确提示该功能需要桌面版）；最多 10 条最近文件（沿用现有设置存储）；`?` / `Ctrl+/` 打开快捷键帮助浮层，内容来自同一张快捷键表 | 无 |
| R7 | `27db7f9` | §5.2 Structure 树中的引用跳转：只对标准表中由“表 + 字段名”确定语义的字段显示 “→”（PAT program_map_PID、PMT elementary_PID / PCR_PID、SDT/EIT service_id、CAT 中已解码 CA_descriptor 的 CA_PID）；私有描述符、保留值、0x1FFF、目标不存在或不唯一时不显示链接。Ctrl+Enter 跳转，Alt+← 返回（复用现有返回栈） | Qt 的 Ctrl+Enter 原本会抢走“重新分析”快捷键 → 只在 Structure 树聚焦且当前行有引用时才跳转；Qt 脚本在新行布局完成前点击 → 加一次布局 tick；Web 测试对路径的假设过窄 → 改为任意 `/descriptors/` 路径 |
| R8 | `9ce1e2a` | §7 时间轴上可拖动的 A/B 标记（Slider 语义，可键盘微调），与 A/B 输入框双向同步；密度条高度 20 → 28 | 拖动按像素量化，测试要求精确包号 → 两端测试按 `ceil(包数/像素宽)` 容差比较并与实时值核对；Qt 中 Shift+Tab 从 A 无法回到密度条 → 显式处理 Tab 顺序 |
| R9 | `698d460` | §6 命令面板：Ctrl+K 搜索框支持 `>` 命令（与快捷键帮助共用同一张表，未加载时禁用并给出原因）和 `#` 标识符跳转（`#0x0100`、`#pid`、`#sid`、`#table`，十六进制按正确位宽显示，找不到时给出提示，跳转可 Alt+← 返回）；普通文本仍是记录搜索。Web 为 combobox/listbox 语义，Qt 为 ComboBox 可访问角色 | Qt 6.7 的 JS 引擎没有 `String.prototype.trimStart`，导致搜索框 `query` 不再更新，记录过滤全部失效（13 个 Qt 用例失败）→ 改为正则；空搜索框按 Esc 会把焦点移走，违反原有“Esc 清空并保留焦点”的约定（`input_focus`）→ 两端都只在面板打开时恢复焦点 |

**每轮最终结果**：
- 构建：Qt 构建通过，QML 通过 qmlcachegen 编译。
- `test_ui_contrast.py`：6/6 通过。
- `test_web_ui.py`：测试从 59 个增加到 64 个，新增的都是 Codex 加的回归测试；失败的始终是同样 10 个基线用例（7 个取消测试，3 个导出测试），没有新增失败。
- `test_qt_resource_paths` + `test_qt_evidence`：18/18 通过。

**验证边界（重要）**：
- R1–R6 期间本机 Qt scripted 测试不产生结果。原因已查明并记录在 [CLOUD_DEVELOPMENT.md](CLOUD_DEVELOPMENT.md) 的 “Local Windows Qt interaction tests” 一节（DLL 搜索路径、仓库外写入被拦截、字体目录、GBK 区域设置）。按该节配置环境后，R7–R9 的 Qt 套件均在本机完整运行；R1–R6 的 Qt 改动同时由 PR 的 GitHub CI Windows 原生检查覆盖。
- 本机 offscreen 运行通过不等于原生 Windows 桌面交互通过。
- Tauri/WebView2 原生拖放、原生窗口下的焦点和快捷键，都没有在桌面上手动验证过。

### 14.6 仍未做的部分

- §5.2 字段 ↔ 字节联动：需要引擎在 JSONL 中输出 `byte_offset` / `bit_offset`，属于引擎和协议改动，要同步 PROTOCOL_COVERAGE.md。
- §2.1 溢出菜单：测试要求 `#reset-layout` 直接可见，所以本次只做了分组。
- §12.1 把测试脚手架拆出 Main.qml：本机 Qt 测试现已可运行，可以作为单独一轮推进。
- P2：EPG 时间网格、i18n、Web 局部渲染、Update 对话框改版、References 去重。
