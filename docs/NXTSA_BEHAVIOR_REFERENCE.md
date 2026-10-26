# 原版 NxTSA / ShowPsiSi Qt 行为参考

记录日期：2026-10-25（香港时间）；保存截图 UTC 05:17:30–05:41:22，对应本地13:17–13:41。本记录冻结初始只读GUI取证批次；后续P1实现与门槛见对应规格。它不是完整功能/协议/像素验收。需求矩阵与阶段见 [NXTSA_UI_UX_PARITY](NXTSA_UI_UX_PARITY.md)。

## 输入、程序和现场身份

本次在原版与 Qt 使用同一个独立输入副本，均由真实 Windows 鼠标/键盘操作（computer-use / @oai/sky），没有用重建 GUI、mock 或 offscreen 图替代原版行为。

| 项目 | 本轮核验 |
| --- | --- |
| 正确工作树 | C:/Users/hentai/Documents/Codex/2026-10-21/task-4/ShowPsiSi；ui/unified-inspector；开始 clean |
| 本地 HEAD | ba1b58484e5b2403680ec00524027c192d428ed2 |
| 已合并 main | de2b1d5631f02c74b418a3c16bb78baae8e6f526；git ls-remote 本轮确认；本地 HEAD 与 main 文件树一致 |
| Qt 产物 | 现有 main CI 40064856916 的 portable；0.3.1 / Qt6.7.3 / TSDuck3.45-4798；本轮未本机构建 |
| Qt executable | 1,651,200 bytes；SHA256 685ebf47b97aca083898a30ccb964fad2ee21741cb00370e3166f650e00b8cd0 |
| C++ core | 1,501,184 bytes；SHA256 872186bcabf4d23f4c2f7600b1f446f66cf94b5f6c8fc8922c70e06a20336b2f |
| 原版 | C:/Program Files (x86)/NxTSA/NXTSA.exe；1,0,0,1；733,184 bytes |
| 原版 executable | SHA256 7571823ec3f32df4f7eb1fabb3ca51745e0dddf6606b53bbb22266e69d528d8a；DLL/OCX 清单见本地 original-binaries.json |
| 本次样本 | hotbird6000.ts；41,999,952 bytes；223,404 × 188-byte packets |
| 样本 SHA256 | 96e116344fa30b8bfc922857632ffa94427cbd536b086e8afdab630ab19de1e1；使用前/后同值 |
| 样本副本 | 工作树 artifacts/nxtsa-parity-20261025/inputs/hotbird6000.ts；来源 NXTSA/samples/hotbird6000.ts |
| Qt 路径 | artifacts/unified-inspector/main-de2b1d5-preview/package/ShowPsiSi-windows-x64/bin/showpsisi-qt.exe |
| 设置 | Qt使用专属 qt-settings.ini、development 模式、自动扫描关闭；没有安装或修改 SDK 安全标签 |
| 窗口/DPI | 原版恢复正常窗口截图2852×1460；Qt1442×930；系统 AppliedDPI=192（配置200%），未独立量测各窗口有效DPI |

系统原生 picker 显示了此前测试目录：独立 Qt QSettings 不意味着隔离 Windows picker MRU。原版仅做普通打开/查看/窗口操作，没有刻意修改配置；不声称其 MRU/窗口状态完全未变。实验前没有发现原版/Qt GUI 实例；本轮启动的原版 PID68776 已正常关闭并读回消失。Qt PID45044 / core82308 保留供用户查看。后续272秒CPU读回：core增加0 CPU秒，Qt增加24.640625 CPU秒；只证明该区间core无新增CPU工作，不据窗口静止声称整个GUI后台安静。

完整原始 Hotbird 捕获 352,319,708 bytes / SHA256 29e1a4fd0d81214d3fb85a64283007c48b6a13f1432c9168a6a4cb672cb4e0f0 仅来自交接，本轮**没有**用于 GUI。短捕获是原始 TS 的一段，不能借它的空文件表推断完整流没有 OC 文件。

## 证据索引与重现方法

