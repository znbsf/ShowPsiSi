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
