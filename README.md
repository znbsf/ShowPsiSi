# ShowPsiSi

两个可运行的 Windows 原型：**Qt Quick 6.7.3** 与 **Tauri 2 / WebView2**，共用同一个 **C++ / TSDuck 3.39-3956** 进程。现在用于验证架构、交互和资源开销，还不是完整的广播标准分析器。

## 直接运行

首次克隆请先完成下方“构建与测试”中的依赖准备、编译和样流生成，然后在本项目 PowerShell 中运行。也可以双击 `Launch Qt.cmd` / `Launch Tauri.cmd`，默认打开含版本变化和故障的合成样流。

```powershell
.\scripts\run.ps1 -UI qt -Auto
.\scripts\run.ps1 -UI tauri -Auto
# 使用 TSDuck 的真实法国地面电视录制流：
.\scripts\run.ps1 -UI qt -Sample samples\real\tnt-uhf22-2019.ts -Auto
.\scripts\run.ps1 -UI tauri -Sample samples\real\tnt-uhf22-2019.ts -Auto
```

界面打开后可输入本机文件路径或使用 Browse。分别启动可避免同时运行影响性能判断。所有处理在本机完成。

SDK 和构建产物位于工作区的 `.deps/`、`build/` 和 `ui/tauri/src-tauri/target/`，不包含在 Git 仓库中。此原型需要本机安装 TSDuck 开发包；尚未制作面向其他电脑的安装包。

## 已实现

- 通过 TSDuck `SectionDemux` 增量解析 188/192/204 字节文件；PAT 发现 PMT PID，另扫描常见 DVB SI PID 与 ATSC PSIP PID。
- section 的原始字节、PID、版本、current/next、包位置、重复次数、80 桶密度，以及 SDT 版本历史。
- DVB 实际 TS 的服务列表，PAT/PMT 关联，EIT 事件列表；标准 service / short-event 描述符由 TSDuck 解码。
- CRC、部分结构长度错误和 demux 连续性统计。无效数据保留，正常节目组织排除它们。
- 描述符字段树与十六进制；PDS + table-id 限定的私有配置解码；可配置频道排序和分组。
- 单 section 实际 SDT 的服务改名预览：TSDuck 编码、版本递增、CRC 重算；导出到新路径。
- SI-only `.ts`（可配置 null 包和重复次数）或 `.bin` 原始 section 文件，均附 PID、来源和修改记录 manifest。
- JSONL CLI 与 MCP stdio 接口。AI 调用的是真实后端功能，与 GUI 共用 schema 和验证规则。

## 看图与复现证据

以下截图来自两个实际运行的原型，使用同一份 TSDuck 官方真实样流。

**Qt Quick**

![Qt Quick 原型](docs/images/qt-real.png)

**Tauri + Web**

![Tauri Web 原型](docs/images/tauri-real.png)

以下 `artifacts/` 文件是本地验证产物，不包含在仓库中，可使用下面的脚本重新生成：

- `artifacts/qt-quick.png`、`artifacts/tauri-web.png`：运行中的两个原型。
- `artifacts/*-issues.png`、`artifacts/*-edit.png`：错误检查和编辑交互。
- `artifacts/engine-tests.log`：后端、导出回读和 MCP 集成测试。
- `artifacts/qt-ui-test.json`、`artifacts/tauri-ui-test.json`：实际控件交互结果。
- [性能对比](docs/BENCHMARK.md)、[扩展和 AI 接口设计](docs/ARCHITECTURE.md)、[当前状态](docs/STATUS.md)。

## 构建与测试

当前 Windows 路线：PowerShell 7、VS 2019 Build Tools / MSVC 14.29、Windows SDK、TSDuck 开发包、CMake/Ninja、Python 3。先安装这些前置依赖并按实际位置调整 `scripts/env.ps1`；`setup-deps.ps1` 在项目内准备 Qt 6.7.3、Rust 1.99.1 和 Python 虚拟环境。详见 [依赖说明](docs/DEPENDENCIES.md)。环境脚本只设置当前进程环境。

```powershell
.\scripts\setup-deps.ps1
.\scripts\build.ps1
.\.deps\py\Scripts\python.exe scripts\make_fixture.py
.\.deps\py\Scripts\python.exe tests\test_engine.py
.\.deps\py\Scripts\python.exe scripts\qt_capture.py
.\.deps\py\Scripts\python.exe scripts\tauri_capture.py
.\.deps\py\Scripts\python.exe scripts\benchmark.py
```

浏览器 UI 检查使用 Playwright，仅连接测试进程自己的 WebView2 CDP 端口。正式性能测试关闭 CDP。Qt 检查通过自己窗口内的鼠标事件操作实际控件。自动检查完成后清理并确认自己启动的进程树退出。

依赖定位脚本目前按本机路径配置；新机器需调整。Tauri 的 Cargo.lock 已锁定版本；C++ 使用 vendored nlohmann/json 3.11.3。Linux/macOS 尚未构建或验证，现阶段不能称为跨平台完成。

## 样流

`scripts/make_fixture.py` 可重复生成含六个服务、SDT v1/v2/v3、私有描述符、2 个 CRC 错误和 1 个长度错误的信令流。无音视频/PCR，不是可播放黑画面。

真实样流来自 [TSDuck 官方流仓库](https://tsduck.io/streams/?stream=france-dttv)，包含 2019 年法国地面电视网络的 UHF22 和 UHF33 录制。下载来源、大小、SHA-256 及随附参考报告保存在 `samples/real/`。二进制样流不纳入源码分发。

## 本轮边界

暂未实现 UDP/SRT/调谐器输入、实时流回压/取消、大文件磁盘索引、完整 SPEC 检查、任意描述符编辑、节目增删联动、保留 PCR/码率/原始位置的完整 remux、私有 DLL 自动发现、实际 LLM 模型接入、完善的 EPG 时间网格和多语言 UI。

时间查询表示“该包位置之前完整接收到的、最新观察到的 current section 状态”。它不能证明节目在未观测区间仍有效。跨 section 的 PAT/PMT/SDT 不混版本，未收齐时不生成其派生服务；EIT 的分段语义仍需后续专门处理。

快照导出保留 PMT 中的媒体引用，但不带媒体/PCR；用于“信令存在、媒体缺失”的测试。要测试真正编码后的黑色视频、原始播发节奏或接收机的全部行为，需要另行构造相应媒体和时钟。`.bin` 本身没有 PID 或时间，必须配合 manifest。

未知私有字段作为原始字节保留，不推断其语义。当前“valid”指已实施的校验通过，不等于完全符合全部广播规范。
