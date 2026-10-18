# Qt / Web 编辑、导出与快照对比交接 — 2026-10-18

结论：编辑、导出、快照对比尚未完全对齐。测试使用真实 Windows Qt 和 Tauri/WebView2 窗口，通过鼠标、键盘和原生保存对话框操作；诊断接口用于状态回读与截图。没有用截图或模拟数据替代功能验证。

## 基线与范围

- main：88506ba3e78e5dc079d83961f3d77334e8ffd1a4；本地源码干净。
- 运行二进制哈希与最终验证清单一致；对应源码 tree：1b10d71368917e4beaec04c2461a6747015a49a9。详见本机 artifacts/operation-parity-audit/identity.json。
- 使用项目合成样本 samples/generated/lab.ts；Qt 为 DVB，上下文自动检测的 Web 为 Auto。使用独立诊断会话，不操作用户原来的试用窗口。
- 审计导出仅写入本机忽略目录 artifacts/operation-parity-audit/ 的新文件；审计没有修改功能代码。本次交接提交仅包含文档，以下缺口仍未修复。

## 确认的缺口

| 项目 | Qt | Web | 影响与证据 |
|---|---|---|---|
| 导出格式 | TS 和 BIN 均实测成功 | 保存对话框只有 TS；请求固定 format=ts | Web 缺少原始 section BIN 导出；app.js:1656，Main.qml:3893 |
| 编辑目标选择 | 编辑窗口只有名称框，目标由外部服务选择决定 | 编辑窗口可切换服务；World News → Culture HD 已实测 | Qt 需关闭编辑窗口回到列表切换；Main.qml:730、3846，app.js:1587 |
| 对比后恢复原选择 | World News(101) → 查看 Sports(103) 的对比 → 返回 Services，变为 Sports(103) | 同样流程返回 World News(101) | Qt 实际丢失原选择；qt-before-compare.json、qt-after-compare.json；Web 对应文件。Main.qml:67 的 defaultInspect 取第一项，Web app.js:911 保存/恢复工作区 |
| 应用对比时刻 | Use snapshot 实测把工作区切到 59008 包，进入 Services，之后可生成历史编辑预览 | 无对应按钮；说明文字却提到 Use snapshot | Web 缺少对比结果直接应用为工作区快照的入口；可另走时间线，不代表底层不支持快照。qt-use-snapshot.json；Main.qml:3057，app.js:1339 |
| 同一变更的多份来源 | 对比 A/B 只打开 evidence[0] | 分别提供 SDT、PAT、PMT；实际打开 Sports 的 A 侧 SDT 和 PMT | Qt 对比入口无法逐份浏览关联来源；不等于其它页面不能查看 PAT/PMT。Main.qml:600，app.js:996；web-compare-pmt.json |
| A/B 范围操作 | 输入包号 / Use current | 输入包号、历史下拉、Swap A/B | 快捷操作未统一；这两个 Web 控件的存在已核对，本轮未逐项执行所有历史预设/交换组合 |

次要差异：Web 预览明确显示版本 3 → 4，Qt 只显示名称变化；Qt 成功保存后保留编辑窗口和预览，Web 关闭编辑窗口。

## 实际通过的项目

1. 两端实际把 Sports UHD 改为 Parity Audit 2026，生成预览并通过原生保存对话框导出 TS + manifest。两个 TS 都是 404200 字节，逐字节相同。
2. 使用真实引擎重新分析两个 TS：包含新名称，版本从 3 升至 4，无 CRC 错误。详见 export-readback.json。
3. Qt 另导出 BIN + manifest：977 字节、14 个 section；长度、偏移、适用的 MPEG CRC 均验证通过，包含新名称。
4. 两端实际取消原生保存后保留可用预览，之后成功导出；没有因取消丢失编辑。
5. 两端生成预览后再次修改名称，旧预览导出按钮都被禁用，须重新预览。截图和状态在 *-stale-preview-capture.json 指向的目录中。
6. A=59008、B=177999：两端都得到 4 个变化（1 个表记录、3 个服务记录、0 个事件记录）。历史证据检视使用 A 侧时刻，同时保持主工作区时刻不变。
7. 原始 lab.ts 的 SHA256 仍为 528c8cd44e1289e8f1d3f59a457bb9247d1f9716df21a4f30c6c6d18cb37ff96。

## 两端共同边界

- 当前编辑功能都是单 section、有效 actual SDT 的服务改名，不能据此声称支持所有表的任意字段编辑。
- 当前 GUI 导出入口附着于改名预览；没有独立的“原样导出当前快照”入口。这一项依据界面与源码核对，不是引擎 export API 能力缺失。
- 导出是 SI-only，缺少媒体和 PCR；不能当作完整可播放节目流。
- 本轮没有遍历所有表类型、所有非法输入、历史预设、分页和文件冲突分支。已有回归结果不等同于本轮逐项 Windows 手工验证。

