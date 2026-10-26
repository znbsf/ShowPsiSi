# NxTSA → ShowPsiSi UI/UX 对应规格

更新：2026-10-25（香港时间）。初始批次建立行为参考、差距审计与 Qt 优先实施规格；随后新增实际复刻授权，P1源码和组件进度见下节。下方14组矩阵保留起始main基线，不表示后续增量尚未实现。实际操作记录见 [原版与 Qt 对拍](NXTSA_BEHAVIOR_REFERENCE.md)。

## 基线与适用范围

- 正确工作树：C:/Users/hentai/Documents/Codex/2026-10-21/task-4/ShowPsiSi。开始时 clean，分支 ui/unified-inspector，HEAD ba1b58484e5b2403680ec00524027c192d428ed2。
- 已合并 main：de2b1d5631f02c74b418a3c16bb78baae8e6f526；本轮 git ls-remote 核对 main 与源分支，HEAD 和 main 的文件树相同。默认 C:/Users/hentai/Documents/ShowPsiSi 是旧 checkout。
- 实测 Qt 是 main CI 40064856916 的现有免安装产物（Qt 6.7.3 / TSDuck 3.45-4798），不是本轮重新本机构建；准确二进制与样本身份见行为记录。
- 输入交接：C:/Users/hentai/Documents/NXTSA/artifacts/ui-ux-handoff-20261025/SHOWPSISI_UI_UX_PARITY_HANDOFF.md，SHA256 695c8adf59f32a68b3d3298fb470cf4882239283a2d5c37f2cc8039e527da96c。
- 原版安装程序是行为参考；NXTSA 重建项目是实现参考。交接中记录的重建提交 4bcb756780b0b4112a68d85db2fba434b8bdfe0e 不能证明其 dirty 文件已验收。迁移时只取明确提交和专项证据，不直接复制其他会话现场文件。
- 用户优先级：先对应原版功能、信息层次和操作结果，再由用户看完整功能决定 UX 优化。Qt 优先；Tauri 本轮没有原生复验。

原版这次确实显示了 I/B/P 解码图像和双通道声波。因此 MPGThumb 与 MP3Wave 不能以“帧索引 / PES 大小时间线”交付为完成。原版菜单也不是重建项目的 14 个平铺视图菜单：本表的 14 组是需求分类，不是原版菜单布局。

## P1 Summary / PID 与返回状态：源码交付，完整应用验收待完成

- 当前分支 codex/nxtsa-summary-pid，从本轮重新 fetch 的 main de2b1d5631f02c74b418a3c16bb78baae8e6f526 开始，保留此前取证与全部本轮改动。最终阶段提交和文件哈希以本地 p1-delivery-checkpoint.json / Git log 为准；测试使用 main 文件树加本阶段补丁，不把旧 main CI 当新源码验收。
- 已实现 C++ scan-owner 全 PID 计数和只读 query_transport；Qt 新增 Summary / PID 入口、六字段、Summary/Error、排序/100行分页、PID→section、错误来源、第二页返回保持。统一/高级工作区继续可达；F6切换PID列表与页签，Alt+Left返回工作区，既有搜索快捷键返回原检查器。
- 已修复 PAT→PMT 筛选后 Back 不恢复旧筛选的问题；新增独立数值 PID filter，避免 PID 0x0100 与另一表 extension 0x0100 的全文匹配碰撞。Back保留原过滤、字段、展开/分页限制和列表位置。
- Error行保留 exact section id / aggregate。普通诊断打开其确切section；PID汇总只表示“查看这个PID的section”；没有来源的聚合不跳PAT。无有效PID的sync错误单列为聚合，不能显示为空错误页。
- 深浅主题显式配对选中背景/文字、页签状态、禁用态和键盘焦点；数值列有最小宽度。组件截图等待polish/render及当前可见delegate列对齐，排除ListView复用池中的旧item。
- Tauri本轮没有新增Summary UI；其原有功能和共享引擎API保留。PES、PCR量测、BIOP内容、Teletext和真实媒体仍属后续切片。

### query_transport 现行合同

API定义见 [tools.json](../api/tools.json)，实现见 [TransportStatistics.h](../core/TransportStatistics.h) 与 [core/main.cpp](../core/main.cpp)。

- 必须匹配 analysis_revision，成功分析完成后查询；offset 0..8192、limit 1..100；sort=pid/packets、descending、errors_only。包数排序同值时按PID升序稳定排序。返回 source、revision、coverage、offset/total/next_offset 和全扫描summary。
- 计数仅覆盖实际读取的窗口，对历史cutoff保持scan-global；分布式预览不把间隙当作已扫描。最多8192个PID槽，无逐包动态分配。重新分析、失败或取消清除旧统计，仍由既有单owner更新。
- 每PID返回packet count/share、payload/adaptation声明计数、TEI、scrambled、malformed header及首末包位置。无同步字节时PID未知，仅进入 aggregate_errors；PID share以所有observed packets为分母，因此存在坏同步包时总和可小于100%。
- header_checks只包括sync、TEI、reserved adaptation_field_control与adaptation长度越界。error_packets对这些错误包去重；不表示continuity、CRC、PES或解码错误总数，加扰不等同错误。Error tab另展示当前快照的retained section/demux diagnostics，保持它们原来的来源范围。
- 码率、packets/s和observed duration只按用户提供的normalized 188-byte TS bitrate推算；未提供则null / Unknown，pcr_derived=false。时长以h:m:s.msec显示并注明supplied rate；分段窗口时是被观察窗口之和，不是跨间隙elapsed time。
- 普通section错误保留source id；aggregate的PID/id可以为null，前端不可造来源。诊断列表分页和transport PID分页不是同一计数，不能合并错误分母。

### 本地验证与准确边界

| 门槛 | 结果 / 证据 |
| --- | --- |
| C++生产引擎与编译期取消助手 | 独立 BUILD_QT_UI=OFF 目录clean build通过；p1-reviewed-clean-build.log |
| 严格引擎回归 | 30 suites / 650 tests reported；649通过、1项既有可选真实样本缺失skip；零failure/error/unexpected skip。包括新增8项统计和6项证据harness测试、既有协议/取消/导出/DSM-CC等 |
| Qt源码组件 | QuickTest 6.7.3：100%与150%各25 PASS（21个实际用例+4 setup/cleanup），零失败/跳过；真实生产引擎生成数据，非mock解码 |
| 组件视觉 | 每个比例8图，含Summary/Error/浅色和既有5个检查器场景；最新Summary/Error/浅色已目检，数值列/选中/页签可读。仍不是完整应用或逐像素原版验收 |
| 既有配色/静态检查 | 6项 authored-token contrast通过；Python/API/PowerShell CI语法及diff检查通过 |
| 完整新Qt构建 | **environment_blocked**：Qt-enabled配置的qmlimportscanner无法写build/.qt/qml_imports/showpsisi-qt_conf.cmake；SDK既有Low/NoWriteUp标签未改变。未把CoreOnly或组件宿主当作新生产Qt |
| 真实Windows新工作台 | **NOT_RUN**。用户查看中的Qt45044/core82308仍为de2b1d5旧CI产物；新代码没有装入那个进程。NXTSA桌面busy时没有抢前台 |
| Hosted CI / 分发 | 新CI组件路线已写入源码，尚未执行托管新revision；本阶段未push/发布/安装。完整Qt候选包与用户实机验收仍是后续门槛 |

正式组件凭据（本地ignored文件；fresh clone按测试命令重现）：

- [100% result](../artifacts/nxtsa-parity-20261025/p1-evidence-final-1/run-1792914662618107600/result.json)
- [150% result](../artifacts/nxtsa-parity-20261025/p1-evidence-final-1.5/run-1792914665561063700/result.json)
- [Summary](../artifacts/nxtsa-parity-20261025/p1-evidence-final-1.5/run-1792914665561063700/transport/summary.png) / [Error](../artifacts/nxtsa-parity-20261025/p1-evidence-final-1.5/run-1792914665561063700/transport/errors.png) / [浅色](../artifacts/nxtsa-parity-20261025/p1-evidence-final-1.5/run-1792914665561063700/transport/summary-light.png)
- [严格引擎记录](../artifacts/nxtsa-parity-20261025/p1-engine-final) / [新统计8项](../artifacts/nxtsa-parity-20261025/p1-engine-final/test_transport_statistics.json)

### 新增可复现测试路线

可选 SHOWPSISI_BUILD_QT_COMPONENT_TESTS 构建官方 QuickTest API 的独立宿主，不需要moc/rcc，输出在component-tests/Release，不进入生产bin或分发包。完整Qt主程序仍走原来的资源编译。Windows和Linux现有CI均已接入组件路线，不能以本地结果宣称托管通过。

构建时额外设置 -DSHOWPSISI_BUILD_QT_COMPONENT_TESTS=ON；若单测组件，可用 BUILD_QT_UI=OFF。显式指向匹配的SHOWPSISI_CORE / SHOWPSISI_TEST_CORE，再运行：

    python scripts/ci/qt_components.py --binary build/component-tests/Release/showpsisi-qml-tests --artifacts artifacts/qt-components

Windows加.exe，必要时提供 --qt-sdk 指向已安装的同版本SDK。脚本使用独立生成数据、QML输入副本和截图目录，保留失败输出；要求实际测试总数、所有提交用例、零skip、无QML错误和全部截图完成。Windows按既有CI规则设置Basic、系统字体及QT_FORCE_STDERR_LOGGING，防止GUI子系统只向调试器写诊断；早期空输出未记为通过。测试输入/展示副本不写用户设置或原始捕获。

独立组件报告现在记录实际engine/runner路径与SHA256、加载QML/生成输入/命令/输出哈希，以及component_scale_factor。它显式说明**单凭本报告未证明source→build绑定**；CI构建记录与本地clean-build命令/源码检查点另行提供。现有CI各平台只运行其配置档位，本地100%/150%双档不等于CI已建双档矩阵。超时会保留部分stdout/stderr、命令、所属PID和失败阶段；producer失败同样产生原子FAIL receipt，额外6项harness回归覆盖这些路径。

同一Hotbird原始输入的新增生产引擎读回：[p1-hotbird-transport.json](../artifacts/nxtsa-parity-20261025/p1-hotbird-transport.json)。223404包 / 88个PID，PID0x0712为12629包、未加扰；transport header errors=0，全部包数守恒，样本SHA256前后不变。该结果是API验收，仍不是新完整Qt实机验收。

