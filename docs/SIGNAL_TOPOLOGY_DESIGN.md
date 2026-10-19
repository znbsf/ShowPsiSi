# Signal Topology：有证据的语义对象树设计

状态：**独立版本设计与实施计划，尚未实现**。2026-10-19。用户已要求开发和测试，并明确在当前完整发布流程跑通后另行发布。本文不把设计当作已有三标准拓扑、字段跳转或新 API。当前实现事实以本次读取的 `e9efde4d7ad4bba84d4aa22a029ed72f9667fc23` 及工作区为基线。并行中的更新器改动不在本设计范围。

## 1. 产品决定

在现有中央页签加入 **Topology**，提供独立的语义对象树；保留左侧 PID/表导航，复用右侧证据检视器。三栏不变，不再添一条侧栏，也不复制现有 PID 树。

- **左：证据入口。** 仍是 All tables → PID + table type；用户点击后照常打开 Tables。
- **中：对象与关系。** Topology 按 DVB、ATSC 1.0、ISDB 的实际语义呈现不同树。它回答“这个信令描述了什么、如何关联”，不是另一种按表分组。
- **右：解释与溯源。** 默认显示所选对象的摘要、关系、未知项和全部来源。点击具体来源，原地切到现有 Structure / Hex / XML / Decoded / Metadata / References；中央对象树和展开状态保留。
- **下：现有时间工作台。** 当前截面、全文件到达密度、表历史保持原语义。拓扑是这个截面的派生观察结果，不是已经验证的物理接收链。

三个标准共用布局、状态模型、来源控件、键盘和颜色规则，**不共用一棵强行统一的 Network → TS → Service 树**。第一批有用范围也应分别具备三个标准的最小骨架；不能把 ATSC 和 ISDB 仅列为“以后换标签”。

### 为什么放在中央

实际检查了 `artifacts/parity-visual/web-dark-workbench.png`（1440 × 1000）及 `qt-native-light-workbench.png`（1180 × 812）：左侧约 180 px，适合紧凑 PID 列表，不适合四至六层的对象、身份和状态；中央列表已有可用宽度，右侧已承担证据检视。把新树塞进左栏会迫使对象名、标识和未知项截断，并与现有 PID 导航争抢空间。

采用中央新页也保留 Services 的快速节目列表。左侧无需模式切换；普通用户原有操作不变。Topology 不是默认替换 Services，也不强迫每次打开文件都学习新树。

## 2. 已有能力与必须补足的边界

实际阅读：`AGENTS.md`、`README.md`、`STATUS.md`、`ARCHITECTURE.md`、`REQUIREMENTS_AUDIT.md`、`UI_UX_REVIEW.md`、`OPERATIONS_PARITY_HANDOFF.md`、`UI_AGENT_DEBUG.md`、`PROTOCOL_COVERAGE.md`、`SATELLITE_ASSOCIATION.md`、`CLOUD_DEVELOPMENT.md`、`NATIVE_TAURI_VALIDATION.md`，以及下列实现。

| 当前依据 | 可以复用 | 不能当作已经具备 |
|---|---|---|
| `core/main.cpp` 的 `latest` / `completeGroup` / `derivedSnapshot` | 同截面、generation-safe 的有效 current 表选择；PAT-selected PMT；原始 section 身份 | `services` 主要由 PID 0x0011 的 actual SDT 产生，不能直接充当 ATSC/ISDB 完整语义清单 |
| `inspect`、`native_table_sources`、`merged` | 精确 section、合并代、原始 bytes、cutoff、全部组装来源 | 任意 SDK XML 属性都有精确字节范围；UI 树路径是稳定跨平台协议地址 |
| `core/SignalMetadata.h` | `wire_source`、部分 `field_path`、描述符/文本范围 | 现有 `field_path` 对全部重复 loop 项唯一；containing-descriptor offset 等于属性的精确 offset |
| `ui/tauri/web/workbench.js` | 无 DOM/Qt 依赖的共同表示、格式、搜索、树节点、历史 | 广播业务对象与标准关联算法；它不得演变成第二个解析引擎 |
| `app.js` 的 `inspect` / `snapshot` / `changeTab` / `comparisonSide` | 请求 epoch、多份比较来源、独立历史检视、恢复原工作区 | 普通 evidence 可直接复用 `comparisonEvidence` 的字样而不重构类型 |
| `Main.qml` 的 `inspect` / `inspectChange` / `restoreComparisonWorkspace` | 相同后端入口、右侧六视图、历史/比较上下文 | 当前单一 `selected` 同时代表 semantic object 和原始 section |

