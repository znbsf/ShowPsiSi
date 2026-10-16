# ShowPsiSi 需求与实现审计

审计日期：2026-10-16 UTC（香港时间 2026-10-17）。
审计基线：`a79ce16ff04e7f418c366db247eb6afce11b495a`。

## 结论与范围

按仓库自行声明的范围，项目有共享 C++/TSDuck 引擎、两个前端、JSONL/MCP 接口、证据查询、配置扩展及 SDT 改名/信令导出的原型实现。不能据此判定完整产品需求已经满足，也不能把既有 Windows 验证报告当成本次云端复测结果。

本次取得的需求依据是 `README.md`、`docs/STATUS.md`、`docs/ARCHITECTURE.md` 和 `api/tools.json`；未取得更早的完整原始需求清单。以下“满足”仅表示代码中存在相应实现，不等于用户已经验收或本次运行通过。审计只读取云端源码，没有访问用户电脑、操作设备、安装依赖或执行 Windows 构建。本文件所引行号对应以上基线，后续修复可能改变行号。

## 初次审计的验证范围（修复前）

初次审计实际执行：

- 9 个 Python 脚本/测试文件通过 Python AST 语法解析。
- `api/tools.json` 能被 JSON 解析器读取，包含 7 个工具。
- 确认此克隆没有 `build/bin/showpsisi-core.exe` 和 `samples/generated/lab.ts`；在 `/usr/include` 与 `/usr/local/include` 的有限搜索未发现 TSDuck 头文件目录。
- 检查原生核心、工具 schema、Python 客户端/MCP、现有集成测试、合成样流生成器与项目文档。

未执行：原生编译、10 项引擎集成测试、真实样流分析、Qt/Tauri 交互、性能对比、导出接收机播放。现有 `docs/STATUS.md` 中的通过记录属于历史报告，本次未独立复现。Python 语法通过也不证明原生或 MCP 功能可运行。

## 修复后独立复核（最终复跑：2026-10-16 20:14 UTC）

在初次审计之后，同一云端工作区已完成 Linux 核心构建和样流准备。本审计重新阅读当前核心/测试差异，并实际重跑 `tests/test_engine.py`：先 17 项全部通过；追加扩展冲突和 UTF-8 边界修复后再次独立复跑，19 项全部通过，没有 skipped，包含真实法国样流、MCP、中文改名、导出回读、失败分析、PMT PID 切换、配置生命周期、竞争导出及 192/204 字节封装。

运行时必须设置本地依赖路径：

```sh
LD_LIBRARY_PATH="$PWD/.deps/tsduck/usr/lib:$PWD/.deps/tsduck/usr/lib/x86_64-linux-gnu" python tests/test_engine.py
```

不设置该环境变量的首次复跑因为缺少 `libsrt.so.1.5` 加载路径而在全部测试 setup 阶段失败；补充路径后通过。这是启动环境依赖，不应把第一次失败隐藏，也不应把它解释为 17 个功能回归。

| 发现 | 当前修复状态 | 证据和剩余边界 |
| --- | --- | --- |
| F1 失败分析污染来源 | 已修复主要路径，回归通过 | 新请求先清空会话并递增 revision；仅 complete 会话允许编辑/导出。missing/tiny/invalid framing 三类失败均测试通过；读盘中途故障注入仍未执行 |
| F2 PMT 错误关联 | 已修复，回归通过 | PAT 按 TSID/SID 索引，PMT 按 PID/SID 索引，只有 PAT 指向的 PMT 能加入服务；切换期间缺 PMT 不回用旧值 |
| F3 扩展验证/生命周期 | 已修复所复现问题，回归通过 | 新配置仅作用于下一次扫描；增加类型/范围、保留字段、重复字段和重叠 PDS/table/tag scope 检查；错误配置不改变待使用的有效配置 |
| F4 覆盖竞态/关闭检查 | 主要路径已修复，竞争测试通过 | 新 ExportFile 使用排他创建并检查 fclose，异常清理本次创建的文件；尚未验证 Windows CRT、磁盘满、关闭失败或进程崩溃。两个最终文件仍非单一原子提交，崩溃可能留下不完整产物 |
| F5 查询时间作用域 | 已添加明确 scope 元数据 | 全程 history/density/counters/demux 仍保留；客户端需按 scope 正确展示，不应当作截面统计 |
| F6 UTF-8 长度契约 | 已明确契约并通过边界回归 | name schema 描述及 x-maxUtf8Bytes 明示 180 字节限制；180 ASCII/60 中文字符导出回读通过，181 ASCII/61 中文/46 emoji 被拒绝。通用 JSON Schema 验证器不会执行自定义 x-maxUtf8Bytes，客户端仍须遵循描述/后端检查 |