### 下一高价值切片：Raw Packet → section来源（设计，尚未实现）

1. 先补原版Packet Explorer与section双hex的共用核心查询，暂名query_packets，新增方法前先冻结schema；不要在QML读取TS或另启解析线程。
2. revision、源文件身份与观察窗口必须匹配；有界start/cursor/limit，最多100包。重新检查source size/mtime等身份，源变化即失败；preview范围外不得默默扩展已分析证据。
3. 同时返回physical188/192/204封装字节、normalized188字节、源文件offset与原包index；sync错误保留raw且PID=null。header/adaptation字段带bit/byte锚点，CRC/continuity/PES状态分开。
4. section id + occurrence定位其起止包，保留中间其他PID及实际包index，不把稀疏源区间伪装连续payload。历史cutoff和返回上下文复用P1框架。
5. 测试覆盖三封装、首末边界、零/超限、bad sync/TEI/加扰、源修改、旧revision、preview间隙、同PID多section和字段→包→返回；合成fixture无owner路径。
6. PES/PTS/DTS、PCR量测随后沿同一模型增量；Teletext/媒体只读参考包在NXTSA独立目录，迁移前核验正式提交、输入有效性与许可证。UK短PCM参考不意味着视频golden已建立。

## 不可倒退的合同

C++ / TSDuck 继续拥有解析、对象身份、来源、校验、编辑与导出；Qt / Tauri 使用同一 JSONL 业务模型。QML / JS 不另写第二套解析器或扫描生命周期。保留当前统一检查器与高级工作区、历史截面、编辑导出、拓扑、规范索引和独立 DVB-I 工作区；兼容入口不能覆盖它们。

新增对象沿用 analysis revision、cutoff、source ID、原始字节锚点和显式 unknown / unsupported / resource_limit。模块完整哈希或 null 的合同不放宽。私有描述符不能仅凭 tag 推断语义。原始完整 TS、原始短捕获、重建 SI-only 派生 TS 是不同输入，媒体、码率和时序验收必须绑定原始输入。

布局以可见信息、动作作用域及恢复结果为准。可以用 Qt 页签/工作区实现原版 MDI 的用户结果；若改变入口、关闭/重开或上下文保持方式，应记录差异供用户决定。原版的 EOF Stop 错误、共享 PID 的错误节目标题、图像瑕疵和窗口裁切不应复制为目标行为。

## 逐组差距矩阵（起始main基线；P1增量见上节）

“已有”仅表示当前基础；“补 UI / 补引擎 / 待原版证据”可同时出现。实测是本次固定输入和动作的有限证据，不表示整组通过。

| ID / 用户任务 | 已有基础与本次证据 | 补 UI | 补引擎 | 待原版证据 / 下一验收 |
| --- | --- | --- | --- | --- |
| UX01 文件、分析、停止/取消、错误 | analyze / cancel_analysis / pause_analysis / resume_analysis、完整/预览覆盖；两端打开/扫描及原生 picker 取消实测 | 对应原版 Start/Stop/Pause 入口、命令作用域与状态；取消后焦点和结果规则 | 复用现有单 owner 生命周期，不新建第二扫描状态机 | 扫描中暂停/取消、坏文件、第二文件、关闭中止未在本轮实测；EOF Stop 报错不算中途取消 |
| UX02 Summary / Error / PID 统计 | 包数、包长、服务、section/CRC 与 demux 诊断已有；原版六字段和 Error 页实测 | 六字段、可见底部 Summary/Error、PID / #of packets / PacketRate / Comment、排序与选择导航 | 全 PID 统计、错误分类/分母、可信时钟/码率；当前 PSI/SI 监测计数不能冒充全 TS/AV 错误 | PID rate 单位与算法、历史 cutoff 总览规则、错误样本；同文件数据/切页/命中分别验收 |
| UX03 Sections / Tree / Hex | 统一树、字段、section hex、历史与分页；同一 PMT 174 bytes 实测一致 | 原版 Field / Bits / Value / Comment；原始 TS 包与 section 两个字节面板；修复 Back 筛选/选择恢复 | 有界原始包查询、字段 bit 范围与包/section 来源映射；不能由前端猜偏移 | 原版字节着色与 bit 锚点需逐字段校准；跨 section/页、空搜索、折叠、返回和重开 |
| UX04 服务 → PMT → ES/PID / EIT | PAT→SID 0x0008→PMT 0x0108；Services / EPG / 媒体 PID 与来源基础；原版右键 PMT 实测 | 对应节目树、右键 View Tables / PMT / SDT / EIT、ES 动作和返回上下文 | 复用服务身份/现有表解析；媒体细节沿 UX07，不重做节目采集 | EIT 选择、共享 PID、多 TSID/ONID、缺 PMT 与服务切换；不能把双击展开当作 PMT 打开 |
| UX05 AIT / 应用 / carousel 关联 | application_signalling 与来源卡片；同 AIT v0 / PID 0x1EC6 / 77 bytes；Qt 精确 source jump + Metadata 返回实测 | 应用列表/属性/位置入口、显式关联和未解析状态、回程选择 | 复用现有 carriage/location 与 topology；缺失的 carousel/object 关系需有来源的增量 | 原版 AIT→carousel 自动关联路线本轮未验证；不能从并列存在推断已关联 |
| UX06 Timing / Bitrate | 到达轴明确 packet index，提供用户码率时可换算；原版 Bitrate 对话框实测 | Program / PID / Bitrate / Current、图形/排序/范围；Timing 独立视图入口 | 有界逐 PID/PCR/PTS/DTS 量测，单位、分母、有效区间、回绕与断点；当前不是 PCR 实测 | 原版独立 Timing 路线未找到并未判定不存在；Bitrate 2597007.00 的单位/算法未独立确认 |
| UX07 PES / ES / 时间戳 | PMT stream_type/媒体 PID 语义存在；原版 PES header、Bits、PTS 和双 hex 实测 | PES 列表与包/ES 详情联动、独立分页/搜索、位置返回 | 当前没有应用级 PES 重组/索引查询；需截断、TEI、加扰、连续性和 PTS/DTS 的有界模型 | 原版 1/50 与 1 of 643 计数语义、DTS、跨 PES、多流、缺起始包；索引不算媒体解码 |
| UX08 DSM-CC 模块/块 | DII/DDB 来源卡片、same-PID bounded 重组；Qt DII 与 complete / incomplete hash-or-null 实测 | 模块/块表、版本/epoch、缺块/冲突列表、来源导航和选择恢复 | 复用 DsmccModules；更大分页源集合/有依据的跨 PID 关联另定范围 | 不完整/冲突/resource_limit/版本变化不得出现完成哈希；SDK 注册不算应用完整支持 |
| UX09 BIOP / OC / 目录与文件 | 仅模块重组；原版 OC Files / OC Hierachy / BIOP List、SRG 和层级实测；短捕获文件表为空 | 对象树、Name / Size / Type / Module / Cycle、内容、键与绑定详情、回程 | 实质缺口：BIOP 对象/文件系统、有界解压、目录绑定/循环、跨模块作用域；现有 SDK module-info 结构校验不能替代 | 用完整原始捕获验证文件/class/config；先复用 NXTSA 明确提交与专项测试证据，不能以空树通过 |
| UX10 Teletext | 当前 core 没有应用级页面组装/渲染路径；原版 PID 0x0653 彩色 page100 和下一捕获实测 | magazine/page/subpage/search/前后、颜色/字符与原始行、来源位置 | 有界 Teletext 解码/页版本与字符集模型、错误及缺行状态 | “下一捕获”未证明等于下一页码；共享 PID 的 Program1 标题是原版差异；需更多真实字符/页样本 |
| UX11 MPGThumb | PMT 媒体类型基础；原版 PID 0x0712 真 I/B/P 图像，选第3帧联动 Picture Header | 图像带/滚动、选中帧、Titles / Bits / Values / Description、错误可见 | 帧/GOP 索引与真实图像解码是两个里程碑；新增依赖须固定版本、分发审查、资源/取消界限 | 720×576、顺序和来源帧需对齐；加扰 0x03AC 应解释不可解码；部分图像瑕疵非正确性 oracle |
| UX12 MP3Wave | PMT 音频 PID 基础；原版 Play Audio 打开真实双色双通道声波、Layer2 / 48000 Hz | 秒轴、通道、选区/位置、Play/Stop、头字段与来源 | PCM 解码/有界波形桶与时间映射；PES 长度图不能叫声波；播放生命周期另定 | Play/Stop 已操作但未录音/独立测音；听感、采样幅值、游标/同步/时长仍待验 |
| UX13 菜单/工具栏/状态/子窗口/键盘 | Qt 统一/高级两入口，F6 + Enter 与 picker 取消实测；原版菜单、MDI Ctrl+F4 恢复实测 | 对应入口清单、禁用原因、状态作用域、详情关闭/重开/位置保持；保留当前快捷键能力 | 使用现有模型和状态，不把句柄当业务 ID | 全键盘、焦点/屏读、窄窗、100%/150% DPI；系统配置200%并非完整 DPI 验收 |
| UX14 config / class / 细节 | 当前原始字段/hex/XML 可查；没有 OC class/config 内容工作区 | 只读预览、对象属性、关闭返回所选对象；每个动作独立验收 | 依赖 UX09 对象/内容解析；class 仅展示不执行，配置不加载执行 | 原版该组本轮 NOT_RUN：短捕获没有文件列表；窗口能开或类名存在不能证明功能 |

## Summary 信息布局基线

原资源 DIALOG_138：364×310 **DLU**，font size 10，14 个控件。DLU 不是 px；后续依据明确字体与有效 DPI 转换，不能硬编码像素近似为验收。

| 字段 | 控件 ID | 位置 / 尺寸（DLU） | 显示与统计约束 |
| --- | --- | --- | --- |
| FileSize | 1010 | 45,14 / 50×12 | bytes，分组数字，绑定输入 |
| Total Packets | 1006 | 158,14 / 50×12 | 实际包数整数 |
| BitRates | 1007 | 259,14 / 50×12 | bps，必须注明测量/推算依据 |
| Duration | 1008 | 158,32 / 50×12 | h:m:s；无可靠时钟显示未知 |
| Errors | 1009 | 45,31 / 50×12 | 错误范围与分类可追溯 |
| Packet Size | 1011 | 259,31 / 50×12 | 真实封装包长 |