本地证据在 ignored [artifacts/nxtsa-parity-20261025](../artifacts/nxtsa-parity-20261025)。包含：
gui-events.json（每场景时间/窗口/说明/截图尺寸）、screenshots/、同名 UIA .txt、manifest.json、file-hashes.json、original-binaries.json、launch.json、引擎 JSON、qt 日志与 validation.json。截图先保存到本聊天可写的 visualization 目录，再复制到实际工作树并逐文件校验 SHA256。运行中的 Qt 日志由进程占用，日志与可变设置不纳入不可变哈希清单，manifest 明确列出排除项。文件不是 fresh clone 必然具有的测试 fixture；下列步骤与样本身份用于重现。

共45个已保存场景：原版32、Qt13。数量表示记录数，不表示45项测试通过；例如 nx31 是实际错误，多个场景只建立局部行为。UIA 有时滞后于像素或缺失（nx18/nx27 的树为空）；不以 UIA 旧值覆盖已观测画面。切换程序前先激活窗口，未保存一次被 Qt 遮挡的原版状态为有效证据。

### 原版：文件、Summary、媒体、服务和来源

先启动原版，恢复正常窗口，Ctrl+O 打开相同副本；Analyzer → Start 才开始扫描。所有下述节目/PID均来自此输入。

| 场景 / 截图 | 实际动作与结果 | 验收范围 |
| --- | --- | --- |
| [nx01](../artifacts/nxtsa-parity-20261025/screenshots/nx01-empty-normal-0.png) / [nx02](../artifacts/nxtsa-parity-20261025/screenshots/nx02-open-before-analysis-0.png) | 正常窗口；Ctrl+O 后出现 Programs / PSI Packets / All Packets / DSMCC，未自动分析 | measured：打开与初始状态 |
| [nx03](../artifacts/nxtsa-parity-20261025/screenshots/nx03-analyzer-menu-0.png) | Analyzer 菜单含配置、Packet Explorer、Bug Report、Start；扫描前Stop/Pause禁用 | measured：此时命令状态 |
| [nx04](../artifacts/nxtsa-parity-20261025/screenshots/nx04-summary-complete-0.png) | Start完成：41,999,952 bytes；223,404 packets；45,940,024 bps；00:00:07；0 errors；188 bytes；PID/#of packets/PacketRate/Comment | measured：显示值；码率算法非独立验证 |
| [nx05](../artifacts/nxtsa-parity-20261025/screenshots/nx05-error-page-0.png) | 底部Error切页可点击；PID/Error Msg表为空，顶部计数保留 | measured：正常样本空错误页；非坏流错误覆盖 |
| [nx06](../artifacts/nxtsa-parity-20261025/screenshots/nx06-video-menu-0.png) / [nx07](../artifacts/nxtsa-parity-20261025/screenshots/nx07-video-scrambled-0.png) | All Packets，PID0x03AC右键 Packet → Play Video / Analyzing Video / View Packets；分析显示“This ES scrambled!!” | measured：加扰拒绝路径；未解密 |
| [nx08](../artifacts/nxtsa-parity-20261025/screenshots/nx08-video-thumbnails-0.png) | PID0x0712 → Analyzing Video，Video Thumb View Program8；真实I/B/P图像、横向滚动；Sequence Header 720×576 | measured：真实图像功能；部分tiles有瑕疵，非全帧正确性 |
| [nx09](../artifacts/nxtsa-parity-20261025/screenshots/nx09-video-selection-0.png) | 点击第3幅P-Picture，下方切换Picture Header / Temporal Reference3 / P-Picture | measured：帧选择联动 |
| [nx10](../artifacts/nxtsa-parity-20261025/screenshots/nx10-audio-menu-0.png) / [nx11](../artifacts/nxtsa-parity-20261025/screenshots/nx11-audio-waveform-0.png) | PID0x0713 → Play Audio，Audio Wave View Program8；红/绿双通道波形、0..9秒轴、Play/Stop、Layer2/48000Hz | measured：真实绘制声波界面；PCM幅值未独立校准 |
| [nx12](../artifacts/nxtsa-parity-20261025/screenshots/nx12-audio-stop-0.png) | 操作Play再Stop，没有modal；双击音频PID激活既有窗口 | partial：没有录音、独立听感或游标时序量测 |
| [nx13](../artifacts/nxtsa-parity-20261025/screenshots/nx13-pes-packets-0.png) | 同音频PID → View Packets，PES Header Packet1/50；下方header hex与PES Packet1 of643面板 | measured：存在两层计数/双hex；643计数含义待定 |
| [nx14](../artifacts/nxtsa-parity-20261025/screenshots/nx14-pes-fields-0.png) / [nx15](../artifacts/nxtsa-parity-20261025/screenshots/nx15-pes-pts-0.png) | 展开PES头和PTS，stream_id0xC0、length2312、bits/flags、33-bit碎片/marker与90kHz时刻 | measured：可展开数据；DTS/时间算法未独立校验 |
| [nx16](../artifacts/nxtsa-parity-20261025/screenshots/nx16-program-tree-0.png) | 拉宽树；Program8含PCR/video0712、audio0713、Teletext0653、AIT1EC6/1EC7、DSMCC1E9E/1E9F | measured：节目/ES层级；拉宽后子窗口可被裁切 |
| [nx17](../artifacts/nxtsa-parity-20261025/screenshots/nx17-service-pmt-menu-0.png) | Program8右键 View Tables→PMT→PID0108 Ver13；双击节目仅展开/折叠 | measured：PMT入口，不是双击打开 |
| [nx18](../artifacts/nxtsa-parity-20261025/screenshots/nx18-pmt-section-0.png) / [nx19](../artifacts/nxtsa-parity-20261025/screenshots/nx19-pmt-field-0.png) | PMT：Program0008/PID0108/v13/PCR0712，section174B；Field/Bits/Value/Comment与TS包/section双hex；选table_id_extension变黄16bits/0x8 | measured：同一PMT身份；bit/颜色锚点仍partial |
| [nx20](../artifacts/nxtsa-parity-20261025/screenshots/nx20-mdi-close-restore-0.png) | Ctrl+F4关闭PMT，前一PES子窗口恢复，PTS展开/滚动和节目选择保留 | measured：一次MDI关闭恢复 |
| [nx21](../artifacts/nxtsa-parity-20261025/screenshots/nx21-teletext-0.png) / [nx22](../artifacts/nxtsa-parity-20261025/screenshots/nx22-teletext-next-observation-0.png) | Program8→PID0653→View TeleText，真实彩色page100；点右箭头仍page100而内容/时间16:27:30→16:27:35 | measured：页面和下一捕获；未证明“下一页码”。标题Program1是共享PID标签差异 |