### 独立复核新增的可复现扩展问题

修改 demo 配置中字段 `logical_channel_number` 的 name 为 `source_id`，加载被接受，分析后服务的 `source_id` 变成整数 20；将该返回值用于 inspect 会得到 `Wrong type: id`。原因是私有字段结果可覆盖内置身份/来源字段，`s.update(decoded)` 没有保护保留键。应拒绝 source_id、id、ts_id、onid 等结构性字段及事件对应键，而不是让配置重写证据关联。

此外，追加相同 `(PDS, table_id, tag)` 的 descriptor 配置、把 LCN 改为 offset 2/u8，同样被接受，LCN 静默变为 1。与架构文档的“配置之间冲突必须报告”不符。建议拒绝重叠 scope、重复字段，并验证默认 demo 配置与外部加载配置使用相同规则。这两项均为实际运行复现，随后已修复并加入 `test_extension_rejects_reserved_fields_and_scope_conflicts`，最终独立重跑通过。保留本段以记录审计如何发现问题及其证据。默认 demo 文件仍由构造器直接读取，未复用 load_extension 校验；它目前是随源码提供的可信配置，若将它开放为用户配置入口，应统一验证。

新增 CAT/NIT/BAT/TDT/TOT 结构化解码的集成用例已通过，但尚不足以宣称这些表所有规范语义/错误路径完整覆盖。此处仍未执行 Qt/Tauri 交互、Windows 打包、接收机播放或性能对比。

## 原始需求覆盖对照（修复前基线）

| 仓库声明的要求 | 代码依据 | 审计判断 |
| --- | --- | --- |
| 两种 UI 共用 C++/TSDuck 核心 | `CMakeLists.txt`、`core/main.cpp`、架构文档 | 结构存在；本次未运行 UI |
| 188/192/204 字节对齐本地 TS、增量进度 | `core/main.cpp:213–235` | 实现存在；尚需三种封装与截断输入回归 |
| section 原始证据、次数、位置、版本历史、密度 | `core/main.cpp:143–175,185–211,237–242` | 实现存在；历史查询有全局/截面字段混杂，见 F5 |
| DVB 服务、PAT/PMT、EIT 关联 | `core/main.cpp:108–140,193–203` | 实现存在；PMT 关联有实质缺陷，见 F2 |
| 错误数据保留并排除派生服务 | `core/main.cpp:68–69,143–162,47–58` | CRC/已实现结构错误路径存在；不等于完整规范校验 |
| PDS/table/tag 私有配置、排序分组 | `core/main.cpp:71–106,202–205,305–309` | 存在；配置生命周期/验证不完整，见 F3 |
| 单 section 实际 SDT 改名、预览令牌、独立导出 | `core/main.cpp:244–282` | 存在；失败分析状态与输出安全需修复，见 F1/F4 |
| GUI/CLI/MCP 共用 schema 和验证 | `api/tools.json`、`core/main.cpp:284–310`、`scripts/mcp_server.py` | 共用入口存在；字符长度契约不一致，见 F6 |
| 原型运行和资源比较 | `docs/BENCHMARK.md`、`docs/STATUS.md` | 有历史报告；本次不能确认当前云端/新机器可复现 |

## 原始发现和回归建议（修复前基线，最新状态见上表）

### F1 · P1：失败的分析请求会污染来源状态，允许旧证据以新路径导出

证据：`core/main.cpp:214–217` 在打开/验证文件前直接修改成员 `source`；`totalBytes` 也在最小长度检查前修改。只有这些检查通过之后才清空 records、preview 和递增 revision。`exportData` 在 `258,262,280` 使用既存 records/token 和当前 source。