保留中间 PID 列表与底部 Summary/Error 切换，不能被 tab 覆盖。原版本次显示 41,999,952 bytes / 223,404 packets / 45,940,024 bps / 00:00:07 / 0 errors / 188 bytes；这是固定样本观察，不是通用算法 oracle。重建版的 100ms timer 是实现绕行，不是 Qt 需求。

## 页面合同模板与共享模型

每个 UX ID 在实现前冻结：入口/菜单/快捷键、source identity/revision/cutoff、列名/单位/排序、默认选择、单击/双击/右键、展开/分页/搜索、详情联动、返回恢复、关闭/重开、loading/empty/error/partial/cancel、可访问名称/焦点，以及数据+操作+截图证据。对拍至少包括：

1. TS → Summary → PID → section → 字段/原包/section hex → 返回同 PID。
2. service → PMT → ES/PES → PTS/DTS/源包 → 返回同 service。
3. AIT → module → BIOP directory → file/class/config → 返回；缺块不显示完整内容。
4. 历史 cutoff ↔ 当前，字段、源区间和选择不串版本。
5. 打开取消、坏文件、第二文件、扫描中暂停/取消、关闭/重开。
6. 仅键盘贯通、窄窗、100%/150% DPI 下关键操作均可达。

现有 API 入口以 [api/tools.json](../api/tools.json) 为准：analyze / query / query_result / query_transport / inspect / query_topology / diff_snapshots / preview_rename / export 与取消/暂停/继续等。现有 Metadata 合同见 [APPLICATION_SUMMARY_API](APPLICATION_SUMMARY_API.md)，模块合同见 [DSMCC_RECONSTRUCTION](DSMCC_RECONSTRUCTION.md)。

query_transport 已交付上述scan-global统计；其余仍为**待设计模型**：raw packet ranges、PES/ES indexes、clock observations、BIOP objects/content、Teletext pages、video frames、audio waveform buckets。按能力可扩展 query/inspect 或新增有版本的方法，实施时再改 schema。统一携带源身份、起止包/字节范围、cursor/limit、partial/reason 和资源上限；外部解码器结果也必须回指输入，而非用 UI 行号充当身份。

模块对象继续保留 PID / download_id / module_id / module_version / announcement epoch；对象键还要带 carousel/module/epoch 作用域，不能跨版本全局合并。解压分别限制输入、输出、倍率、深度、工作量与取消，未完成/冲突/超限为 null 内容与明确原因。现有 16 MiB/module、64 MiB hash work、256 identities、2048 source sections 等边界继续有效，变更需单独合同与测试。

## Qt 优先实施阶段（尚未实施）

| 阶段 | 实施内容与复用入口 | 验收门槛 |
| --- | --- | --- |
| P0 已做本轮 | 固定正确工作树、产物/样本身份、45个原生操作场景及14组差距 | 只对明确测过的动作下结论；余项维持 partial / NOT_RUN |
| P1 源码/组件已交付，完整应用待验证 | Main.qml / UnifiedInspector.qml / InspectorModel.js；Summary/Error/PID布局、Sections与服务入口、Back 状态；复用 query/inspect、现有 History/Metadata | 先补可信统计合同再显示码率/时长；同输入字段/动作/返回一致；不删除高级工作区 |
| P2 Timing / Packet / PES | core 单 owner 增量索引、原包/section来源、PTS/DTS/时钟模型；Qt只消费共享查询 | 33-bit/90kHz、回绕/断点、截断/TEI/加扰、随机访问与分页测试；原始流独立验证 |
| P3 DSM-CC → BIOP → OC | DsmccModules / ApplicationSignalling 与现有 topology/source cards；参考正式 NXTSA提交，先定API再接树/文件视图 | 保留 hash-or-null；对象作用域、缺块、冲突、循环/解压上限、内容哈希及回程；完整原始捕获证据 |
| P4 Teletext / 实际媒体 | 页渲染、帧索引→图像、音频索引→PCM波形/播放；依赖固定与分发审查先行 | 各自分阶段数据与真实输出验收；索引完成不得标图像/波形完成 |
| P5 原生与用户验收 | Qt逐页数据/动作/视觉对拍；保留两前端回归 | 多文件/取消/历史、100%/150%与窄窗、键盘；Tauri单独记录。用户看完整功能后决定UX差异 |

现有回归复用： [统一检查器](../tests/test_unified_inspector.py)、[QML 交互](../tests/qml_unified/tst_unified.qml)、[原生验证驱动](../tests/verify_unified_native.py)、[应用卡片](../tests/test_application_summaries.py)、[carriage](../tests/test_application_carriage.py)、[DSM-CC 重组](../tests/test_dsmcc_reconstruction.py)、[响应式分析](../tests/test_responsive_analysis.py)、[取消](../tests/test_cancellation.py)、[Qt topology](../tests/test_qt_topology.py)。这些是复用入口，本轮文档变更没有重跑整个产品测试，也不能据存在测试文件宣称新功能已测。

## 明确待办与历史边界

- qt05记录的筛选后Back缺口已在P1源码修复，并有真实引擎QML组件回归；尚不能据此声称新完整应用的Windows实机路线通过。
- PR29 的导航变化可能重置焦点、手动原生驱动所属进程树清理、机器SDK路径仍保留待办。常规CI缺unified专项回归已由P1补入源码路线，托管执行与完整应用门槛仍待验证。
- [2026-10-18 operation handoff](OPERATIONS_PARITY_HANDOFF.md) 的 Web BIN / Use snapshot / Qt 对比选择等属于历史待复核，本轮没有重新运行其保存/导出流程；不能直接宣布仍坏或已修。
- 构建、CI、静态测试、offscreen 图不能替代本次之外的 Windows 真实交互验收。后续实现按 [交付 runbook](DELIVERY_RUNBOOK.md)、[CI 合同](CI_TEST_CONTRACT.md)、[取消合同](ANALYSIS_CANCELLATION.md)、[协议覆盖](PROTOCOL_COVERAGE.md) 执行；SDK 注册、解析、应用语义和完整协议支持分别报告。


## 2026-10-25 core SI implementation (UX03; user-priority correction)

The current slice concentrates on the original SI inspection interface. No new
Summary, media, Timing, playback or export feature is included in this slice.
`UnifiedInspector.qml` now groups the navigation tree by PSI/SI table family and
shows an expandable Field / Bits / Value / Comment tree table, hexadecimal plus
decimal values, and a visible Section hex/ASCII pane. Field clicks highlight and
scroll to the corresponding bytes; byte clicks reveal the narrowest matching
field. Equal ranges prefer a named field over opaque payload. F6 cycles the tree,
field table and hex pane; arrow keys operate each region. Back restores field,
expansion and scroll context. Unknown SDK attribute offsets clear the highlight.

`inspect.si_structure` is produced by `core/SiWireFields.h`, not inferred in QML.
Its `bit_offset` and `bit_length` are MSB-first positions in this exact section's
`raw_hex`. Headers and supported PAT/PMT/CAT/SDT/NIT/BAT/EIT/TDT/TOT loops have
bounded ranges. The descriptor layouts for service, network/bouquet name, short
event, registration, CA, ISO-639 and stream identifier are emitted only after
context-aware SDK identity/decoding succeeds. Unknown/private payloads remain
opaque. Existing native/decoded trees, exact descriptor views and advanced
workbench remain available. A malformed envelope does not establish loop ranges.

Validation is against HEAD `b305ef7` plus this slice, not the old main portable.
The production engine was clean-built in the existing isolated CoreOnly build;
18 section-evidence and 44 protocol-coverage tests passed. The Qt component suite
uses actual production-engine output and tests click selection, shared-byte bit
fields, unknown offsets, descriptor selection, expansion, keyboard and Back at
100%/150%. Receipts live under `artifacts/nxtsa-parity-20261025/si-final-*`.
The original Hotbird input independently confirms PMT PID 0x0108, program 0x0008,
version 13, PCR PID 0x0712, 174 bytes and seven streams (`si-hotbird-evidence.json`).
`si-hotbird-pmt.png` is a real Qt offscreen render of that engine detail.

Remaining differences: this is not complete original MDI/pixel parity; the
original separate source-TS-packet hex pane is not implemented here. Section
bytes must not be relabelled as original TS packet bytes. Not all descriptor
semantic subfields have bit ranges. Complete new application/native interaction
acceptance remains pending; no foreground input was performed.
The previously attempted Qt-enabled build command was
`cmake --build build --target showpsisi-core --parallel 2` after `scripts/env.ps1`.
CMake regeneration failed before compilation because the existing kit's
`C:/Users/hentai/Documents/ShowPsiSi/.deps/Qt/6.7.3/msvc2019_64/bin/qmlimportscanner.exe`
could not write `build/.qt/qml_imports/showpsisi-qt_conf.cmake` (exit 1;
`artifacts/nxtsa-parity-20261025/p1-core-build.log`). This was a Qt-enabled
configuration failure, not a newly completed full Qt compile. Its child argv was
not captured. No unchanged failing code-generation route or security-label
change was retried for this slice. CoreOnly and the existing public QuickTest
host avoid that generator and establish only engine/component evidence.


## 2026-10-25 original visual reconstruction (supersedes dark P2 preview)

User correction: reproduce the original colors, icons, fonts and layout before
any redesign. `UnifiedInspector.qml` now uses the original light treatment,
actual NxTSA bitmap icons, Programs / PSI Packets navigation, a dense unstriped
field tree, red values, yellow selection and dual hex/ASCII panes. The field
tree stays complete while byte selection reveals a matching descendant. The
horizontal and vertical pane boundaries remain adjustable. Header/field widths
and ten-byte hex rows follow `nx19-pmt-field-0.png`; this is not a claim of full
original MDI/window-chrome or exact font/pixel parity. Compact search/back/page
controls retain existing functionality at the bottom of the tree.