### 原版：AIT、OC、Bitrate、原包与取消

| 场景 / 截图 | 实际动作与结果 | 验收范围 |
| --- | --- | --- |
| [nx23](../artifacts/nxtsa-parity-20261025/screenshots/nx23-ait-section-0.png) | AIT树v0/PID1EC6显式View version；77B，organisation000B/application1AB6 | measured：section视图；未走AIT→carousel自动关联 |
| [nx24](../artifacts/nxtsa-parity-20261025/screenshots/nx24-oc-files-0.png) | carousel1AB7分支右键View Carousel；OC Files / OC Hierachy / BIOP List；Name/Size/Type/Module/Cycle和SRG详情 | partial：文件表为空；不算文件/class恢复通过 |
| [nx25](../artifacts/nxtsa-parity-20261025/screenshots/nx25-oc-biop-list-0.png) | BIOP List显示module10一个SRG、objectKey0x53475700 | measured：SRG列表；非多对象/内容验收 |
| [nx26](../artifacts/nxtsa-parity-20261025/screenshots/nx26-oc-hierarchy-0.png) | OC Hierachy画DSI→DII→Module10；DSI cycle10.630343，DII14modules/cycle3.555150 | measured：层级显示；cycle算法未独立校准 |
| [nx27](../artifacts/nxtsa-parity-20261025/screenshots/nx27-view-menu-0.png) | View含Toolbar/StatusBar/TS Tree开关、Summary和Bitrate | measured：菜单；重建版平铺14视图不是原版此菜单 |
| [nx28](../artifacts/nxtsa-parity-20261025/screenshots/nx28-bitrate-0.png) | View Bitrate，Program/PID/Bitrate绿条/Current；PID0712为2597007.00 | partial：未独立确认单位、分母和时钟 |
| [nx29](../artifacts/nxtsa-parity-20261025/screenshots/nx29-packet-explorer-0.png) / [nx30](../artifacts/nxtsa-parity-20261025/screenshots/nx30-packet-next-0.png) | Analyzer Packet Explorer，header/adaptation/pointer/PES/payload色例；点next使packet0→1、PID0136→065E，hex/fields更新 | measured：原包与下一包；search/末包未全测 |
| [nx31](../artifacts/nxtsa-parity-20261025/screenshots/nx31-stop-after-eof-0.png) | 完成/Ready后Start仍禁用、Stop/Pause可用；点击Stop弹“Can't Stop analyzing”；确认后Start启用、Stop/Pause禁用 | observed_error：原版EOF状态问题；不是扫描中取消通过 |
| [nx32](../artifacts/nxtsa-parity-20261025/screenshots/nx32-picker-cancel-0.png) | Ctrl+O后Escape，OC界面和既有分析保留 | measured：文件框取消；随后正常Alt+F4关闭本轮原版 |