`OPERATIONS_PARITY_HANDOFF.md` 是旧审计快照。当前源码已有 Web BIN、Use snapshot、Qt 多来源与恢复逻辑；本文只继承其验收教训，不把旧缺口重新描述为本次已复现缺陷。新功能仍须实际跑双端交互，不能凭现有代码宣称这些扩展工作流已验证。

特别注意：现有 `services[].source_id` 是 section 证据字符串，**不是 ATSC 16-bit source_id**。新对象用 `evidence[].section_id` 表示来源，用 `atsc_source_id` 表示线上字段；不得复用同名字段造成串接。

## 3. 先建图，再投影为树

后端模型是有类型的对象和有来源的边；界面树只是其中一个确定性的投影。

- `contains`：该标准可证明的容纳关系，例如完整 PMT 中的 elementary stream。
- `announces`：NIT 宣告某个 transport；不等于捕获文件已收到该 transport 的数据。
- `maps_to`：例如 ATSC 虚拟频道映射至 MPEG program。
- `member_of`：service 在 bouquet 中；不是唯一父级。
- `references`：EPG、logo、PCR PID、CA、数据应用等引用；关系存在不表示内容已收到。
- `candidate_association`：有外部来源的候选关联，例如卫星标称轨位目录。

树节点出现一次；多父关系用带“引用”字样的别名节点或右侧关系列表。别名点击定位主对象，环路不递归展开。所有边也须有来源，不能仅给节点附一份泛化的来源。

没有完整业务身份的对象使用“观察对象”临时键，明确标为未解析；禁止把未知值补成 0、空字符串或已有对象的身份。名字、LCN、频率和轨位不作为全局唯一键。`Network ID` 与 `Original network ID` 分开展示。

## 4. DVB：网络／传输流／服务

建议投影（各行只在有证据时出现）：

```text
DVB · 当前观察截面
├─ Networks（网络，来自 NIT）
│  └─ Network · network_id
│     └─ Transport stream · ONID / TSID [本捕获已观察 | 仅被宣告]
│        ├─ Service · service_id · 名称
│        │  ├─ Components（PMT ES，已解析或未知类型）
│        │  └─ Related signalling（EPG / CA / applications，按实际关联）
│        └─ Delivery parameters（信令宣告的参数）
│           └─ Satellite candidates（关联引用；不是 TS 的已确认父级）
├─ Unassigned transports（未建立 NIT 网络关系的已观察 TS）
└─ Bouquets（BAT，非网络父级）
   └─ Bouquet → Service references
```

规则：

1. Network 来自 NIT 的 `network_id`；transport 身份以本分析/标准上下文内的 `(original_network_id, transport_stream_id)` 为主。`network_id` 不等于 ONID。NIT 对 transport 的 membership 是边；若多 NIT 均宣告，不复制实体或擅选一家。
2. NIT-other / SDT-other 描述的 TS 和服务标“仅被宣告”，与“本捕获已观察”区分。不能将当前 PAT 或相同 SID 的 PMT借给远端 TS。
3. Service 的已解析身份是 `(ONID, TSID, SID)`。PAT 的 program_number 和 PMT 的 program_number 按明确上下文关联；只有 PAT 指向的 PID + program_number 可以供应该服务的 PMT 组件。
4. 仅 PAT 可得 TSID/program_number 时，显示“Program 0x… · SDT 未观察”；保留观察身份，待有证据再解析，不伪造 ONID 或服务名称。PAT 的 program_number 0 是网络 PID 指示，不生成节目。
5. 完整 SDT 已有服务、但 PAT/PMT 缺失时保留服务，标明缺的关系；不得回用上一代旧 PMT。NIT 未收到时放入 Unassigned transports，不编造“Network unknown”实体。
6. Components 表示 PMT 宣告的 ES：PID、stream_type、语言、component_tag（存在时）和分类依据。未知 stream_type 保留原值，不归入 Audio/Video；PCR PID 是属性/引用，不能自动造出一条视频 ES。它们不证明媒体包存在或能播放。
7. Bouquet、LCN、区域/列表排序、运营商标签属于关系或属性，不能改变 transport 的主层级。LCN 冲突显示全部候选；没有唯一结果就不选一个排序号。
8. **TP 不等于 TS。** UI 不命名为“卫星 → TP → TS → 节目”的已确认实物树。delivery 记录用 Hz、sym/s、polarization 等原始参数；“transponder”物理身份没有独立依据时不创建。单个卫星候选仍是候选，不能成为确认父节点。
9. 卫星关联复用已有 `inspect.satellite_associations` 边界：仅支持的 DVB 描述符；ISDB 同 tag 不套 DVB 规则；目录缺项、捕获时归属、共轨多星都显式未知。