`inspect.source_packet` supplies the first observed original 188-byte TS packet,
with source packet index, file offset and physical framing stride. It reads the
source only when file size/time still match analysis; unavailable/changed files
leave the packet pane unavailable while retained Section bytes remain readable.
The optional `section_offset`/`section_bytes` map only the matching PSI payload
fragment in that packet, including multiple sections after a pointer field.
A spanning Section is never presented as wholly contained in its first packet.
The underlying source identity guard is metadata-based, not a fresh full-file
cryptographic revalidation. No playback, all-packet browser or export increment
was added. This supersedes the prior missing-first-source-packet-pane boundary.

Validation: clean production core and QuickTest host build; 4 unified-engine
tests cover exact layout, 188/192/204 framing, changed source, multiple Sections
and continuation; 18 existing Section tests pass. The component suite runs
11 SI checks plus 15 existing Summary checks at both 100% and 150% (30 PASS
including four setup/cleanup entries), with palette, packet/Section selection,
original grouping and divider drag checks. Existing theme tests: 6 PASS;
presentation model: 50 assertions. The current original-input preview is
`artifacts/nxtsa-parity-20261025/classic-hotbird-pmt.png`; associated raw engine
state is `si-hotbird-evidence.json`, and actual renderer checks are in
`classic-hotbird-qt.log`. These remain offscreen component evidence. The
previous full-app Qt code-generation write blocker remains; no foreground or
full new application acceptance is claimed.


## 2026-10-25 network / TP / named program follow-up (in progress)

User authorized resolving the Qt build blocker and organizing programs by network,
TP, name and LCN in the existing original style. Current readback confirms the
shared SDK generator retains inherited Low/NoWriteUp and the build directory has
normal integrity. Do not repeat the unchanged local generator route or change
shared SDK/security labels. Use the existing hosted Windows CI build/package route,
then verify source/artifact identity locally. This route change addresses delivery;
it does not claim the local integrity mismatch has been repaired. Stop on a hosted
build failure, diagnose its retained evidence, and preserve the existing gates.

The classic tree consumes revision/cutoff-bound, paged engine topology and service
metadata. Network and transport identities remain separate; names come from SDT /
NIT, LCN is used only when resolved, and TP parameters are advertised declarations.
Unknown/conflicting data and remote announced services remain explicit. Existing
PSI tables and field/byte inspection stay available.


Complete Windows candidate run 40195156893 passed all five jobs and produced
artifact 12600545735. Its 698-file manifest and source tree were verified locally.
The full packaged app passed eight isolated checks in explicit DVB mode: automatic
network/TP loading, keyboard program activation, PMT selection, source replacement,
resolved LCN, light SI and QML diagnostics. Auto interpretation intentionally keeps
ambiguous signalling unresolved; network/TP projection requires the existing
explicit analysis profile, not a separate parser-enable toggle.

Further whole-window review exposed field Home/arrow keys toggling Section groups.
Navigation now moves focus without folding; Return/Space or clicking activates a
group. A real QML key regression covers root navigation, fold/unfold and the exact
field/byte selection. The updated candidate requires a new hosted build; the prior
successful artifact is not evidence for this follow-up source revision.


## Local Qt integrity diagnosis reopened (2026-10-25)

The user explicitly requested fixing local compilation. Fresh ancestor readback
shows an explicit inheritable Low/NoWriteUp label on the original ShowPsiSi root;
the shared SDK inherits it, while the current worktree/build root is unlabeled
(medium). No evidence yet identifies the historical setter. This new observation
allows a bounded test of an existing, already-low output location without changing
any security descriptor. Capture the actual scanner token before resuming it and
compare identical scans into fresh medium vs inherited-low task directories.
Budget: one paired probe, then one fresh local Qt build if the low output works;
stop on token-query failure, unexpected scope, timeout or no new evidence. Preserve
all earlier CI artifacts. No SDK relabel, ACL broadening or global configuration.

### Local build blocker resolved (2026-10-25)

The paired real-process probe confirms Medium parent (`S-1-16-8192`), Low
scanner child (`S-1-16-4096`), same user and zero restricted SIDs. The identical
scanner exits 1 without output in the Medium worktree, but exits 0 and writes
1,665 bytes in the original workspace's inherited-Low artifacts directory.
The original workspace root carries the explicit inheritable Low/NoWriteUp
label; its historical setter remains unknown. No security descriptors changed.

A fresh full Release build from source HEAD `08d0a443b5ad16c03b050dbf14c8f42b388760dc`
plus the dirty `scripts/build.ps1` and `scripts/env.ps1` patch succeeded, placing
outputs under the original workspace's `artifacts/local-qt-integrity-20261025/build`.
The script now accepts `-BuildDirectory` for Qt/core builds and respects an
explicit `QT_ROOT`. The default build route is unchanged. Tauri custom-output
packaging is outside this fix and is explicitly rejected.

The locally built application passed all nine existing complete-app classic-SI
checks using the actual engine: light SI, automatic network, actual TP,
keyboard program/PMT selection, field-tree navigation, source replacement,
known LCN and absence of QML errors. The Hotbird capture hash exactly matches
the earlier CI candidate capture. These are offscreen software checks;
interactive desktop/GPU/dialog acceptance is not implied. The test-owned app
was terminated by the harness after capture (exit 1 from forced cleanup).

Evidence is under the original workspace's ignored
`artifacts/local-qt-integrity-20261025/`: `probe.py`, `probe-result.json`,
`build.log`, `validate-local.py`, `runtime-result.json`, and
`local-classic-1792936315344021200/report.json`. Executable SHA256 values:
- core: `fd0c9f4d062809e2c9e25b6691c6091f2b0c833d31dff5a0d7b7df4737339d5b`
- Qt: `5e8010ac9d26c45e089333f098954ef37771ba023e0e50f0bf5da763d06ba075`

This resolves the local build/output-permission gate. This follow-up patch is
local and uncommitted; the earlier hosted/PR results do not validate this patch.


## Tree stability and field-column resizing (2026-10-25, in progress)

The user reports whole-view flashing, lost tree position, and fixed field
column widths in the locally built preview. Source inspection identifies the
backend clearing detail during inspect, a JS-array navigation model replaced
on detail changes, and automatic Center scrolling. Reuse the verified Low
output build route; no SDK permission investigation is reopened. Add delayed
inspection/scroll-anchor and actual mouse-drag column regressions, then build
and run the complete local application. Budget: targeted component regression,
repair supported failures, one candidate build and runtime check. Stop on
invalid environment or no new evidence; preserve the prior runnable preview.

### Tree/columns local candidate result

`UnifiedInspector.qml` now retains the last displayed detail only while the
next inspection is pending; failed inspection still clears the stale detail.
The navigation ListModel updates by stable key, preserving the focused row,
viewport anchor and live delegate. Selection no longer recenters the tree.
Field/Bits/Value/Comment share adjustable pixel widths, with draggable header
separators, double-click content fit and a synchronized horizontal scrollbar.
Column widths survive record changes during the session.

Regression includes an explicitly delayed inspect, failure clearing, an
80-record synthetic scroll stress case derived from real engine data (actual
mouse click and delegate/viewport identity assertions), and actual column
mouse drag/double-click. Component result: 35 PASS including 4 suite lifecycle
entries (31 test cases), zero failures/skips. Initial test preparation errors
(incorrect QtTest double-click API and target row not instantiated) were fixed;
failed receipts remain preserved. The complete locally rebuilt app passed all
nine existing real-engine SI checks. A first complete-app attempt hit a
transient diagnostic-client PermissionError; a new run with traceback capture
passed, without changing application permissions or the client implementation.

Evidence: original workspace `artifacts/si-navigation-resize-20261025/`, including
`components/run-1792939852046510900/result.json`, `build.log`,
`runtime-result-2.json`, `delivery-checkpoint.json`, and `Launch Local Qt.cmd`.
Qt executable SHA256: `1be99923e937f45419f28e2d404129dcbd7f4426e39142313b736c9e205f20ba`.
Source identity is HEAD `08d0a443b5ad16c03b050dbf14c8f42b388760dc` plus the local
uncommitted UI/tests/build-script/docs patch; hashes are in the checkpoint.

The candidate was launched on the Windows desktop and its Hotbird SI view was
observed. Native automated input stopped on detected concurrent user input;
no native click/drag pass is claimed. The candidate remains open for the user.
The old executable is preserved. This local interaction repair is not yet
committed/pushed; earlier hosted results do not validate the new patch.


## Missing left SI hierarchy correction (2026-10-25)

User reference screenshot shows PMT program descriptors / ES / ES descriptors,
and NIT network descriptors / ONID-TSID transports / transport descriptors,
simultaneously expanded in the left tree. Previous navigation exposed only a
single Section node and did not satisfy that structure. Existing original-app
reference nx18/nx19 establishes table/field/hex identity, not complete tree
parity. The local NXTSA mfc_shell.cpp is a reconstruction, not authoritative
original source; use the user screenshot as the hierarchy reference.

The engine already supplies scoped wire-loop ownership and exact bit offsets.
Project those nodes without flattened descriptor duplicates or SDK attribute
subtrees, retain expanded inspected tables across navigation, and route child
clicks through the owning record before positioning fields/bytes. No protocol
parser change. Budget: targeted model/component regressions, full local build,
complete-app check with actual PMT and NIT; stop on invalid evidence/environment.
Reuse the verified Low output build route, without ACL changes.

### Internal SI tree local acceptance

The left navigation now projects exact engine wire-loop ownership: PMT program
and ES descriptor lists; NIT/BAT network or bouquet descriptors and ONID/TSID
transports; PAT programs, SDT services, and EIT events when carried by the wire
structure. Descriptor nodes use engine-provided names/tag and byte provenance;
SDK attribute trees and the separate flat descriptor index are not duplicated
in the left tree. Unsupported structures are not invented. Table sections keep
separate record identity; this is not a claim of complete original-app parity.

Nodes expand/collapse via [+/-], Left/Right and Space. A record lazily loads its
structure on selection/expansion. Up to 64 inspected structures are retained
per source/revision, with bounded 100-child pages. A cached child from another
table selects its owning record before positioning the field group and exact
Section/source-packet bytes. Expanded PMT/NIT branches coexist, source change
clears the cache, and long labels have horizontal scrolling. Prior viewport
stability and adjustable field columns remain covered by regression.

