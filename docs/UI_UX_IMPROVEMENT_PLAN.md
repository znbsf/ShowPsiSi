# ShowPsiSi UI/UX 改进方案（2026-11-03 重新整理）

> 基线：`main` @ `12b78aa`（PR #30 合并后）。本文取代 2026-10-20 版的改进方案。旧版 §0–§14（编辑器风格分析、R1–R9 实施记录）保留在 git 历史中：`git show e80dabb:docs/UI_UX_IMPROVEMENT_PLAN.md`。
>
> **为什么重新整理**：10 月 25 日起，用户明确要求核心 SI 工作台使用 **NxTSA 原版外观**，不再沿用现代深色编辑器风格（见 [UI_UX_STANDARDS.md](UI_UX_STANDARDS.md) 顶部）。规则是先对齐原版功能，再由用户决定 UX 上的差异（见 [NXTSA_UI_UX_PARITY.md](NXTSA_UI_UX_PARITY.md)）。PR #30 已在本地完成 01–17 项功能对应，所以现在正是“用户决定 UX 差异”的阶段。本文就是这份待决定清单。

## 0. 结论

1. **产品现在有两套视觉语言。** 默认是经典 NxTSA 框架（菜单、7 个位图按钮、白底树、Courier 字段表、双 hex、MDI 子窗口）；**View → Advanced workspace** 是 10 月的现代工作台（Services/Topology/Tables/EPG/Issues/Changes、Ctrl+K 命令面板、引用跳转、A/B 对比）。两者共享选择（从经典 PMT 0x0102 切过去仍选中同一 PMT），但视觉、键盘和信息组织完全不同。这是当前最大的 UX 决策点（§3 B1）。
2. 经典框架的主路径能用，而且接近原版：树 → 表 → 字段 → 两个 hex 面板双向高亮、右键 View Tables / Service EPG / Packet Explorer、Summary 六项、MDI 子窗口和 Window 菜单都已实测。
3. 剩下的问题分四类：
   - **A**：不改变原版外观的缺陷，可以直接修；
   - **B**：偏离原版的改进，需要用户逐项拍板；
   - **C**：Advanced workspace 后续怎么处理；
   - **D**：工程债，影响后续 UX 迭代的速度和可审查性。
4. 建议顺序：先补齐 #30 的托管 CI 基线 → 修 A 类 → 用户决定 B 类 → 格式化长行代码 → 实现已批准的 B 项。在 B1 决定之前，Advanced 只维护、不加新功能。

## 1. 现状盘点（2026-11-03）

| 层 | 入口 | 内容 | 视觉 |
|---|---|---|---|
| 经典 SI 工作台（默认） | 启动即是 | File/View/Analyzer/Window/Help 菜单，Open/Save/Start/Stop/Pause/Tree/Print 按钮；左侧 Programs / PSI Packets / All Packets / DSMCC 树；右侧 Field/Bits/Value/Comment 与两个 hex 面板；Summary/Error、Bitrate/Timing、Services/EPG、DSM-CC/OC、Teletext、PES/ES/Media、Native Decode、Packet Explorer 子窗口 | 原版固定浅色调色板，不跟随主题 |
| Advanced workspace | View → Advanced workspace；“SI Inspector” 按钮返回 | 10 月 R1–R9 的全部成果 | 令牌化深/浅主题 |
| DVB-I XML 工作区 | View → DVB-I XML document | 独立文档工作区 | 沿用 Advanced 风格 |

旧版方案各项现在的去向：
- §2 源栏/统计/消息、§4 记录区各标签、§5 检查器、§6 搜索、§7 时间线：只存在于 Advanced。经典框架用菜单、树和 Summary 子窗口实现等价用户结果。
- R7 引用跳转、R9 命令面板只在 Advanced 中可用。经典框架里 Ctrl+K 聚焦的是左下角 “Find SI table” 输入框。
- §5.2 “字段 ↔ 字节联动需要引擎输出偏移”：经典框架已经实现（字段与两个 hex 面板双向高亮，无映射字节会清除旧高亮）。Advanced 的 Hex 视图还没复用这条路径。
- §12.1 测试脚手架拆分：`Main.qml` 从 PR #27 时的 6,208 行增长到 6,908 行，问题更严重了，见 D1。

## 2. A 类：不改变原版外观、可直接修的缺陷

以下均为本次在真实引擎上观察到的现象（Web 经典框架：`scripts/cloud_preview.py` + `samples/generated/lab.ts`；Qt：`scripts/qt_capture.py --real` 离屏截图）。“两端”表示两端都要核对，修复时两端一起验收。