没有在上述菜单中确认独立 Timing 路线，标记 NOT_RUN，不据此宣称原版不存在 Timing。class/config、多个OC文件和内容预览本轮 NOT_RUN；需要完整捕获及下一批原版行为证据。

### Qt：同输入、来源与返回

启动精准 portable，独立设置/自动扫描关闭，初始Auto/full；之后显式DVB重扫用于AIT与DSM-CC。GUI第二次扫描revision2；独立CLI进程revision1，不能混用来源身份。

| 场景 / 截图 | 实际动作与结果 | 验收范围 |
| --- | --- | --- |
| [qt01](../artifacts/nxtsa-parity-20261025/screenshots/qt01-empty-0.png) | 输入路径预填，未点击Analyze前不扫描 | measured：隔离启动 |
| [qt02](../artifacts/nxtsa-parity-20261025/screenshots/qt02-same-input-complete-0.png) | Analyze；223404/223404 packets，112 distinct payloads，PAT→service0008→PMT0108→TgCom24 | measured：完整扫描与服务映射 |
| [qt03](../artifacts/nxtsa-parity-20261025/screenshots/qt03-pat-service-hex-0.png) | 选PAT service0008，program_map_pid0108；Show Hex显示section原字节 | measured：字段/hex；没有原版双hex与Bits列 |
| [qt04](../artifacts/nxtsa-parity-20261025/screenshots/qt04-pmt-exact-0.png) | 搜索0x0108并选PMT：Program8/v13/PCR0712/7streams/174B/CRC valid；packet2584–222529 | measured：原版同PMT身份与字节数 |
| [qt05](../artifacts/nxtsa-parity-20261025/screenshots/qt05-back-after-filter-0.png) | Alt+Left回PAT详情/service8，但query仍0x0108，只显示PMT，PAT选中项不可见 | observed_gap：上下文恢复不完整，本轮不修代码 |
| [qt06](../artifacts/nxtsa-parity-20261025/screenshots/qt06-keyboard-enter-0.png) | F6切焦点，导航PMT有外框，Enter打开PMT | measured：此键盘路线；非全键盘/屏读验收 |
| [qt07](../artifacts/nxtsa-parity-20261025/screenshots/qt07-advanced-services-0.png) | 高级工作区保留Services/Topology/Tables/EPG/Issues/Changes、历史、六个详情tab与编辑导出入口；21services、1562section observations | measured：既有入口；本轮未执行编辑/导出 |
| [qt08](../artifacts/nxtsa-parity-20261025/screenshots/qt08-ait-metadata-0.png) | 改DVB→Analyze→Tables搜索1EC6→AITv0 Metadata，77B、21cards分页、read-only/not-executed | measured：同源AIT卡片 |
| [qt09](../artifacts/nxtsa-parity-20261025/screenshots/qt09-ait-source-0.png) / [qt10](../artifacts/nxtsa-parity-20261025/screenshots/qt10-metadata-return-0.png) | Open source application type/test flag，revision2/cutoff176595/section bytes3–4；Metadata返回恢复卡片/筛选 | measured：精确source jump和返回 |
| [qt11](../artifacts/nxtsa-parity-20261025/screenshots/qt11-dsmcc-dii-0.png) | Tables搜索1E9E，选U-N extension0002（DII，162B）Metadata，已有模块/来源卡片 | measured：复用已有重组；extension0000的DSI另为unsupported |
| [qt12](../artifacts/nxtsa-parity-20261025/screenshots/qt12-incomplete-module-null-0.png) | module000C为unresolved/incomplete、assembled sha256:null，PID1E9E/download1AB6/epoch20 packet2999/revision2可见 | measured：完整性与身份合同；未实现OC浏览器 |
| [qt13](../artifacts/nxtsa-parity-20261025/screenshots/qt13-picker-cancel-0.png) | Ctrl+O原生picker，Escape后DII、module000C和完整结果保留 | measured：取消打开；非扫描中取消 |