Validation: 83 presentation-model assertions; 37 Qt PASS entries (33 cases +
4 suite lifecycle entries), no failures/skips; 14 complete locally built app
checks on actual Hotbird data plus the declared fixture. Initial regressions
caught non-family expansion-state warnings and a duplicate async detail
assignment clearing selected-field position; both were repaired and rerun.
The final Windows native candidate was opened with Hotbird PMT PID 0x0108,
program 8. Actual mouse drag widened its tree; actual mouse click selected
teletext_descriptor at section/stream/28/descriptor/33. Observed left-row
position unchanged, right field group at top, and both hex panes highlighted.
Only this bounded native operation is established, not all original UI paths.

Evidence is in original workspace `artifacts/si-internal-tree-20261025/`:
`components-final.log`, `runtime-result-final.json`, `build-final.log`,
`native-preview.json` (actual capture and source), and `delivery-checkpoint.json`.
Source is HEAD `08d0a443b5ad16c03b050dbf14c8f42b388760dc` plus the local dirty
UI/model/tests/build-script/docs patch. No new commit, push or merge occurred;
prior hosted CI does not validate this patch. The candidate stays open for review.


## Generic table hierarchy audit (2026-10-25)

User clarified that every table must expose its reference-data hierarchy, not
just PMT/NIT examples. Source audit confirms SiWireFields covers only selected
wire layouts and the prior navigation projection discarded the engine's native
semantic trees. This leaves AIT/UNT, DSM-CC, ATSC, ISDB, SCTE and other decoded
families at Section-only navigation despite existing structured evidence.
Use existing pinned reference vectors as a whole catalog. Preserve selected
section vs assembled table scope and never invent byte offsets for semantic
nodes. No protocol parser change. Budget: one catalog audit, generic renderer
plus regression repairs, then one local candidate build and full-app checks.


The user additionally specified the mouse contract for both SI trees: a single
click on [+/-] toggles; a single click on row text selects/locates; double-click
on row text toggles. Earlier left-family activation and right-field-group clicks
violated this contract. Unify delegate behavior and verify actual mouse sequences
for family, record, internal-loop and right-field group rows. Keyboard expansion
remains explicit through Left/Right/Space (and field Return).


User also reported missing vertical field grid lines. Add viewport-height column
boundaries aligned with the same column-width values as the headers and rows;
keep lines visible through selected rows and blank space, and synchronized with
horizontal scrolling. Verify alignment after resize and both-axis scrolling.


### Generic hierarchy and interaction local acceptance

The navigation now uses exact wire loops where available and the existing
native semantic tree otherwise, recursively and without a table-family allowlist.
The pinned catalog contains 52 inputs and 34 native table names; 37 inputs had
children hidden by the old navigation. All 52 now preserve available structure
and attributes (41 use the generic route). This is reference-vector coverage,
not a claim that every broadcast table or original-app behavior is supported.
Multi-section native trees are labeled Assembled with their section count;
semantic nodes without proven wire ranges explicitly report unavailable byte
ranges instead of inventing hex highlights. No protocol parser was changed.

Both tree delegates now use single-click +/- to fold, single-click text to
select/locate, and double-click text to fold. An uncached record double-click
retains its requested expansion until inspection completes. Field-group folding
also retains its viewport, clamped only when the resulting content is shorter.
The native check caught a model-reset scroll-to-top defect after the initial
component pass; it was repaired and added as a regression before final rebuild.
Vertical field boundaries cover the viewport and track header widths and
horizontal scrolling, including selected rows and blank space.

Final validation: 904 model assertions on 52 pinned inputs; 38 component cases
(42 PASS entries including 4 lifecycle entries), no failures/skips; 22 complete
locally compiled app checks with actual Hotbird and declared reference data.
The synthetic DVB bundle exercises AIT, UNT and both DSM-CC native structures
through the final candidate engine. Offscreen checks are distinct from native
interaction. Actual Windows mouse checks observed left text selection without
folding, double-click folding and single-click + expansion; the final rebuilt
candidate also verified right descriptor double-click folding and + expansion
at the same viewport position, and a native Field-column drag moved its vertical
boundary with the header. The final candidate remains open on Hotbird PMT.

Evidence: original workspace `artifacts/si-generic-tree-20261025/`, including
`catalog/reference-trees.json`, `before-audit.json`,
`components-scroll-final.log`, `build-scroll-final.log`, `runtime-result.json`,
`native-preview.json` and `delivery-checkpoint.json`. Final Qt SHA-256:
`14756c8d379300780685ec73519b6733e4c58909e27ef50729185915e12205e4`.
Source remains HEAD `08d0a443b5ad16c03b050dbf14c8f42b388760dc` plus the local
patch, including the new reference fixture helper. No new commit/push/merge;
prior hosted CI does not validate these local changes. Build route reuses the
existing Low-integrity output directory; no ACL or security label was changed.


## Qt and Tauri core SI synchronization (2026-10-25)

User requests matching UI and UX in both frontends. Qt local acceptance above
is the baseline; Tauri still uses the older workbench. Reuse the same model,
icons, exact wire/semantic scope and existing engine bridge. Add the classic
SI surface to Tauri and retain the older workspace through an explicit switch.
Required gates: shared-model catalog, Qt component/resource checks after moving
the shared source, real-engine browser interaction and native build/runtime if
the installed toolchain is usable. Reuse the established Low output Qt route;
no renewed security-label investigation. Budget one implementation pass plus
repairs justified by failing checks; stop environment probes after a decisive
missing dependency or access failure and report that boundary.

Native Tauri first build reached the linker, then LNK1104 could not create a
Windows Temp lnk*.tmp file. This matches the established inherited-Low child
write boundary, now at the linker temporary output. One bounded retry redirects
process-only TMP/TEMP into the existing Low artifact root; no ACL changes.

The low-temp retry passed linking and reached tauri-build, whose ACL generation
writes gen/schemas inside the source crate (verified in the pinned local SDK).
That Medium source tree is not writable by the Low build helper. Build an exact
hash-checked copy of only the Tauri sources/assets in the existing Low artifact
root, keeping the working tree untouched. This is the bounded source-output
fix, not a permission change; preserve the source manifest and final binary.


### Dual-frontend local acceptance (2026-10-26)

Qt imports `ui/tauri/web/inspector-model.js` directly; the web frontend loads
that same file. Generic native-table recursion, exact wire ranges, original
bitmap icons and network/TP/program organization now have one implementation.
Tauri defaults to the classic SI view with the same palette, typeface, field
columns, dual hex panes, explicit +/- and double-click folding, and adjustable
column/pane boundaries. The prior advanced workspace and DVB-I remain available.
Summary/PID uses the existing scan-global `query_transport` contract in both
frontends; it does not reinterpret packet counters as media/decoder validation.

The final web check uses the actual engine: 20 core interaction checks and
14 Summary/PID/generic hierarchy checks passed. The uncached raw PMT regression
also verifies that asynchronous label changes preserve the clicked DOM element
through both clicks. Its fixture has an empty PMT; it checks the decoded root,
not a nonexistent elementary stream. Four existing/default browser checks,
eight bridge checks and six palette checks passed. The shared-model catalog
passed 904 assertions on 52 inputs; the rebuilt Qt passed 38 component cases
and 22 full-application offscreen checks. These are separate evidence layers.

Both current Windows applications were started on the same 223,404-packet
Hotbird input. Qt's visible native window was inspected. Tauri's built-in
read-only diagnostic capture confirms the native WebView2 classic SI surface,
completed real scan, field grid and packet/section panes. Computer Use application
authorization timed out for Tauri, so this iteration does not claim native mouse
acceptance: the final mouse regressions ran in the real-engine browser surface.
No security labels or ACLs were changed. Browser tooling's available update was
not installed. Clean-machine deployment, native dialogs and pixel-identical
cross-platform font rasterization are outside this core-SI verification.

Evidence is in the original workspace's ignored
`artifacts/si-dual-ui-20261026/`: source manifest, Qt/Tauri build logs,
`browser/classic-result.json`, `browser/extended-result.json`,
`web-regression-final.log` plus `web-double-final.log` (corrected empty-PMT
expectation), native preview identities and Tauri diagnostic capture.
Final Qt executable SHA-256:
`8c60f40cc8681d424aa4e1c2c9ba5f7ab17597e6cab0eae0edd43b8591b65cef`.
Final Tauri executable SHA-256:
`051e875ef6a52448c56360cdaf99d6839e68c1f6873c54e9b085fe1bd429110d`.
Both were built from `08d0a443b5ad16c03b050dbf14c8f42b388760dc` plus the
reviewed local patch. Hosted checks must be matched to the published revision;
previous green checks do not validate this patch.


Hosted run 40213407212 passed both Tauri build jobs but found one selector
collision in 79 browser cases: the older evidence test selected `data-path=section`
across both workspaces, including hidden classic rows. Scope that locator to
`#tree-area`; the complete CRC/group/arrival/evidence case then passed locally.
This follow-up changes only the regression selector and this evidence note;
application source and the verified local executable hashes remain unchanged.


## 顺序实施计划（2026-10-26）

用户要求：先列计划，香港时间 2026-10-26 05:43:19（本次请求核对时间
01:43:19 后四小时）才开始实际实现。四小时为启动延迟，不是全部开发时限。
按下表编号顺序推进，两种 UI 同时覆盖；本表是计划，不是完成报告。
不提前实施代码改动。完整列表涉及多阶段开发，不能承诺一次全部完成。

基线工作树：`C:/Users/hentai/Documents/Codex/2026-10-21/task-4/ShowPsiSi`。
本次核对基线：`8f42e3bd308ef8ea6b088e15a887e22faf202ede`，工作树原先干净。
继续使用 `codex/nxtsa-summary-pid` 和草稿 PR #30；执行时重新核对，不回滚用户改动。
参考：`C:/Users/hentai/Documents/NXTSA/shared-reference/PROGRAM_DESIGN.md`
及其 APPLICATION / WINDOWS_AND_VISUAL / PROTOCOL_VIEWS / MEDIA_AND_PACKET / ACCEPTANCE 规格。
设计文档中的原版观察、静态资源、目标设计和未知项保持各自证据层级。