DVB 的规范依据：[ETSI EN 300 468 v1.19.1](https://www.etsi.org/deliver/etsi_en/300400_300499/300468/01.19.01_60/en_300468v011901p.pdf)，§5.2.1 NIT、§5.2.2 BAT、§5.2.3 SDT。上述 UI 投影属于产品设计，不是该规范规定的界面。

## 5. ATSC 1.0：PSIP／虚拟频道／MPEG program

这是 TS/PSIP 范围，**不包含 ATSC 3.0 的 IP、ROUTE 或 MMT**。

```text
ATSC 1.0 · 当前观察截面
├─ Virtual channel lineups（TVCT / CVCT 上下文）
│  └─ VCT context · 表头 TSID · TVCT 或 CVCT
│     └─ Virtual channel · two-part / one-part channel number · short_name
│        ├─ MPEG program reference · channel_TSID / program_number
│        │  └─ Components（经 PAT/PMT 验证的本捕获映射）
│        └─ Programme source reference · source_id（可关联 EIT/ETT）
├─ Unmapped MPEG programs（PAT 中存在但尚无 VCT 关系）
└─ PSIP context（MGT / STT / RRT 等关系摘要与证据，不复制 PID 树）
```

规则：

1. 主入口是虚拟频道，不造 DVB Network/ONID。TVCT 和 CVCT 上下文分开。VCT 表头 TSID 与每个频道的 `channel_TSID` 是不同字段；名称相近不代表相同对象。
2. TVCT 的 `major.minor` 是虚拟频道号；CVCT 同时支持 two-part 和 one-part 形式，显示必须按实际编码，不能把 one-part 强制变成 `major.minor`。它们不是 RF channel，也不是 DVB LCN。`source_id` 是节目来源/节目指南关联标识；多条频道可共享 source_id，不能把它当唯一频道 key。
3. 频道槽位在本分析的 VCT 上下文内由频道号形式和规范化频道号定位（two-part 使用 major/minor，one-part 使用解码后的单段号）；碰到重复冲突条目时，另保留带原始 entry locator 的 observation identity，不相互覆盖。mapping/source_id 变化作为关系变化；跨 lineup 或跨捕获不自动合并。
4. `(channel_TSID, program_number)` 只在可匹配的捕获 transport 上连接 PAT/PMT。没有匹配 transport、PAT 指向不同 PID、PMT 未齐或 program_number 不匹配时，显示未解析映射，并保留 VCT 原始值。
5. program_number 为 0 的 inactive 项和为 0xFFFF 的 analog 项不强绑 PMT。hidden、hide_guide、access_controlled、service_type 等保留具体语义，不能等同“无效频道”。
6. TVCT 的 carrier_frequency 不能提供已知 RF，规范将其置零；不据此造“0 Hz”载波。其它字段/适用规范中的频率也只标“宣告值”，不是测量或调谐确认。
7. MGT 提供 PSIP 表目录及 PID/版本等引用，不是地理网络或频道实体父级。STT 是时间信令；RRT 是分级上下文。右侧关系列表展示这些信息，原始逐表导航仍交给左侧。
8. source_id 与 ATSC EIT/ETT 的连接是独立证据边；最小范围可只给“相关 EPG/来源表”入口，不在树内展开庞大时隙。ETT 配对还须满足其类型/标识上下文，不能仅凭数字相同关联。
9. `service_location_descriptor` 可提供节目位置的独立声明。若与 PMT 不一致，要并列呈现和标冲突，不把它偷偷当作缺失 PMT 的已验证替代。

依据：ATSC [A/65:2013](https://www.atsc.org/wp-content/uploads/2021/04/A65_2013.pdf)，§6.3/§6.5 的 VCT、频道身份和节目映射，以及 §6.3.2 的 CVCT one-part 编号。SDK 支持某表不代表本应用已完成上述派生。

## 6. ISDB：区域 profile 下的网络／TS／服务

ISDB 复用部分 MPEG/DVB 形态，但有自己的 descriptor 语义、播出机构/下载/台标及地区配置。界面标题明确区分 **ISDB Japan**、**ISDB Brazil**、**ISDB · region unspecified**；不能由文字、国家名猜测 profile。

```text
ISDB Japan / Brazil / 未指定地区 · 当前观察截面
├─ Networks（NIT）
│  └─ Network · network_id
│     └─ Transport stream · ONID / TSID · TS 名称（若有）
│        ├─ Service · SID · 名称
│        │  ├─ Components（PAT/PMT；component_tag 等原始字段）
│        │  └─ Related signalling（EPG / data / logo reference）
│        ├─ Terrestrial / delivery information（适用描述符）
│        └─ Partial-reception service references（若明确宣告）
├─ Unassigned transports
└─ Broadcast / auxiliary context（按 profile 和证据展示关系）
   ├─ Broadcaster references（BIT）
   └─ Download / common-data references（SDTT / CDT 等）
```

规则：

1. NIT/SDT/PAT/PMT 的对象链接仍要求正确 profile、完整同代和明确标识关系。不能因为服务结构长得相似，就用 DVB 私有描述符、字符集或卫星参数解释。
2. `remote_control_key_id` 是 TS 信息描述符中的遥控键标识；与 TS 名、transmission_type 信息共同展示，不当作 SID、虚拟频道号或全局 LCN。适用性依地区 profile 明示。
3. partial-reception descriptor 的 service 引用可以作为“一段接收相关声明”，不能由此推导完整 RF layer/segment 分配或实际接收结果。没有描述符时不从节目名猜 One-seg。
4. `transmission_type_info` 的类型值依运营规则解释；没有规则时保留 raw/unknown，不无条件标成 A/B/C，也不据 SID 猜 One-seg。分层传输、服务与组件不是可假定的一对一关系。
5. BIT 的播出机构上下文、CDT 的公共数据/台标相关数据、SDTT 的软件/下载触发信息，不能全部塞成 Service 的天然子对象。只有标准规定的显式引用、适用 profile 及原始字段匹配后才生成关联；否则在 auxiliary context 中显示未关联声明。
6. logo 关联不是自动下载/渲染承诺；对象树只显示可验证标识/关系及可检查的原始证据。LDT/NBIT/ITT/AMT 等保持原始表可达，丰富语义投影另列后续范围。
7. 普通 `isdb` 未确定 Japan/Brazil 时显示“地区配置未指定”。日本与巴西的字符集/时间设置是解释配置，不是用户或发射站所在地推断；切换解释配置须走现有重扫流程。

本次实际查阅的官方全文是 [ARIB STD-B10 v4.6-E2](https://www.arib.or.jp/english/html/overview/doc/6-STD-B10v4_6-E2.pdf)（§6.2.42 TS information、§6.2.32 partial reception、§4/§5.2.13 表/播出机构语义）及 [STD-B31 v2.2-E1](https://www.arib.or.jp/english/html/overview/doc/6-STD-B31v2_2-E1.pdf)（§3.3/§3.4 分层传输）。这些是明确标注版本的设计依据，不声称已审最新全文。

巴西 [Fórum SBTVD 官方规范索引](https://forumsbtvd.org.br/legislacao-e-normas-tecnicas/normas-tecnicas-da-tv-digital/) 列有 NBR 15603 地区规范；本次英文全文链接跳回集合首页，未取得最新版全文，不能宣称 Brazil 与 Japan 表/描述符完全一致或最新地区规范已验证。实施前逐条核验适用性；既有测试边界见 [PROTOCOL_COVERAGE.md](PROTOCOL_COVERAGE.md)。

## 7. 标准选择、混合输入与未知

- 顶部 Standards 仍决定下一次分析的解码上下文；Topology 内的“视图标准”只过滤已存在的派生结果，**不能悄悄改变解码器或重扫**。
- 单一有效家族时直接显示名称，不多放一个必须点击的控件；多家族确有证据时提供 family selector，列出每族状态/对象数量。
- Auto 不足以定标准时显示“上下文不确定”，把未解析声明放在 Unresolved signalling。0xC7/0xC8 等表 ID 跨 ATSC/ISDB 冲突，不能凭 table_id 建树。
- 没有任何语义对象时仍保留 Tables 入口，并写明“已保留 N 份原始 section；此上下文暂无可建立的语义关系”，不把空树说成无信号、无频道或解码失败。
- 只收到声明的节点显示 `Announced only`；本捕获匹配的节点显示 `Observed here`；缺表显示 `Incomplete`；矛盾显示 `Conflict`；未知解释显示 `Unresolved`。这些是观察状态，不使用认证/正常播出/可接收的绿色通行证。
- 不把状态压成一个百分比分数。对象证据质量、关系解析状态、字段冲突和解释 profile 分开存储，UI 显示最重要状态并可展开原因。

## 8. 三栏具体布局

### 中央 Topology 页

页签建议顺序：Services / Topology / Tables / EPG / Issues / Changes。其余相对次序不变。

1. 工具栏：标准名称或视图选择器、现有风格的对象搜索、结果数；搜索框说明可搜名称、十进制/十六进制 ID、类型和状态。
2. 单行截面条：`Observed through packet #59,008 · DVB`，若查看 A/B 则明确 `Comparison A`。不从到达密度推导墙钟时间。
3. 可滚动树：主列 `Object / identity`；次列 `State`；末列 `Sources`（精确来源条目数，不是 section 重复次数或子对象数）。宽度不足时状态与来源数移到节点第二行。
4. 节点第一行短名称，第二行只放关键 identity，例如 `ONID 0x2001 · TSID 0x1001`。至少 12 px 的主要字段，28 px 以上单行行高，双行按内容增长；不得靠缩到 9 px 容纳信息。
5. 树底部显示对象数/未解析数/加载状态；分页作用于节点子级集合，不能把上下文父节点切没。大列表按分支惰性加载，不把 2,500 行静默截断当作全量。

### 右侧对象摘要

标题 `OBJECT INSPECTOR`，名称、类型、状态；其下依次为：

1. 身份和值：明确原始 ID、语言/名称、当前 profile。
2. 重要关联：PAT→PMT、频道→program、service→transport 等，带状态和来源入口。
3. Sources：按所支撑的结论分组，例如“名称 / SDT”“PMT 映射 / PAT”“组件 / PMT”“网络成员 / NIT”；每条可打开，不能只提供 evidence[0]。
4. 冲突/未知说明；未知不是空白，也不默认填零。
5. 辅助属性默认折叠，例如卫星候选、台标引用、协议解释。没有任何读到的证据不显示伪按钮。

右侧不再加入一组与六种原始视图同级的混乱页签。使用清晰的模式头 `Object / Source evidence`。点击来源后顶部保留“← 返回对象”及被检查的 assertion；现有六视图、Section/Merged 控件完整复用。

### 尺寸与窄窗

沿用已保存 splitter，不覆盖用户布局。1440 px 的建议初始分配：左 180、中约 650、右约 600（含分隔线和边框以实际可用宽度约束）；1180/1000 px 保留双行节点并收紧次要列，不改变现有最小窗口策略。新页签在窄宽度使用可横向滚动的 tab strip，选中项自动可见，不压到不可读。

面包屑只显示当前对象的主要祖先；中间项可折叠，完整路径可复制。右侧来源路径独立，防止将“对象关系路径”误读为“原始表字段路径”。超长 stream 文本作为 plain text，tooltip 也不解释 HTML；仅允许既有已验证参考链接打开外部 URL。

## 9. Focus、selection、activation

三个概念分开：`focused_node_id`（键盘所在行）、`selected_node_id`（右侧展示的对象）、`active_evidence_ref`（打开的原始证据）。一组变量不得兼任。

| 操作 | 结果 |
|---|---|
| Up/Down、Home/End、type-ahead | 仅移动焦点；不换对象、不请求 inspect |
| Left/Right | 收起/展开；已展开 Right 到首子节点，已收起 Left 到父节点；不跟随证据 |
| 点击节点正文，或 Enter/Space | 选择对象，右侧显示摘要；不自动跳入首份证据 |
| 点击 disclosure | 仅折叠/展开；不把展开当成导航 |
| 点击具体 Sources 链接，或焦点在该按钮时 Enter/Space | 激活该来源，在右侧打开精确证据；对象选择保留 |
| 点击关系列表的对象链接 | 选择目标语义对象并 reveal；可返回原对象 |
| 左侧 PID/表点击或 Enter/Space | 与现在相同：打开 Tables；拓扑选择、展开、搜索留存 |
| “在 Tables 中显示” | 显式进入 Tables，定位对应 PID/type、逻辑组、section 和页；保留返回点 |
| 双击 | 不增加隐藏语义；与单击选择一致，避免意外退出拓扑 |

用现有选中底色表达 selection，2 px focus ring 表达 focus，来源按钮的按下态表达 active evidence；不能只用颜色区分。未选择对象时右侧说明可选择对象，不默认跳到第一份未知表。

Web 用 `tree` / `treeitem` / `group`、`aria-level` / `aria-expanded` / `aria-selected` 和 roving tabindex；Qt 给同等 Accessible role/name/state。树中 Sources 数字是统计，不嵌套一排 tabbable 控件；可操作来源位于右侧，Tab 可以正常离开树。正文菜单若有复制 ID，必须键盘可达。Loading、失败、来源被过滤、只定位到容器等用礼貌状态播报。

## 10. 从语义对象精确跳到 SI 字段

### 用户流程

例：选择 DVB Service → 右侧点击“名称 · SDT 0x42 · PID 0x0011 · §0 · service_name”。

1. 保持中央 Service 的选择/展开/滚动和主工作区截面。
2. 右侧切到 Source evidence；显示 section ID、PID、table ID、版本、section number、current/next、目标字段和 **evidence cutoff**。
3. 默认 **Section** scope，展开到目标字段、滚动居中、可见 highlight；精确 locator 不被现有 selectedService 过滤藏掉。需要合并上下文时用户可切 Merged，不能在 merged generation 中任意找同名属性冒充原字段。
4. 如有可靠 bit/byte 范围，在 Hex 标出对应区间；没有范围则只突出精确结构字段并写“字节范围未提供”。不能对所有 SDK XML 属性编造字节位置。
5. 若只知道 descriptor/container，打开它并标“已定位到描述符；未提供精确字段位置”；若只到 section，明确“已定位到 section”。失败时保留请求的 locator 和重试按钮，不能悄悄打开第一行算成功。
6. “← 返回对象”恢复完整摘要；“在 Tables 中显示”才改变中央页面。原始来源不再需要通过手动搜索表名才能找回。

### 来源地址契约（拟议，非现有 API）

每一条 assertion 和 relation 均可拥有多个 `EvidenceRef`，由 C++ 生成；UI 不根据名称、数组顺序或格式化 XML 字符串反推。

```json
{
  "analysis_revision": 7,
  "at_packet": 59008,
  "section_id": "opaque exact ID returned by the core",
  "table_identity": {"pid": 17, "table_id": 66, "extension": 4097,
    "version": 2, "section_number": 0, "current": true},
  "assertion_key": "service.name",
  "locator": {
    "field_id": "opaque source-field anchor",
    "container_id": "opaque descriptor/loop-entry anchor",
    "precision": "field",
    "byte_range": null,
    "display_path": "SDT / service 0x0067 / service_descriptor / service_name"
  },
  "role": "declares"
}
```

- `section_id` 是权威证据身份；PID/table/version/section 用于核对和显示，不能替代 exact ID。version 可为 null。同 version 不同内容、版本回绕、同包多个 section、重现旧内容都不能只靠 version 定位。
- `at_packet` 是不可变的包含式观察 cutoff；同一 `section_id` 多次重现时仍须传它，不能默认“最后出现”。在不同捕获/analysis revision 中地址无效。
- `field_id` / `container_id` 是引擎发出的有作用域 ID；重复 service/descriptor entry 必须可区分，不能只有 `service_name` 或 tag。建议 locator 在 exact section 内绑定原始 loop entry/descriptor offset 和字段 token；版本变化不靠 child index 猜。
- `byte_range` 若存在，明确 `offset_scope: section_bytes`（自 table_id 所在的 section 首字节开始，包含表头）、起点/长度及可选 bit 范围，并通过 raw 长度校验。不得把 TS 文件 offset 当 section offset。
- `precision` 为 `field` / `container` / `section`；另外给 `resolution_status`，区分可解析、上下文冲突、未支持、已失效。最高精度可随字段类型不同，但显示必须真实。
- 原始字段 anchor 应随 `inspect` 的规范化字段节点返回；共享 presentation layer 把 anchor 映射到实际节点。Qt/Web 当前 `section/native/table/childN` 等渲染路径只用于各自焦点恢复，不作为协议证据地址。
- 一条衍生结论需要多个前提时全部保留，例如 PMT link 同时引用 PAT mapping 和 PMT program_number；标注各自 `role`。重复观察可合并计数，不能丢失相互矛盾的声明。

## 11. 时间、历史、A/B 与返回

### 一条不可破坏的规则

**查看来源不改变工作区时刻；只有明确的 Use snapshot / 时间线操作改变它。**

Topology 查询和所有来源必须共用 `{analysis_revision, at_packet, standard_profile}`。截止包之后的 section、later repetition、未收齐的另一代不能补入当前树；`next` 和 invalid 表保留为证据，不进入正常 current 关系。

| 路径 | 主工作区 cutoff | 证据 cutoff | 返回语义 |
|---|---|---|---|
| 当前 Topology → 来源 | 不变 | 等于生成拓扑的 cutoff | 返回同对象和同树状态 |
| A/B 某侧 → 对象/来源 | 不变 | 该侧 cutoff | 返回该侧记录；再退出恢复原工作区 |
| 来源 → Table sections 另一 section | 不变 | 保留当前 evidence cutoff | 不自动升级到最新代 |
| 在 Tables 中显示 | 不变 | 保留 evidence cutoff；显示若与主列表不同的 scope 提示 | Back 恢复 Topology/来源 |
| 现有表历史 activation | 明确改变，仍用 first completion `at_packet` | 同一准确 cutoff | 与现有行为一致，不偷偷改成 last_packet |
| Use snapshot / Latest | 明确改变 | 重新按新 cutoff 解析 | 清除过期 evidence/preview，重新核对节点存在性 |

若 Tables 的主列表属于另一 cutoff，“在 Tables 中显示”应使用只读 scoped reveal layer，并在列表顶部显示“来源截面 #…；主工作区 #…”。不要把历史 section 注入最新数据假装当前表。如本阶段不实现 scoped reveal，则该动作对不同截面禁用并解释原因，仍可在右侧准确检查；不能用隐式 snapshot 代替。

返回点保存：tab、view-family、对象/来源身份、主 cutoff、evidence cutoff、搜索、展开集合、列表页/滚动、右侧 view/scope、焦点目标、分析 revision。source/ref/profile 变化时验证返回点；对象已不存在则保留“上次选择此截面未观察到”提示并定位最近仍有效祖先，不换成同名对象。重新分析或失败/取消清理后清空跨 revision 的返回栈。

只记录有意义的对象/证据激活，不把箭头 focus、折叠动作都压入 Back。提供可见 Back 按钮；Alt+Left 仅在应用导航上下文使用，Web 防止触发浏览器离开。Esc 清当前搜索或关闭已有局部弹层，不作为无提示跳出多层上下文的捷径。

## 12. 数据与 UI 状态最小契约

以下是工程接口建议，不代表 API 已存在：

```text
TopologySnapshot
  schema_version, analysis_revision, at_packet, interpretation_profile
  status / diagnostics / counts
  nodes[]: node_id, object_type, identity, label, attributes,
           observation_status, evidence[], unresolved_reasons[]
  edges[]: edge_id, from, to, relation, resolution_status, evidence[]
  projections[]: family, roots[], child_order / reference_nodes
  coverage: supported_adapters, missing_tables, unsupported_relations
```

引擎负责：标准判别、身份、关系、同代/同截面选择、冲突保留、原始 locator。优先提取共享只读 snapshot builder，给 GUI/JSONL/MCP 一致结果；不能在 Qt 写一套、Web 写另一套，也不能遍历展示 XML 来推断节目对象。

API 可采用独立的只读 `query_topology(at_packet, family, parent_id, offset, limit)`，或 `query` 的显式 opt-in projection；实施前二选一并同步 `api/tools.json`。推荐独立 read-only 操作，避免把大图无条件加到每次现有 query。它必须复用同一个 snapshot selection，不能重做时间规则。首次范围不新增外网查询、调谐、媒体解码或自动加载插件。

客户端增加独立 `topologyState`、`objectSelection`、`inspectionContext`、`navigationState`；inspection context 的 kind 为 `workspace` / `comparison` / `topology`，不把 topology 标成 Comparison。保留现有 request epoch，增加 revision/cutoff/selected-object 校验：较晚返回的旧请求不能抢回焦点或展示旧证据。

加载失败保留之前摘要但标为 stale/错误，不继续声称最新；重试只重试只读请求。扫描中或取消未确认时禁用新树查询；分析失败/取消遵循既有清空约定。增大图限制、分页和缓存必须明确上限，缓存键包含 revision/profile/cutoff，不能跨次分析复用。

## 13. 最小有用范围与后续范围

### 首次实施范围（独立版本；不是当前发行阻断项）

1. C++ 只读对象/边、明确时间与 provenance；三标准各自最小骨架：DVB NIT/SDT/PAT/PMT，ATSC TVCT/CVCT→PAT/PMT，ISDB profile-aware NIT/SDT/PAT/PMT。
2. 三标准的未关联/仅宣告/缺表/冲突状态；ATSC analog/inactive、source_id 重复；ISDB profile 与 remote-control/partial-reception 声明可正确展示。
3. 双端中央 Topology、右侧摘要/所有来源、Back 与 exact section/field jump。只对有稳定 locator 的首批字段称“精确字段跳转”；其余如实降到 container/section，不伪称完整字段覆盖。
4. 和现有历史/比较共用 cutoff、来源选择和恢复；来源不会自动改 snapshot。第一期不新增“拓扑 A/B diff”算法，只允许现有 A/B 侧按同 cutoff 溯源。
5. 键盘、搜索、窄窗、双主题、无障碍及真实引擎回归；只读，保留现有编辑/导出能力且不新增树内编辑。

### 后续独立提案

- BIT/broadcaster alternate projection、完整 logo/download/data application 语义链、详细 ATSC EPG/ETT 层级。
- 跨文件/跨捕获合并、运营商专用频道列表、历史拓扑 diff/图形连线、持久化大索引。
- 任意 SDK 字段的 bit-range mapping、通用字段编辑、实际 RF/TP 观测关联。
- 卫星目录扩容/捕获日期归属验证、调谐器集成、真实媒体包验证。

允许内部按共同数据层 → 三个 adapter → 双端 UI 分阶段开发，但用户可见发布不得将一个标准的树重命名后宣称三个标准已完成。各 adapter 单独报告“已实现 / 已测试 / 未支持”，不以 SDK 注册数量替代产品覆盖。

## 14. 验收矩阵（实施时必须执行）

| 类别 | 输入/操作 | 必须观察到 |
|---|---|---|
| DVB 身份 | 同 TSID 不同 ONID、同 SID 多 TS、多个 NIT membership | 不串服务，不借 PMT，不静默丢关系 |
| DVB 声明 | NIT-other TS、无 NIT 的本地 PAT/SDT、无 SDT 的 program | 宣告/本捕获状态准确；有未关联分支；不补 ONID=0 |
| Delivery | 多 TS delivery loops、共轨多候选、目录缺项、ISDB 同 tag | TS 不等于 TP；候选不是父级确认；原始各 loop 不混 |
| ATSC | TVCT/CVCT、one-part/two-part、header TSID ≠ channel_TSID、重复 source_id、频道重新映射 | 各频道独立；准确或未解析的 program 关联；不把 major/minor 当 RF |
| ATSC 特殊 | inactive/analog/hidden、VCT 与 PMT 声明冲突 | 不造 PMT；hidden 不判 invalid；冲突双方来源可见 |
| ISDB | Japan/Brazil/unspecified，同 tag 不同 profile，remote key/partial reception | profile 显式；不套 DVB 字段；遥控键不变 SID/LCN；不假装 RF 测量 |
| 不完整 | 少 section、bad CRC、current/next、未知私有 namespace | 仅有效完整适用代参与正常关系；原始证据仍可达 |
| 代和时间 | 同 version 内容变化、回绕、重现旧内容、同包多 section、完成包边界 | 严格截面，不用未来 sibling，history jump 用完成包 |
| 多来源 | SDT 名称、PAT mapping、PMT component、NIT membership 逐一打开 | 每份 exact section ID/field/cutoff 匹配；不只打开第一份 |
| 字段定位 | 重复同 tag、重复名称、分 section 服务、无 byte range 的 SDK 属性 | 目标唯一；可靠字段高亮；不支持部分准确降级 |
| 返回 | Topology→SDT→PMT→Tables→Back；从 A/B 进入再退出 | 对象、树、搜索、焦点、主 cutoff 均正确恢复 |
| 异步 | 快速选择两个对象、切 cutoff、反复 Back、rescan/cancel、断开后端 | 旧响应不夺回界面；无过期编辑令牌；无无限 loading |
| 输入与无障碍 | 键盘全程、28 px 行、1000/1180/1440、长中英/RTL 名称、双主题 | focus/selection 可辨、无必需内容截断、状态有文字、无 markup 执行 |
| 性能 | 大量服务/关系、深树、分页内外定位、搜索后恢复 | 有界渲染、祖先保留、计数完整、无静默丢节点 |
| 非回归 | 现有 Services/Tables 六视图、CRC/历史、编辑、TS/BIN 保存/取消/回读 | 新页不移除既有功能；源文件哈希不变 |

新增 fixtures 必须经真实 core 生成图与 inspect；UI 控件使用真实数据响应。单元测试可用 stub 校验状态机，但不得将它作为协议/真实窗口完成的证据。对最终组合代码跑 engine、Qt、browser 门槛，再按已有路线操作真实 Windows Qt/WebView2；仅构建、截图、offscreen 不足以宣称原生交互完成。

建议诊断快照新增：`topology.profile/cutoff/selected_node/focused_node/expanded_ids`、当前可见 nodes/edges、`inspection_context`、`evidence_ref`、locator 解析精度、返回目标和 pending 状态。诊断用 ID 要和同次截图关联，不能以像素猜 source 身份。

## 15. 本次交付与验证边界

交付文件：`docs/SIGNAL_TOPOLOGY_DESIGN.md`；离线线框 `artifacts/topology-design/index.html`，以及同目录 `README.txt`。线框可切换 DVB、ATSC 1.0、ISDB 三个示意场景，并演示右侧来源/返回；其它应用按钮仅作布局占位。

本次完成文档和 HTML 静态检查；未取得浏览器渲染截图或真实交互验收。受限 shell 的 sandboxed Chromium 启动失败；云桌面 wrapper 未产生可核验输出；浏览器 file URL 被策略拒绝。没有禁用沙箱、修改安全设置或使用用户电脑。

本次只新增本文和可选的忽略目录线框材料，没有修改引擎、Qt/Tauri 实现、构建脚本或发布门槛，没有提交或发布。线框的频道/网络/数据均为设计示例，不是已解析样流，不是正在运行的新功能。已有真实工作台截图仅用于布局对照。

实施接手先核对当时最新 HEAD/工作区和用户批准范围，再按第 13 节取范围。这个设计不能自动授权改变当前正在收尾的安装版或扩充其验收清单。