可直接从控制流确认的失败路径：先成功分析 A 并创建预览，然后分析不存在的 B（或小于 188 字节的 B）。请求报错，但 A 的 records、revision 和 preview 仍然存在，source 已变为 B；之后查询显示混合状态，导出 manifest 会把 A 的内容标为 B 的来源，旧预览也仍可使用。这破坏“来源可追溯”而不只是界面显示。

建议：分析使用临时 session，成功后原子替换；或在开始新分析时一致地清空全部状态并使旧预览失效。两种策略均应明确定义失败后可否继续查询旧会话。更晚的扫描异常还可能留下不完整 records，应禁止将失败/未完成会话当成成功分析导出。

回归：A → preview → 不存在 B；A → 长度不足 B；A → 无同步 B；扫描中异常。断言 source/records/revision/preview 的一致性，以及失败会话的 export 行为。

### F2 · P1：PMT 仅按 service_id 关联，未检查 PAT 指定的 PMT PID

证据：`core/main.cpp:193–203` 将 PAT 放入 `pmts[service_id]`，却将所有所选 PMT 放入 `components[r.ext]`；关联时只按 sid 查 components。PMT 所在 PID 未参与匹配。`handleSection` 在 `179–182` 只添加发现的 PMT PID，没有移除旧 PID；`latest` 也会保留没有新观测的旧 PID section。

如果 PAT 将某节目从 PMT PID A 切换到 B，旧 A 和新 B 都可留在 selected 中，后写入 components 的那个胜出，由字符串 key 迭代顺序决定，而不是由最新 PAT 的引用决定。结果可能是界面显示 PMT PID B，但 components/PCR/ES 来自 A；没有匹配的当前 PMT 时也可能继续展示旧组件。多个 TS 的重复 service_id 还会被同一个 map 混合。

建议：先建立当前完整 PAT 的上下文，再仅接收 `(PAT 引用 PID, program_number)` 匹配的 PMT；服务关联也应检查 transport_stream_id。没有匹配项就显式标记缺失，而非退回旧 PMT。

回归：同 sid 在两个 PID 上给出不同 PCR/ES，PAT 先引用 A 后引用 B，分别查询切换前、切换后但 B 尚未收到、B 收齐后三个截面；再交换 PID 数值，确保结果与 map 顺序无关。

### F3 · P2：扩展加载后混用旧解码与新组织规则，且缺乏完整配置验证

证据：`core/main.cpp:305–309` 只做部分结构检查后替换 extension，返回 `requires_rescan=true`，但不失效 records/pending/revision；`state` 在 `186,202–205` 立即使用新的 extension ID 和组织规则，而 records 中描述符/字段仍是旧配置解码结果。`descriptors` 在 `90–101` 会使用加载时未保证存在且类型正确的 tag/name/fields 等字段。

影响：遵循文档立即重新分析的客户端可避开混合状态，但 API 没有保证该前置条件。格式不完整的配置也可能加载成功，到后续分析才抛异常。例如包含合法 pds/table_ids/payload_bytes 和空 fields、却缺失 tag 的 descriptor 能通过加载检查，第一次处理描述符时才在 `spec.at("tag")` 失败。

建议：完整验证 root/descriptors/字段类型、数值范围、名称、PID、排序分组字段以及冲突；拒绝非法配置并保留旧配置。成功变更后要求重新分析并禁止旧会话预览/导出，或将解码配置明确绑定到既存会话。

回归：省略 tag/name、错误类型、负 offset、越界 PID、重复冲突定义；加载后不 rescan 即 query/preview/export；校验错误不得改变会话状态。

### F4 · P2：导出的“绝不覆盖”保证存在竞态，文件与 manifest 也非事务提交

证据：`core/main.cpp:260–269` 先 `exists` 再默认模式打开 `ofstream`，两步之间别的进程可以创建目标，之后打开会截断它。`279–282` 写好数据后才创建 manifest，且 manifest 流未显式 close/核查关闭结果就返回成功。

影响：单进程普通路径有既存文件保护，但无法支持 API 中无条件的 “Never overwrite existing output”。manifest 失败会留下不完整的一对产物；重试又被已有数据文件阻止。缓冲刷新/关闭错误也可能迟于成功返回。