| 顺序 | 工作 | 完成条件与本地验收 | 规格入口 | 状态 |
| --- | --- | --- | --- | --- |
| 01 | 失败候选输入保留旧会话 | A 已分析并选中字段；打开不可读/无效 B 后，A 的结果、来源、选择和可用操作保持；成功切 B 才发布新身份；旧预览令牌不得串源 | APP-002/003/007 | 已完成：入场拒绝保留旧会话；引擎、浏览器与完整 Qt 离屏通过 |
| 02 | 两端返回恢复具体字段和位置 | 字段→另一表→返回，恢复字段身份、展开、过滤、字段/hex 横纵位置和面板状态；两端结果一致 | APP-011、VIEW-003/050 | 已完成：按字段身份恢复列宽和双轴位置，浏览器/Qt 组件通过 |
| 03 | 无映射字节清理旧高亮 | 点击未解释字节或 TS header 时，不保留另一字段的旧映射；有可靠范围的字段仍准确双向定位 | APP-010、VIEW-020/021 | 已完成：无映射选择清除旧范围，两端本地回归通过 |
| 04 | Summary 六项和原版布局对齐 | 两端有 FileSize、Total Packets、BitRates、Errors、Duration、Packet Size；两排指标、Summary/Error tab；未知/部分范围和单位明确 | VIEW-007/008、VIS-005 | 已完成：六项指标、两排自适应布局和经典浅色一致 |
| 05 | 键盘、焦点、选中行为同步 | 树方向键进入子项/返回父项、字段/hex 导航、F6/Shift+F6、Home/End 等价；文本单击、双击和 +/- 规则保持 | APP-009、VIEW-051、VIS-018 | 已完成：树/字段父子键、双 hex 光标及正反 F6，本地回归通过 |
| 06 | 原版主框架、菜单、工具栏与状态栏 | 依据资源还原主菜单和 7 个命令按钮/2 分隔位；可见命令有实际行为或明确禁用原因；帮助、树显隐和分析状态一致 | WIN-001～005/008～018 | 已实现并本地验证；原版位图、菜单命令和显隐状态对齐，未支持的输出明确禁用 |
| 07 | 多窗口与工作上下文 | 至少三类已支持视图可切换、关闭、恢复；窗口身份独立；平铺/层叠/最小化与焦点正确；重复打开实例规则明确 | WIN-006/007、APP-006/011、VIS-008/009 | 已实现：New 开启独立窗口，SI/Summary/Native Decode/Packet/Timing 支持复用、关闭、切换和排列；原生鼠标/DPI 留给 17 |
| 08 | 完整树分支与右键导航 | Programs/PSI/All Packets/DSMCC 等有依据入口；右键命中当前指针对象，View Tables→具体 PID/版本；无数据与未支持有明确状态 | VIEW-017/018/023～026 | 已实现：观测 PID 索引、DSMCC 分支及指针对象的精确表菜单；无数据明确说明 |
| 09 | Packet Explorer 原始 TS 包浏览 | 首/前/后/末及索引/PID 过滤可用；header/adaptation/pointer/payload 与真实包同步；边界、坏包和取消有反馈；返回原字段 | VIEW-022、MED-006/007、WIN-027/042 | 已实现并本地验证：原包与封装、首前后末、索引/PID、分批搜索取消、header/区域及 section 链接 |
| 10 | 跨包来源片段与精确定位 | 跨包 section 的每段真实 TS 来源可达；区分文件/包/section 坐标与 188/192/204 封装；位范围与未知状态准确；不造重组包 | APP-010、VIEW-021、MED-002/005/011 | 已实现：首个观测 occurrence 的全部可信来源片段，双 hex 可切换并使用全局 section 偏移；超过界限或不可靠明确不可映射 |
| 11 | 统计、错误与 Timing/Bitrate | 先补用户可见统计和来源说明；独立 Bitrate 条形与 Timing 页面有可信时钟、范围、单位、wrap/跳变处理；无时钟显示 unknown；诊断区分检测范围 | VIEW-009～016、APP-013/014 | 已实现：捕获流 PCR 测量、可信区间时长、原始 Timing 分页、绿条码率及跳包；无时钟 Unknown，范围明确 |
| 12 | 服务、EIT/EPG 与 AIT 追查 | 同 SID 不同 TS、共享 PID 不串源；服务→具体 PMT/ES/EIT/应用→证据可返回；缺失关联明确显示，不靠 ID 猜测 | VIEW-024～033 | 已实现：完整 ONID/TSID/SID 服务身份、ES/EPG/AIT 来源跳转及返回；同 SID、共享 PID 与歧义反例通过 |
| 13 | DSM-CC/OC/BIOP/Class/配置内容 | 信令→模块/缺块→对象→内容，三类视图可达；完整与缺块样本分别验证；Class 只读不执行；导出与原字节/身份一致 | VIEW-034～043 | 内容浏览已实现：DSI→模块→对象/绑定→只读内容、Class 与配置，两端实测；导出在 16 接入，原生验收在 17 |
| 14 | Teletext 实际页面 | 真实页/子页/捕获身份、40 列字符与已支持属性可见；导航与内容更新正确；缺行、未知字符集和不支持项明确 | VIEW-044～049、VIS-013 | 已实现真实 PES 页/子页/捕获、40×24 显示、颜色/马赛克/双高及来源跳包；部分 Latin Level 1 范围明确，两端真实字幕验证通过 |
| 15 | PES/ES 与真实音视频视图 | 先完成 TS→PES→ES 来源链，再接真实视频缩略图/帧、PCM 波形和播放；分析、解码、设备输出、停止/换源释放分项记录 | MED-001～040 | 已实现有界 PES/ES 来源链、真实解码帧与预览播放、PCM 波形和 Windows 输出控制；原始 A/V 同步不推断，输出在 16 接入，桌面验收在 17 |
| 16 | 保存、复制、输出与设置对齐 | 每种支持输出有范围/单位/来源；取消/覆盖/失败正确；配置 Cancel 不提交，分析设置标明生效时点；未支持打印/帮助入口明确 | APP-015～020、WIN-030～044 | 已实现：同一选中上下文的保存/复制，原始字节和派生 PNG/WAV 明确分开；配置确认持久化、取消恢复；本地两端检查通过 |
| 17 | 全链路、DPI 与退出收尾 | 固定输入下两端逐项对照；100/150/200% 可达；保留高级功能；换源/取消/关闭验证真实进程和资源退出；记录尚未验证项 | E2E-01～16、APP-021～026、VIS | 本机收尾完成：整链、两端原生鼠标/保存取消/正常退出通过；Qt 原生 200% 越界已修复；缩放和系统 DPI 的验证边界见下文 |

执行规则：

1. 每项开始先确认当前源码中缺口仍存在；只修改该项必要代码，Qt 与 Tauri 的
   用户行为一起验收。用现有共享模型和引擎，不复制两份协议实现。
2. 只做必要本地检查。用户明确要求不走 CI：不触发、不等待、不轮询 CI。
   提交使用 `[skip ci]` 并遵守当前托管平台跳过规则；不使用强制推送，不自动
   合并/发布。每个可交付小项验证后提交、推送，保存确切 SHA。
3. 复用已经验证的 Qt 低完整性输出目录，以及 Tauri 校验源码副本和进程级
   TMP/TEMP 的构建方式。先读已有证据，不重新调查同一权限根因，不改 ACL/安全标签。
4. 样本、SDK 与构建产物继续 ignored。构建、组件/离屏、浏览器、原生鼠标、
   媒体解码和可听输出分别报告。任何未运行层不得写成通过，不用截图/假数据替代功能。
5. 每项更新状态为“进行中/已完成/部分完成/受阻”，附源码 SHA、必要证据及余项。
   真正受阻时记录原因，继续不依赖它的后续项；不以扩大后台协议工作替代当前页面。
6. 本次定时启动后持续顺序执行，阶段结束保存恢复点并报告实际完成情况；不因
   自动化再次唤醒而重做已完成项，不把任务量写成完成率。需要用户权限/设备时
   只暂停依赖部分，继续已有授权内工作。


### 2026-10-26 延迟启动未生效后的恢复

此前只生成了待确认的任务卡片，未找到已保存的 ShowPsiSi 自动化；四小时后
没有实际启动。用户本次催办后立即开始顺序实施，不再依赖未生效的定时卡片。
第 01 项采用有界候选入场校验：先检查可读、TS 封装、字符集与范围，再清除
旧来源和预览；拒绝候选返回 input_rejected/state_preserved。两端在入场确认前
保留视图。已经开始读取后的故障、取消仍按原有 failed/cancelled 合同处理，
不把部分新流还原成旧流。取消接受与入场拒绝竞争仍在 owner 的 finish 点裁决。
复用已有 Low 输出路线，在新 ignored 输出目录构建；不重开安全标签调查。


第 01 项本地结果：`si-ordered-engine-and-cancel-final.log` 共 51 项，50 通过，
1 个可选实流样本缺失而跳过；浏览器 3 项通过，包括具体字段/位置保留及原错误提示。
完整 Qt 应用在 `si-ordered-20261026/candidate-admission-1792990368343865800/report.json`
保存三类候选拒绝前后相同来源、字段与导航上下文。Qt 为离屏，不声称原生鼠标。
这些证据均位于原工作区 ignored artifacts；本次没有启动或轮询 CI。


第 02 项：返回记录具体字段身份及列宽、字段/双 hex 横纵位置，避免依赖显示行号。
本地浏览器的真实引擎返回用例通过；Qt 组件 39 个实际用例通过（43 PASS 含生命周期），
无失败/跳过。证据 `si-ordered-components-step02-final.log` 及 `si-ordered-web-step02.log`。
其中 PID 统计旧测试已按第 01 项的候选拒绝保留合同更新；成功换源仍替换旧 PID 行。


第 03 项：两端明确记录“所选字节没有 SI 字段映射”，清掉旧范围并能重新选择
可靠字段；返回上下文也保留该状态。2 个浏览器回归与 40 个实际 Qt 组件用例
通过（44 PASS 含生命周期），无失败/跳过。证据 `si-ordered-web-step03.log`
及 `si-ordered-components-step03.log`。本地组件不等于原生鼠标验收。


第 04 项：Tauri 补 FileSize 并采用与 Qt 相同的六项顺序和两排指标；窄视口降为
两列/单列。经典 Summary 在两端均保持浅色。真实引擎浏览器用例验证 FileSize
值、六项位置和切 Error tab 后指标不变，见 `si-ordered-web-step04.log`。