Qt05 的静态对应：UnifiedInspector.qml selectRecord 在新选择时保存 query，而 query 已先被用户改为0x0108；back恢复该 query 与旧 PAT detail 的组合。需要后续对“筛选前的上下文”定合同并加交互回归。本轮没有把其他历史问题自动标为当前复现。

## 独立引擎读回

使用同产物 core、同文件、显式DVB，正常结束客户端，保存 engine-state-dvb.json / engine-summary.json / inspect-02/74/3b/3c.json。不是另一个GUI验收：

- 223404 packets、188 bytes、CRC0、112 retained payload records、21services、30events；analysis_status=complete。
- timing.basis=packet index，pcr_derived=false，seconds_per_packet=null；当前时轴不是测量PCR时钟。demux零错误只覆盖其监测范围，不证明全TS/AV无错。
- PMT inspect02为PID264/Program8。CLI inspect74选的是PID7879（1EC7）AIT，不是GUI1EC6，不能将两份身份混为一条。
- inspect3b选首个U-N/DSI，status=unsupported_message；这不能推导DII不支持，GUI明确打开第二组DII。
- full cutoff223403，PID7838/download6838/version0/epoch20 packet2999：module10和11完整，module12/13不完整且hash=null。完整模块分别为110B和962B。
- module10 hash 48fc1e9712cee63369f98f6391e890ac1b05b7d4a79cdf321f8d6db0c5a4dede；module11 hash e01b933ff16435c1f5ab58ff31a5aff295e610739233872f1078793722aca564。
- completeness仅验证CRC-valid sections、宣告大小和块覆盖/长度；未验证模块签名、可选校验、BIOP内容或软件可执行性。decompression=not_requested、execution=not_executed。

## 状态与下一批证据

| 范围 | 本轮状态 | 剩余门槛 |
| --- | --- | --- |
| 原版/Qt同样本打开、完整扫描、PMT与picker取消 | measured | 更多坏/空/第二输入；扫描中状态转换 |
| 原版真实缩略图、选帧和声波界面 | measured / partial | 解码正确性、帧来源、PCM幅值、播放声音/游标独立测量 |
| 原版PES、Teletext、OC、Bitrate | partial | DTS/计数语义、多页字符集、完整文件内容、单位/时钟算法 |
| 原版Timing、config/class | NOT_RUN | 明确入口及完整原始捕获；不从窗口类名推断 |
| 扫描中Pause/Stop/Cancel，坏文件/第二文件 | NOT_RUN | 本次短流结束快；需要可控真实长扫描，不能以EOF Stop或测试gate代替生产路径 |
| 窄窗、100%/150%、全键盘/屏读 | NOT_RUN | 本轮只建立系统200%配置下的有限交互；不宣称逐像素一致 |
| Tauri / WebView2 / macOS | NOT_RUN | 各平台单独实机回归；保留既有功能 |
| 本机构建工具 | environment_blocked（沿用已记录问题） | 既有SDK工具Low/NoWriteUp标签问题未改变；本次用精确CI产物，无新安全配置尝试 |

本批次仅建立文档与ignored取证，没有发布、安装、push、merge或新增产品依赖。当时没有重跑全套产品测试；其文档检查覆盖链接、14个UX标识、截图/哈希和diff格式。后续实际实现和测试独立记录在P1进度中。以 validation.json 为本地文件检查读回，后续工程实现仍按项目交付/CI/协议合同完成。