建议：使用平台排他创建，不跟随不可信重定向；数据和 manifest 均完成并检查刷新/关闭后才报告成功。定义失败时只清理本次创建的产物，或返回明确的部分输出状态。不要删除/替换他人文件。

回归：两个进程竞争同路径、manifest 已存在、manifest 写入失败、数据写入失败、结束刷新失败；确认原文件不变，且失败不被报告为完整成功。

### F5 · P2：历史 query 混合截面数据和全文件数据，字段未充分标注

证据：`core/main.cpp:186–191` 在 `query(at_packet)` 下过滤 tables/diagnostics，但 observations、crc_errors、history、packets 和 complete 仍取整个分析值；`206–210` 的 density 与 demux 也不受 at 限制。返回对象只有 selected_packet，没有对这些字段逐项标明 scope。

影响：请求较早包位置时，调用方会同时得到“当时的服务”和“未来才发生的错误/历史/密度”。如果这些指标本来 intended 为全文件概览，它们仍应在 API 中清楚命名/分层，避免 AI 或 UI 将其解读为截面事实。

建议：分离 `capture_summary` 与 `snapshot`，或者按 at 截断可截断统计；不可按包定位的 demux 指标显式标记为全程聚合。

回归：在目标截面之后注入 CRC 错误和 SDT 新版本，断言 query 返回的每类字段具有明确且一致的时间作用域。

### F6 · P2：服务名长度 schema 与实现的 UTF-8 字节限制不一致

证据：`api/tools.json` 声明 name 为 `minLength:1,maxLength:180`；`core/main.cpp:284–297` 未实现字符串长度 schema 验证，而 `248` 以 `std::string::size()` 强制最多 180 UTF-8 字节。JSON Schema 长度是字符数，不是 UTF-8 字节数。

本次轻量检查：61 个“中”是 61 个字符、183 字节，符合发布 schema 却会被实现拒绝。已有 MCP 中文测试只使用短名称，不能覆盖该边界。

建议：明确广播编码/descriptor 空间的字节限制，schema 与错误说明同时声明；按 Unicode 字符验证 schema，再单独执行编码后字节预算检查，不把两种限制混为一个。还需验证更长 provider name 共同占用 descriptor 空间的行为。

回归：空名称、180/181 个 ASCII 字符、60/61 个中文字符、emoji、组合字符、接近 descriptor 总容量时的 provider/name 组合。

## 明确尚未实现的产品能力（不是隐瞒的回归）

README 已明确排除 UDP/SRT/调谐器输入、实时回压/取消、大文件磁盘索引、完整广播 SPEC 校验、任意描述符编辑、节目增删联动、媒体/PCR/原始节奏 remux、私有 DLL 自动发现、真实 LLM 接入、完整 EPG 时间网格和多语言 UI。Linux/macOS、安装包及接收机播放验收也未完成。若这些属于用户最终目标，本项目当前只能算覆盖其中的原型子集。

EIT 分段语义另有明确限制，不能把当前 EIT 列表当成完整 EPG 验收。当前导出仅为信令快照，缺失媒体/PCR，因此“保留媒体引用”不能替代可播放或真正黑色视频流测试。

## 建议验收顺序

1. F1/F2 和对应回归已完成；继续覆盖扫描中途 I/O 故障及更复杂 TS/PID 切换。
2. F3–F6 已修复所复现问题或明确语义；继续做磁盘满、关闭失败、进程崩溃和 Windows 排他创建验证。
3. 在受支持 Windows 环境重跑当前 19 项测试，保留结果与构建/样流哈希；分别测试 188、192、204 封装、current/next、版本回绕、多 section 和连续性错误。
4. 再做两个 UI 的真实交互与同条件资源对比；云端网页预览或截图不能替代原生 Qt/WebView2 验收。
5. 对照用户完整原始需求逐项决定哪些是当前里程碑、哪些列入后续；由用户确认视觉偏好和真实接收机行为。

本审计只修改此文档；实现修复由同一任务的其他工作完成。修复后的通过范围仅限上文实际执行的 19 项引擎测试，不能外推为全部需求完成。