| ID | 现象 | 位置 | 修法 |
|---|---|---|---|
| A1 | Summary 说明第二行以 “unavailable; no measured PCR clock.” 开头，缺少主语，用户不知道是什么不可用 | 引擎 `rate_basis` 原样拼接：Web `transport-si.js:11`、Qt `TransportSummary.qml:127`、`StatisticsView.qml:30` | 前端加 “BitRates basis: ” 标签；文字仍来自引擎，不在 UI 里改写语义 |
| A2 | 还没打开任何文件时，左侧 hex 面板显示 “Original packet unavailable for this section.” | Web 经典空状态（Qt 待核对） | 无 section 时显示中性空状态，或留空，与原版一致 |
| A3 | 选中 PAT 时，Web 标题是 `lab.ts · PAT : PAT · PID 0x0000 · 0x1001 · v1 current · §0/0 · ×178`，Qt 是原版格式 `PAT : 0x0003 PID[0x0000] Version 17`。Web 的 PMT 已是原版格式 | `inspector-model.js:153–154` 的通用回退分支和 `:126` 的原版格式分支 | 让 Web PAT 走原版格式分支；`§`、`×` 这类符号不进入经典标题 |
| A4 | 覆盖率行措辞两端不同：Web `Coverage · full · … · observed ranges [start, end): …`，Qt `Full coverage · … · [0, N)` | `app.js:854`、`Main.qml:204` | 统一一个共享格式函数，两端都调用 |
| A5 | 状态栏不一致：Web 选中服务后左侧状态文字被清空；完成文字 Web 为 “Analysis complete”，Qt 为 “Scan complete”；版本格 Web 为 “development”，Qt 为 “0.3.1” | 两端状态栏 | 共享状态文字表；版本格两端取同一来源 |
| A6 | 树中 `LCN ?`、`LCN conflict` 没有解释 | 经典树 | 只加 tooltip / Accessible.description（“LCN 未在 NIT/BAT 中声明”“多个服务声明了同一 LCN”），不改显示文本 |
| A7 | 左下角 `1 / 19`、Previous / Next 没有说明对象（实际是表实例的分页） | 经典树底部 | 加 tooltip 和可访问名称 |
| A8 | Summary 底部 Summary / Error 两个按钮，在截图中看不出哪个是当前页 | Web 经典 Summary（需对照原版和 Qt 核对） | 使用原版的按下态或标签页态 |

验收：每项用真实引擎跑两端，并补对应回归测试。不能只看截图。

## 3. B 类：偏离原版的改进（需要用户逐项决定）

每项给出推荐做法；不选则保持原版行为。

**已决定（2026-11-03）**：
- 用户选择 **B1 ②**：Advanced 冻结，B2–B4 作为方案 ② 的内容实施。
- B6 让 Summary 更接近原版对话框，同样实施。
- B5、B7、B9 仍待决定；B8 保持原版（只有浅色）。
- 实施状态见 §6.1：A1–A8、B2、B3、B4、B6 已在分支 `ui/classic-refinement` 完成。

| ID | 问题 | 可选方案 | 推荐 |
|---|---|---|---|
| **B1** | 两套视觉语言并存，切换时整个界面风格跳变 | ① 保持现状，两者独立；② 把 Advanced 的少数高价值能力，用经典样式做成经典菜单命令（见 B2–B4），Advanced 冻结；③ 把 Advanced 也改成经典样式 | **②**。改动最小，保留原版观感，常用能力不必切换世界 |
| B2 | 经典框架里没有按标识符跳转（R9 的 `#PID` / `#SID` / `#table`） | 加 Analyzer → “Go to PID/SID…”（Ctrl+G），经典对话框样式，复用 `workbench.js` 的解析和 R7 返回栈 | 做；不在经典里加 `>` 命令模式（菜单已覆盖） |
| B3 | 经典树里引用字段（PAT program_map_PID、PMT elementary_PID / PCR_PID 等）不能直接跳转 | 字段右键加 “Go to PMT · PID 0x0100”，复用 R7 的允许列表 resolver（同样排除私有描述符、0x1FFF、缺失或歧义目标） | 做；只加右键项，不加行内 “→” 图标，保持原版行外观 |
| B4 | Comment 列长说明被截断（如 “0: network signalling; otherwise program ident…”） | ① 悬停 tooltip 显示全文；② 选中字段时在状态栏显示全文；③ 允许换行 | ①＋②，不改变行高 |
| B5 | 键盘焦点只有 1px 点线框（原版样式），在白底和黄色选中行上很难看清 | ① 保持原版；② 只在键盘导航时加粗为 2px 深色框 | ②，鼠标操作时外观不变 |
| B6 | Summary 子窗口用系统无衬线字体和现代输入框，与 Courier 树表和原版对话框不一致 | 按原版 DIALOG_138（Tahoma / MS Sans Serif、凹陷字段框）统一 | 统一到原版对话框样式 |
| B7 | Packet Explorer 每行 16 字节，SI 双 hex 每行 10 字节 | ① 保持（需原版证据确认 Packet Explorer 的原版行宽）；② 统一 | 先补原版证据再定 |
| B8 | 经典框架固定浅色；Advanced 有主题切换 | ① 经典保持只有浅色；② 给经典加深色方案 | ①，符合“原版外观”要求 |
| B9 | Qt 启动时状态栏出现警告 “Recent files saved for this session only. ×1” 和 Dismiss | 判断这是隔离测试设置下才有的现象，还是普通用户也会看到；如果用户会看到，应降级为 info 或只在设置面板说明 | 先核对普通启动路径 |