## 本机证据索引

以下路径均相对本机忽略目录 `artifacts/operation-parity-audit/`；原始截图、导出文件、绝对路径和配置不会随此交接文档上传。其它机器应按复现步骤重新取证，不能假定这些文件存在。

- identity.json：版本、二进制、源文件身份。
- export-readback.json、qt-output.ts / .bin、web-output.ts 及各自 manifest：真实导出及回读。
- qt-before-compare.json、qt-after-compare.json、web-before-compare.json、web-after-compare.json：选择恢复差异。
- qt-use-snapshot.json：实际切换工作区到 A 时刻。
- web-compare-capture.json、web-compare-pmt.json：A 侧证据和 PMT 来源导航。
- qt-stale-preview-capture.json、web-stale-preview-capture.json：编辑后禁用旧预览的真实截图与状态。
- cleanup.json：独立验证进程退出及原试用窗口保留情况。


## 接手顺序与验收

1. 优先补 Web BIN 导出和 Use snapshot，并修复 Qt 对比退出丢失选择；随后对齐 Qt 编辑目标选择、多份来源证据、历史预设与 A/B 交换。
2. 统一操作时保留两边已有能力；两种导出格式、保存取消/冲突拒绝、预览失效、历史编辑的来源时刻都必须保留。不要把 SI-only 输出描述成完整媒体流。
3. 使用 `scripts/make_fixture.py` 的合成样本，两边选择同一服务、同一包号与解码上下文。记录源文件 SHA256，使用独立 UI 会话和新输出路径。
4. 选择 World News（SID 101），进入 A=59008/B=177999 对比，打开 Sports（SID 103）来源，再退出；两边都应恢复原服务、详情和主快照。显式 Use snapshot 则应将主工作区移到选定时刻。
5. 对每份来源分别检查 SDT/PAT/PMT 的 source ID、PID 与 cutoff；不能仅核对按钮存在。反向 A/B、相等范围、历史选择、分类过滤和分页也需覆盖，特别是未改名的表记录。
6. 同名编辑导出 TS/BIN + manifest，使用真实引擎回读 TS，按 manifest 验证 BIN section 长度、偏移和 CRC；对比双方结果并确认源文件不变。另测取消、已有输出/manifest 拒绝、名称/服务/快照改变后的旧预览失效。
7. 按改动范围运行 engine/Qt/browser 回归，再分别操作真实 Windows Qt 和 WebView2；不能只用 offscreen 或构建产物代替交互验收。保留已知浏览器环境限制，按现有 hosted CI 路线执行浏览器矩阵。
8. 按 DELIVERY_RUNBOOK 完成最终组合版本的 PR、CI、合并及合并后 CI，最后启动对应二进制供用户试用。若后续接手另开会话，先读用户当时指令再确认执行范围。

## 交接时的交付状态

核对时间：2026-10-18 09:53 UTC。本机工作区为 ShowPsiSi，原分支 `main`，upstream `origin/main`；二者均为 `88506ba3e78e5dc079d83961f3d77334e8ffd1a4`，本轮开始时无已暂存、未暂存或未跟踪源码文件，所有本地分支均已被 origin/main 包含，无待合并 PR。

- 上一轮功能交付：[PR #18](https://github.com/znbsf/ShowPsiSi/pull/18) 已合并；PR head 为 `f99afb463a756855846f7388a341e66d8c094517`，与合并版本的源码 tree 相同。
- [最终 PR CI 39108552186](https://github.com/znbsf/ShowPsiSi/actions/runs/39108552186) 与 [合并后 CI 39108923466](https://github.com/znbsf/ShowPsiSi/actions/runs/39108923466) 均已重新查询确认 success。这不是本次发现的差异已修复的证据。
- 本次用户要求为保留交接并完成必要合并推送；本次新增分支 `codex/operations-parity-handoff` 仅交付本报告与 STATUS 入口。文档变更不重新构建应用或重跑原生 UI，托管 CI 状态以本次 PR / 合并版本为准。
- 独立审计 Qt/Tauri 及其后端已退出；原试用 Qt/Tauri 窗口和后端保留（审计清理时已核实）。接手者须重新确认进程归属，不能凭旧 PID 操作。
- 现有差异是下一轮实施任务，不是本报告的已完成修复。通用表字段编辑和原样快照导出属于两端共同缺口，应单独明确能力范围及验收，不混入已完成的历史导航能力。