第 05 项：树/字段的父子方向导航、原包和 section 的首末/逐字节/行/页键，以及
F6/Shift+F6 来源栏和各窗格的正反切换已经对齐。浏览器 4 个相关用例通过；
Qt 组件 43 个实际用例通过（47 PASS 含生命周期），无失败/跳过。
旧焦点测试已纳入新增原包窗格；Summary TabBar 切换明确聚焦实际 TabButton。
证据 `si-ordered-web-step05.log`（TS 来源栏定位修正见 `si-ordered-web-keyboard-final.log`）
及 `si-ordered-components-step05-final.log`。下一项为 06 原版主框架。


### 前五项交付检查点（2026-10-26，源码 ec2b993）

01–05 已实现并逐项提交推送：`f2fa708`、`a04af1b`、`4932996`、`6fa33bf`、
`ec2b993`。这些提交都带 `[skip ci]`，没有启动或轮询 hosted CI。
06–17 仍为待实施；下一项是原版主框架。本记录不表示整份计划完成，也没有
声称存在仍会自动唤醒的已生效定时任务。

最终本地检查：引擎/确定性取消 51 项（50 通过、1 个可选实流样本缺失跳过）；
响应式分析/MCP 31 项通过；Qt 组件 43 个实际用例通过；最终完整 Qt 应用
Hotbird→换源→AIT/UNT/DSM-CC 共 22 项通过。完整浏览器 85 项中 82 通过、
2 个 POSIX 专属场景在 Windows 跳过，1 项因新增异步入场时序仍使用即时断言
失败；将它改为等待实际 GUI 入场后，该完整旧预览令牌取消用例复测通过。
这次修正只改测试等待，不改应用程序，也不把分次结果伪装成一次全绿运行。

Qt 与 Tauri 最终 release 均本地编译成功。两个原生程序已各自用隔离设置/配置
加载同一 Hotbird PMT（PID 0x0108，334 字段），保存原生渲染读回。原生鼠标、
原生媒体播放、主框架/节目图标/DPI 的完全对齐仍未验收，属于后续 06–17。

证据在原工作区 ignored `artifacts/si-ordered-20261026/` 及同级日志：
`si-ordered-engine-and-cancel-final.log`、`si-ordered-responsive.log`、
`si-ordered-components-step05-final.log`、`si-ordered-qt-full.log`、
`si-ordered-web-full.log`、`si-ordered-web-cancel-preview-final.log`、
`native-previews.json` 和 `tauri-source-manifest.json`。原生捕获只证明该次渲染与
字段值，不证明鼠标/设备/跨 DPI 完整通过。


### 第 06 项主框架（2026-10-26）

两端共用 classic-model.js 菜单顺序、命令启用规则和工具栏槽位；复用原版 128.bmp 的 7 格位图，包含 2 分隔位。经典源配置收进 Card Configuration，Open 选择后进入 Ready，Start 才分析；高级工作区仍可到达。工具栏、状态栏、TS Tree 开关可逆，Summary 保留左树。状态栏显示本产品及版本，不冒用原产品版权。帮助有本地内容；尚未实现的保存、打印及窗口排列明确禁用，后续项目负责解锁。

修复集成期间 Summary 被 UnifiedSi 容器初始化覆盖、状态单元误挂到 DVB-I footer，以及网页菜单被工具栏覆盖的问题。当前 Qt 本地完整构建成功，实际引擎加载 Hotbird 后的 10 项完整应用离屏观察通过（含开关与 Summary）；Qt 源组件 47 项实际用例通过（QtTest 加生命周期为 53 PASS）。浏览器 9 个经典界面用例及静态资源检查共 10 项通过。证据：原工作区 artifacts/si-frame-components.log、si-frame-qt-runtime.log、si-ordered-web-step06-fixed.log。完整应用观察使用诊断接口与离屏渲染，不冒称原生鼠标或像素验收。未运行托管 CI。


### 第 07–11 项本地实现（2026-10-26）

New 开启同一输入会话内的独立窗口工作区；SI、Summary、Native Decode、Packet Explorer、Bitrate/Timing 使用真实数据组件。相同类型/身份激活已有窗口，New 可明确复制 SI 窗口。每窗保留实际控件和上下文；关闭回到前窗，Ctrl+F4、Ctrl+Tab/Shift+Ctrl+Tab、平铺、层叠、最小化/恢复可用。成功更换分析身份关闭旧窗；拒绝候选不关闭。历史 cutoff 构成文档 key，保留自己的只读分析/详情数据。标题标出文件、分析批次和 latest/cutoff。

All Packets 列出引擎观测到的 PID，不把 PSI 表列表冒充全 PID；DSMCC 使用实际表记录，缺失显示空态。右键命中指针对象，View Tables 绑定 exact section ID。Packet Explorer 通过 query_packet 直接读源文件，保留 188/192/204 原始封装与各坐标、header/adaptation/pointer/PES header/payload 区域。PID 检索每批最多 4096 包，取消使后续批次停止并拒绝在途旧答复。源文件大小/mtime 改变或 revision 过期即拒绝。原始源可读到分析窗口以外，但明确标成 raw source only。

inspect.source_fragments 对首个观测 occurrence 核验每段原字节、PID、连续性和结束位置；最多跨度 65536 包及 128 个片段，不能确认就不映射。两端可切换片段，包内 offset 加 section_begin 后才联动字段；仍保留完整 section，绝不伪造 188-byte 包。

Timing 每 PID 追踪可信 PCR 对、回绕/跳变/声明间断；采样窗口和坏包重置链。超过 10 秒或不递增的 PCR 区间不参与率估计，明确测量的是捕获的标准化 188-byte 流。Duration 为可信 PCR 区间之和，不外推全文件长度。用户给定码率与测量值分开；原始 PCR 样本最多保留前 4096，计数继续覆盖全部观测。连续性诊断单独记录，旧 Header/CRC 错误口径不混合，也不宣称完整 TR 101 290 检查。

本地证据：si-packets-engine.log / si-fragments-engine.log / si-timing-engine.log；19 项包/计数/PCR 实际引擎测试通过，跨包重组原字节核对通过。Qt 源组件 52 个实际用例通过（含生命周期为 60 PASS）；完整 Qt 实际引擎窗口检查记录在 si-documents-qt-runtime.log、si-packets-qt-runtime.log、si-timing-qt-runtime.log。新增浏览器窗口/右键/包/跨包/PCR 跳转用例分别通过。35 项合并检查曾出现 1 个页面启动等待超时和 1 个未配置 Qt 资源测试 skip；新增启动失败现场保留后，该启动用例单独复核通过，未把此批写成全绿。当前 Tauri 网页行为有真实引擎浏览器证据；上一次原生 Tauri 本地编译只覆盖早期窗口框架快照，尚需最终重新封装。无托管 CI。


第 07–11 项追加合并回归：`si-ordered-steps07-11-combined.log` 中 40 项全部通过、无 skip，覆盖包读取、Timing、原有 transport 口径、桥接静态资源及 13 个经典 UI 用例。此批不含未配置的 Qt portable resource suite；Qt 源组件和完整应用仍使用前述独立证据。

## 服务、EPG 与应用追查检查点（2026-10-26，步骤 12）

两端新增独立 Services / EPG 窗口，按实际 SDT 的 ONID/TSID/SID 选择服务。
Service、ES、EPG、Applications 使用同一 query_service 响应；双击/Enter 打开
确切 section，ES 定位到真实字节偏移对应的 stream，关闭后恢复服务页。
多个实际 SDT 网络身份或 PAT 映射冲突时不关联 PMT；共享 AIT PID 保留非独占来源。
自动标准模式不隐含 DVB 应用解释，明确提示需要 DVB 上下文。
事件为截止点内已观测 EIT，不能当作完整节目单或实时播出保证。

本地验证：36 项引擎/浏览器检查通过（服务身份、错误上下文、原有 AIT carriage
回归、EPG→ES→AIT→返回与共享 PID）；完整 Qt 离屏显示真实 Hotbird 服务、
PMT 组件及准确结构路径，4 项观察通过且无 QML 错误。
证据位于原始仓库 ignored artifacts/si-service-final.log、si-service-qt-runtime.log。
原生鼠标与 DPI 验收仍归步骤 17，不以离屏结果替代。

## DSM-CC 对象内容检查点（2026-10-26，步骤 13 内容部分）

两端独立 DSM-CC / OC Files 窗口提供 Modules、OC Files、OC Hierarchy、
BIOP List；DSI 的 ObjectLocation 可以进入当前同 PID/download 的模块与对象。
模块保留宣告代次、版本、尺寸、缺块、源 section 和 SHA-256；完整模块才提供内容。
BIOP 损坏保留已验证前缀，引用目标为部分 BIOP 时不标已解析；重复键、版本不符、
跨 carousel、缺块、未知 profile 均保留原因。目录循环仅针对当前导航路径拦截。
库存按已验证模块对象提供，名称尚未解成路径时明确采用 object key。

内容支持按 4096 字节分页的 hex、严格 UTF-8 文本、只读 Class Info；Class 不加载、
不执行，属性正文/字节码验证不在当前解释范围。Class 字符串上限 1000 且保留总数，
fields/methods 4096 超限明确报错；模块 16 MiB、快照工作 64 MiB、对象 4096 有界。
未压缩模块可解释；压缩模块仍保留原字节与无法解析状态，不宣称展开支持。
导出接入步骤 16，真实桌面与 DPI 验收归步骤 17。

本地验证：45 项引擎/浏览器检查通过；完整 Qt 离屏从实际重建输入的 DSI 进入
SRG、目录、M12 八个 Class，再进入 M13 configuration.txt。八个内部类名分别核对，
配置为 49,528 字节、SHA-256 4050ad6c70ed0686b18f275421b21fdfbec2052aea8efd56f355f912110e03bb。
浏览器相同窗口链通过，并逐页拼回配置全文件后核对同一 SHA-256。
输入为参考工程的完整捕获重建输入，不把它当作原始短捕获的完整对象证据。
ignored 证据：si-carousel-final.log、si-carousel-reference-web.log、
si-carousel-reference-qt-runtime.log、si-frame-20261026/carousel-reference.json。

## Teletext 页面检查点（2026-10-26，步骤 14）

两端 Teletext 窗口读取当前分析身份中的真实 TS→PES→44-byte Teletext unit，
PID 入口采用明确 DVB PMT teletext_descriptor 声明或用户显式 PID。
页号/子页、Previous/Next capture、分段扫描、字符选择及来源原包跳转可用，
关闭原包后返回同一页、捕获和字符。捕获不会被当作直播时钟。