## 4. C 类：Advanced workspace

- 在 B1 决定之前，只修缺陷，不加新功能。
- 如果选 B1 ②：
  - R7、R9 的解析逻辑保留在共享的 `workbench.js`，经典和 Advanced 共用，不复制。
  - 让 Advanced 的 Hex 视图复用经典已经实现的字段 ↔ 字节范围（这是旧版 §5.2 的主要缺口，现在引擎已提供）。
- 旧版未做项的处理：
  - 溢出菜单（§2.1）、EPG 时间网格、i18n、Update 对话框改版、References 去重：全部降为 P3，等 B1 决定后再评估；
  - Web 局部渲染（§12.2）：移到 D 类。

## 5. D 类：工程债（影响 UX 迭代）

| ID | 问题 | 建议 |
|---|---|---|
| D1 | `Main.qml` 6,908 行，测试脚手架仍混在里面；`app.js` 240 KB；PR #30 新增的 Web 模块大量写成超长单行（`inspector-model.js` 最长 11,710 字符/行，`carousel-view.js`、`teletext-view.js` 超过 3,000），diff 和审查几乎不可读 | 先做一次纯格式化提交（不改语义，跑全部测试）；然后把 `SHOWPSISI_SCRIPT` 测试场景拆到独立文件，仍按编译期排除 |
| D2 | 经典调色板以字面值硬编码在 QML/CSS 中（`#efefef`、`#a0a0a0`、`#808080` 等），`test_ui_contrast.py` 只覆盖令牌 | 建一个共享的经典调色板对象（与 `classic-model.js` 同级），两端引用，并纳入对比度测试 |
| D3 | PR #30 的提交全部带 `[skip ci]`，最新 `main` 没有托管 CI 结果 | 本地基线已补（见下）。托管 CI 仍需在推送本分支时运行 |
| D4 | 本机 Qt 交互测试需要特定环境（DLL 路径、仓库内 TEMP、字体目录、UTF-8） | 已记录在 [CLOUD_DEVELOPMENT.md](CLOUD_DEVELOPMENT.md)；建议加一个 `scripts/qt-test-env.ps1`，避免每次手工拼环境 |

### 5.1 本地基线结果（2026-11-03，`main` @ `12b78aa`）

`main` 在本机并不全绿。查明两个真实原因，已在 `ui/classic-refinement` 的 `3fa2d84` 修复：

1. **J.94 分析无法启动（用户可见回归）**：#30 新增的扫描配置校验（`output-model.js` 的 `scanSettings.validate`，两端共用）在标准白名单里漏了 `j94-system-b`。用户选 J.94 后只看到 “Unknown standards or scan mode”，分析不会开始，而引擎和两端的选择框都支持这个上下文。已补上，并新增测试，把校验白名单与 `api/tools.json` 中 analyze 的 standards 枚举对齐。
2. **12 个 Qt 布局 / 对比 / 引用用例失败**：#30 让窗口按 `Screen` 尺寸自适应，而 Qt offscreen 插件默认是 800×600 屏幕，窗口被限制为 760×540。测试环境现在通过 `offscreen:configfile=tests/qt_offscreen_screen.json` 声明 1920×1080 屏幕。产品行为不变。

