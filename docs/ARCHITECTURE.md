# 扩展与 AI 原生接口

卫星关联也由 C++ 引擎负责：`lookup_satellite` 和
`inspect.satellite_associations` 读取同一个有来源的离线目录，Qt/Tauri 只呈现候选、
原始参数、来源和不确定性。轨位匹配不确定真实星体；不以频率猜身份。
边界和目录维护见 [卫星关联](SATELLITE_ASSOCIATION.md)。

## 当前运行结构

```mermaid
flowchart LR
  Qt[Qt Quick / QML] -->|JSONL / QProcess| Core[C++ showpsisi-core]
  Web[Tauri / WebView2] -->|Rust stdio bridge| Core
  CLI[CLI / Python scripts] -->|JSONL| Core
  Agent[AI agent] --> MCP[MCP stdio adapter]
  MCP -->|同一组操作| Core
  Core --> TS[TSDuck SectionDemux / descriptors / SDT serializer]
  Core --> Evidence[原始 section / 包位置 / 历史 / 错误]
  Core --> Rules[私有字段配置 / 排序 / 分组]
  Core --> Preview[编辑预览 + revision token]
  Preview --> Export[新 TS 或 BIN + manifest]
```

前端不解析 TS，也不自行改 CRC。两个原型调用同一个 exe，后端和输入的 SHA-256 记录在性能报告中。Tauri 的 Rust 层只管理进程、消息、文件选择和测量事件，业务逻辑留在 C++。

## 私有描述符：已经工作的配置路线

参见 `extensions/demo.json`。私有标签不能仅凭 tag 判断；这里使用 `(PDS, table_id, tag)` 三项限定，以免不同运营商的同号描述符被混淆。

样例在 SDT 的 service descriptor loop 中使用 `private_data_specifier = 0x53505349`，之后的 `tag = 0xE1` 负载为：

| 偏移 | 字段 | 类型 |
| --- | --- | --- |
| 0 | logical_channel_number | u16 大端 |
| 2 | group | u8，映射成 News / Culture / Entertainment |

未识别的 `0xE2` 仍保留为 `E204CAFEBABE`，没有臆造解码结果。描述符 loop 边界先验证，再运行字段配置；标准服务名/事件名交给 TSDuck 解码。

通过 `load_extension` 加载另一份 JSON，再 `analyze` 即可生效；`organization.sort_by` 和 `group_by` 从派生服务字段中选择排序与分组来源。集成测试已验证换 PDS 后解码不会误匹配、改变排序字段无需编译。

这一层只覆盖定长 u8/u16 字段。复杂循环、位域、加密负载、多表关联、私有表 ID 和运营商特有的完整节目组织，不适合无限堆叠 JSON 表达式。

## 复杂私有协议：后续 C++ 扩展路线