40×24 显示保留原始页头文字、8 色、已支持 Latin group 0000 字符、马赛克、
分离图形、双高上下半格、conceal/reveal 和手动 flash phase。C4 清屏后的未收行
为已知显示空白，source_present=false，不伪造接收行或来源。断流清除页上下文，
保留之前已验证的捕获；奇偶校验/未知字符集/扩展/boxing 均有明确限制。
row 0 前 8 列是元数据空白，页号显示在控件中；X/28、M/29 等增强未宣称完整支持。
默认扫描 65,536 包，上限 262,144；PES 16 MiB/4096、unit 32768、页缓存 64、
捕获 128 有界，旧捕获和页驱逐计数可查。范围边界不借用不完整 PES。

本地：29 项 Teletext/服务/对象引擎与浏览器检查通过；完整 Qt 离屏的字符、颜色、
conceal 与捕获切换通过。实际 test-012 输入 SHA-256
2e3a280bb6d2da71791ba18390e6d649296688782ad0a80f0dfefa8eb8c4d50b，
显式 PID 1068，page 889 的 9 个字幕事件/18 行与独立 SRT 在引擎、浏览器显示字符、
完整 Qt 页模型分别一致。该样本 PAT 保留位无效，仍仅作显式 PID 接收证据，
不算 PSI 自动发现通过。检查了 Qt 的实际离屏截图，双高只作纵向缩放。
证据：si-teletext-final.log、si-teletext-subtitle-oracle.log、
si-teletext-reference-web.log、si-teletext-reference-qt-runtime.log。
真实桌面鼠标、DPI 与设备输出仍归步骤 17。

## PES、ES 与真实媒体检查点（2026-10-27，步骤 15）

两端独立 PES / ES / Media 窗口使用同一 query_pes / decode_media / audio_control。
PES 列表稳定选择、分页、PTS/DTS、PES/ES 字节分页与确切 TS 字节跳转可用；
复用已有 Packet Explorer 时会重新定位包和字节，不留在旧包。解码从用户明确
选中的 PES index 开始，断流或加扰不拼成连续 ES，不从私有 stream_type 猜 codec。
自动 codec 来自 context-aware PMT；显式输入格式与自动解释分别标明。

视频为最多 16 个真实 PNG 解码帧，拟合 320×180，预览按派生 10 fps 播放，
不宣称原始帧节奏或 A/V 同步。音频为最多 3 秒、mono / 48000 Hz / s16le 的
实际解码 PCM 和 512 个峰值范围；原始采样率/声道与解码输出分别说明。
Windows 输出仅操作本进程的缓冲句柄；播放、暂停、继续、停止、关闭和换源受
同一 preview token 约束。设备 API 排队不作为物理可听验收。

外部 FFmpeg 9.0.2 Windows x64 工具固定 SHA-256
3256173f3f8bffd7df12227c68adf68025edb1832273a9530688a7bb1ed8edec。
工具为可选外部依赖，不自动下载、不随程序分发；GPL build 的安装包分发审阅
尚未纳入当前交付。配置由 SHOWPSISI_FFMPEG 或本项目 .deps/ffmpeg 路径指定。
执行前核对哈希；无 shell/网络输入。独立 Job 限制单进程、384 MiB、8 秒和
4 MiB 输出；输入上限 16 MiB、256 PES、64 个连续段。取消通过独立请求注册表
仅设置匹配 revision/request_token 的标志，不访问 Engine/TSDuck 状态，旧取消
不能命中分析或另一媒体请求；接受取消后不发布成功预览。

本地：媒体/PES 与分析取消共 29 项通过；两个浏览器整链检查通过；完整 Qt 的
视频、原包定位、播放结束、PCM、静音设备输出和关闭释放通过且无 QML 错误。
实际完整 I 帧参考的派生 remux 输入也通过完整 Qt：恢复 ES 为 25,756 字节，
SHA-256 dc60e1a17c0cee0f5702e23ed171e70e5bc2d4543ee2bd179185e84eb9cedc64，
真实 PNG 已加载，解码子进程退出。该证据仅对应已接受的单 I 帧与派生 remux，
不把原始 test-074 全文件当作干净视频或原始时序证据。
证据：si-media-cancellation.log、si-media-web.log、si-media-qt-runtime.log、
si-media-audio-qt-runtime.log、si-media-reference-qt-runtime.log。
当前仅实测 MPEG-2 video / MPEG audio；可选解码格式不等于全部 application-tested。
真实桌面/DPI/最终退出与未支持平台边界仍由步骤 17 收口。


### 2026-10-27 步骤 16：保存、复制和设置

两端 File→Save / Ctrl+S 使用同一 output-model；冻结活动窗口和选中身份后再选择
输出类型与路径。section、188 字节 TS 包/原封装、单个完整 PES/对应 ES、完整
模块、BIOP 文件或对象，以及当前解码预览 PNG/mono 48000 Hz s16le WAV 均由
引擎重新核对 revision/来源/范围/模块 epoch/preview_token。JSON 报告明确仅为
分析摘要和 coverage，不伪称完整分页集合。高级 SDT 改名和 SI-only 重组 TS/BIN
原功能保留，不能当作原始媒体 TS。Copy 保留字段列名、bits 单位、值和说明；
hex 复制明确显示层与分页可能不完整。系统剪贴板失败时浏览器选中可复制原文。

export_asset 限于有界资源；临时文件写入、关闭后使用同卷原子无覆盖发布，输出
与 manifest 任一冲突均拒绝；不支持 hard-link 的文件系统显式失败。源变更和
过期身份拒绝；残缺模块无输出。取消路径选择不发送写请求。两端 native close
的 active-export 保护涵盖新方法。没有实现打印，禁用原因指向保存入口。
配置 OK 验证并在各端独立保存偏好；Cancel 恢复打开前值；Start 提交有效选项。
扫描选项只作用下一次分析，重启不恢复旧分析为当前结果。外部 decoder 仍按
步骤 15 的固定 hash 和显式本地路径配置，不自动获取或分发。

本地 6 项引擎输出检查通过：含 Unicode 路径、原字节/对象全文/空文件、PNG/WAV
hash、缺块、旧 epoch/token/revision、源变更、已存在 output/manifest、不可用
目录及临时文件清理。浏览器 3 条链通过（设置取消/提交、真实保存与冲突、既有
视频/静音音频关闭）；完整 Qt 7 项检查通过（设置恢复/持久化、section/report、
PES/ES、当前 PNG 选项与取消无输出、无 QML 错误）。Qt 此处为离屏；原生文件
对话框、鼠标与最终退出属于 17。证据 si-output-engine.log、si-output-web2.log、
si-output-qt-runtime.log；没有启动或查询 CI。


### 2026-10-27 步骤 17：最终本地构建与原生收尾

Qt 与 Tauri 均以本次工作树当前源码构建。Tauri 的 36 个输入文件逐一核对 SHA-256
后复制到已接受的 Low 构建目录，cargo --locked --offline 成功；未运行托管 CI。
最后修复两端原生窗口标题跟随活动文档、保存页的可读来源说明和经典样式；
经典模式成功分析后均默认选中有效 PAT，避免 Qt/PAT 与 Tauri/SDT 的起始差异；
从 Open 文件入口进入配置也先保存旧值，Cancel 与菜单进入配置的恢复行为一致。
原生 200% 检查发现 Qt 初始 1440×900 与固定 minimum 超出逻辑屏幕；已改为
依据 Screen 限制初始/最小尺寸。1920×1080 主屏上 QT_SCALE_FACTOR=2 的实际
窗口为 920×480 逻辑像素，屏幕为 960×540，菜单、状态和关闭按钮可达。
Web classic #app 的旧移动布局 min-height 也被限定覆盖，避免缩小逻辑视口时
状态栏落出屏幕；配置栏可滚动。高级工作区原样保留其独立布局。

Windows Computer Use 的实际操作分别验证两端：树文字单击不折叠、双击展开表
列表、加号单击展开 PAT 内部 Program 树；字段列边缘实际拖动且竖线保持对齐；
Windows 原生保存路径选择器打开、Escape 取消后保留原位置与内容且没有输出。
Qt 与 Tauri 都通过正常关闭窗口退出，核对各自已记录的 UI、core、WebView 主
进程 PID 已不存在；没有靠强杀来声称正常退出。媒体解码 Job / PCM 的停止、
取消及窗口关闭释放证据见 15 与最终运行检查，不把设备排队等同于物理可听验收。

最终本地检查：41 项 PES/媒体、Teletext、Carousel、导出引擎检查；20 条经典
浏览器整链，另加 1 条三档缩小逻辑视口检查；4 条高级编辑导出/拓扑/历史/DVB-I
链；52 个 Qt 实际组件用例（60 PASS 含生命周期）；完整 Qt 的 output、documents、
packets、video、audio 五条应用运行链全部通过。此前固定真实字幕、BIOP Class/
配置、单完整 MPEG-2 I 帧的字节与 hash 证据保留，不改写原样本完整性结论。

缩放边界：Qt 100/150/200 进程缩放均有离屏功能检查，100 与 200 另外做了真实
桌面检查；Tauri 当前 Windows 系统 DPI 的真实操作已通过，100/150/200 等效缩小
逻辑视口在真实 Chromium 检查菜单、字段、导航、状态和保存控件可达。WebView2
的 force-device-scale-factor 尝试没有观察到实际缩放变化，因此不把它计作 Tauri
原生 200% 证据。没有更改用户 Windows 显示设置；多显示器系统 DPI 切换、不同
宿主字体渲染和主观像素级 1:1 仍未实机验收。打印、压缩模块、Teletext 增强集及
原始 A/V 同步等既有明确 unsupported/partial 范围保留，不以完成 UI 宣称全协议支持。

证据位于主工作区 ignored artifacts/si-frame-20261026：si-final-qt-build4.log、
si-final-tauri-build5.log、tauri-source-manifest.json、si-final-engine.log、
si-final-classic-web2.log、si-final-browser-scales.log、si-final-advanced-web.log、
si-final-components.log、si-final-runtime.json 和 native-final.json。最终源码提交、
产物 hash 与预览 PID 在 delivery-final.json 记录。原生最终预览使用独立设置。