此外，本机 Web 套件无法启动，原因是 Playwright 1.64 要求的 headless shell 没有安装。设置测试已支持的 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`，指向已安装的 Chrome 即可，无需下载。

修复后的本地结果：
- `test_qt_ui` 61/61、`test_qt_topology` 11、`test_qt_dvbi` 8、`test_qt_protocol_cards` 6、`test_qt_resource_paths` 8、`test_qt_evidence` 10、`test_protocol_presentation` 15、`test_unified_inspector` 5、`test_ui_contrast` 6；
- `test_web_ui` 98 个测试（13 skip），全部通过；
- Qt 组件测试（QuickTest，真实引擎）60 例通过。

`tests/verify_classic_si*.mjs` 需要 Hotbird 原始捕获，仓库内没有，本机未运行。

## 6. 实施顺序

1. D3：取得 main 的托管 CI 基线，并在本地跑一遍 Qt / Web 套件。
2. A1–A8：一个小 PR，两端同时改，每项配回归测试。
3. 用户决定 B1–B9：每项选“推荐 / 其他方案 / 保持原版”。
4. D1：纯格式化提交，然后拆测试脚手架。
5. 实现已批准的 B 项，每项单独提交，两端同步验收。
6. 按 B1 的结果处理 C 类。

### 6.1 实施结果（2026-11-04，分支 `ui/classic-refinement`，未推送）

| 提交 | 内容 |
|---|---|
| `3fa2d84` | 恢复 J.94 分析；离屏测试声明桌面尺寸屏幕 |
| `519d6ea` | A1–A8：两端统一文案、标题、覆盖率、状态与 Summary 当前页 |
| `de48978` | B2 Go to PID/SID（Ctrl+G）；B3 字段右键、Shift+F10、菜单键、Ctrl+Enter 引用跳转，含文档子窗口 |
| `02e5601` | B4 完整注释；B6 Summary / 统计视图的原版对话框外观 |

审查和运行中修掉的问题（均有回归覆盖）：

- `Dialog.result` 是 FINAL 属性，同名声明使 Main.qml 无法加载。
- 自定义 `background` 让字段右键菜单宽度变成 0，无法点击。
- 真实引擎的 inspect 是异步的：详情到达时 navigation 没有重建，Back 的 `pendingRestore` 永远不完成。组件测试的宿主是同步的，只有真实程序场景能测出来。
- Back 恢复了 `selectedFieldIndex` 却没同步 `currentIndex`，键盘命令会作用在第 0 行。
- 行级 tooltip（名称 + 值）被替换后值列截断内容不可见，已补回。

本地结果：`test_qt_ui` 64、拓扑 11、DVB-I 8、协议卡片 6、协议展示 15、资源路径 8、证据 10、统一检查器 5、对比度 6、扫描辅助 4 全部通过；Qt 组件测试通过（统一检查器 33、Summary 17、经典框架 5、文档窗口 3）。

未解决的已知问题：

- `tests/test_web_ui.py` 共 112 个（跳过 13）。整套运行时偶发 1–2 个用例等待 30 秒超时，每次是不同用例；单独重跑通过。启动时超时的现场是空白页（`#workspace-toggle` 不存在），另一些是分析未完成。
- 在不含 C3 的 `de48978` 上同样复现，因此不是 C3 引入的；根因未定位，是否早于 C2 也未确认。在定位前，Web 套件不能算作稳定全绿。

未验证：托管 CI、原生 Windows 桌面交互、Tauri、高 DPI、屏幕阅读器、与原版 NxTSA 的逐项视觉对拍。B5、B7、B9 未实施，等待用户决定。

## 7. 本次分析的验证边界

- Web：真实 `showpsisi-core` 引擎，通过 `scripts/cloud_preview.py` 在 Chromium 中操作 `lab.ts`：分析、选择服务、右键菜单、字段 ↔ hex 高亮、Summary、Packet Explorer、Window 菜单、切换到 Advanced 再返回、Ctrl+K 焦点。不是 Tauri/WebView2。
- Qt：`scripts/qt_capture.py --real`，真实样本 `tnt-uhf22-2019.ts`，本机离屏截图。只用于观察布局和文字，不作为功能结论。
- 未做：原生 Windows 桌面交互、Tauri、DPI、屏幕阅读器；与原版 NxTSA 的逐项视觉对拍（原版证据见 [NXTSA_BEHAVIOR_REFERENCE.md](NXTSA_BEHAVIOR_REFERENCE.md)）。A 类各项是否在 Qt 上也存在，需要在修复时逐项核对。
- 截图只用于观察，不替代功能测试。