优先复用 TSDuck 的 `AbstractDescriptor` / `AbstractTable` 和 PSI 注册机制，按官方 [扩展开发说明](https://tsduck.io/docs/tsduck-dev.html) 编译与 SDK 版本匹配的模块，补充 XML 模型和名称文件。描述符解码与节目组织保持两个独立接口：

1. **协议模块**接收明确上下文（广播标准、PDS、registration id、table id、原始字节），返回字段、字节范围、错误，并可选实现 encode。
2. **组织模块**接收同一时间截面的完整表集合，返回频道/分组/LCN/EPG 关系，以及每个结果引用的 section ID 和字段位置。

组织结果是有来源的派生视图；只有显式编辑才生成修改。不能让“排序/分组”顺带修改捕获数据。配置之间冲突必须报告，未知字段始终可以回到 hex。

原型尚未实现任意 DLL 加载。正式接入时应固定插件 ABI 与 TSDuck 构建版本；可信原生插件可在引擎内运行，需要隔离故障或第三方脚本时采用独立 worker。当前框架已经有进程边界，但并不等于安全沙箱。

## AI 原生：已经可调用的能力

### ID、字符编码与多语言 EPG

`core/SignalMetadata.h` 在 C++ 层生成三类只读解释，Qt 和 Tauri 共用结果：

- `lookup_identifier` 不需要先扫描，按 ID 命名空间、位宽和标准上下文查询安装的 SDK 名称库。返回原始数字/十六进制值、名称或未知状态、名称库文件/节、SDK 版本及不确定性。名称库不等于当前运营商所有权核验；无法确认的资料日期为 null。
- `inspect.identifier_lookups` 关联受支持的表头和原生描述符属性，指向原始 section、字段路径及所在表头/描述符偏移。不会通过 SID、PID、TSID 或轨道位置猜测运营商/卫星。
- `inspect.text_diagnostics` 从已确定结构的原始字段提取有界字节，记录长度、字符集选择符、配置/生效字符集、解码状态及警告。`analyze.default_charset` 仅覆盖本次扫描的默认输入字符集；DVB 字符集尊重显式选择符，RAW 字符集不识别 DVB 前缀。它不是自动探测，也不会改写源文件或输出编码。
- `events[].language_variants` 保留每种语言的全部短描述和扩展片段。仅在同一原始 EIT section 的同一事件内按语言和片段编号组合；缺失、冲突或无效片段不输出完整扩展文本。重复片段保留来源，完全一致的重复只组装一次。快照比较剔除来源位置的变化，返回值仍保留证据。

两端 Metadata 视图均提供 ID 查询、逐字段诊断、语言选择及可展开的原始证据。首选语言缺失时明确标记回退；所选语言有冲突时显示状态，不借用另一语言的标题伪装成功。范围和验证边界见 [PROTOCOL_COVERAGE.md](PROTOCOL_COVERAGE.md)。

“AI 原生”在这里是操作接口和证据结构的设计，而不是在 UI 附加聊天框。

`api/tools.json` 是能力发现入口，同时用于后端参数验证和 MCP tools/list。当前操作：

| 操作 | 结果 |
| --- | --- |
| capabilities | schema、版本、能力边界 |
| analyze | 增量进度、服务/事件、历史、诊断 |
| cancel_analysis | 按原始分析请求 ID 请求合作式取消，原请求另行返回终止状态 |
| query | 指定包位置的观察快照 |
| inspect | 原始 hex、字段、字节偏移、指定截面内的出现位置 |
| diff_snapshots | 同次分析的 A/B 截面对比：表、服务、事件的新增／移除／变化，附双方证据 |
| load_extension | 加载声明式协议规则，要求重新分析 |
| preview_rename | 修改前后、version/CRC、绑定当前 revision 的 token |
| export | 写新文件，返回来源与修改 manifest |

工作流可以是：“查询发生问题的版本 → 定位 CRC 或描述符字段 → 提议改名 → 检查预览 → 输出测试流 → 重新分析验证”。GUI、脚本、MCP 完全共享该路径，AI 无需模拟点击或识别截图。

JSONL 示例（每行一个 JSON 对象，同一进程内保留分析状态）：

```json
{"id":1,"method":"analyze","params":{"path":"C:/captures/input.ts"}}
{"id":2,"method":"query","params":{"at_packet":60000}}
{"id":3,"method":"inspect","params":{"id":"从 query 返回的 section id"}}
```

响应为 `{id,result}` 或 `{id,error:{code,message}}`；分析过程中还会出现 `{event:"progress",request_id,state}`。标准输出只输出协议数据。普通请求仍按 FIFO 串行执行；独立输入控制路径允许长扫描期间请求取消。Engine/TSDuck 状态只由一个线程访问。具体状态、EOF 与 MCP 语义见 [取消契约](ANALYSIS_CANCELLATION.md)。

MCP 客户端的配置示例（不自动修改任何客户端配置）：

```json
{
  "mcpServers": {
    "showpsisi": {
      "command": "C:/path/to/ShowPsiSi/.deps/py/Scripts/python.exe",
      "args": ["C:/path/to/ShowPsiSi/scripts/mcp_server.py"]
    }
  }
}
```

MCP adapter 已通过 initialize、tools/list 和完整 tools/call 工作流：分析、查看原始证据、预览改名、导出、回读验证；中文服务名与中文输出路径也已覆盖。未测试特定外部 AI 客户端，也没有配置模型、API key 或自动授权客户端写文件。协议具备本机文件读取和新文件输出能力，应按客户端的实际授权范围接入。

后续优先增加有字段 schema 的 `preview_patch`、批量事务、持久化证据索引和 export profile。届时可将工具结果进一步分页，避免把所有 EPG/出现位置一次性塞进 AI 上下文。


## 截面对比（下一轮实现）

`diff_snapshots` 是只读操作，要求一次成功完成的分析。`from_packet` 和
`to_packet` 使用当前分析内的零起始包编号，包含在对应包完成接收的 section。
允许 A→B 和 B→A；每条结果携带双方各自的包位置与证据，不修改查询或编辑状态。

表按有效 current section 的稳定槽位比较；重复收到相同字节不会被当成变化。
服务按 ONID/TSID/SID 关联；事件另外保留 PID、表、section、事件 ID 和开始时间，
不把 p/f 与 schedule 的不同证据强行合并。增加／移除表示两个观测截面的差异，
不能解释为已经证明节目开播／停播。

`kind` 可选 `all`、`tables`、`services`、`events`；`offset`、`limit` 提供确定性分页，
单页最多 200 条。`summary` 给出各类统计，`next_offset` 为 null 时表示没有下一页。
`before`／`after` 内含 `at_packet`、`value` 和 `evidence`；前端必须用相应一侧的
截面调用 inspect，避免从历史比较跳到未来的解码结果。
