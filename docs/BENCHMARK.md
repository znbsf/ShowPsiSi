# Qt Quick 与 Tauri 最小原型测量

测量日期：2026-10-17。当前两者加载表现接近；Qt 的私有提交内存明显较低，Tauri 的启动时间更短。不能由这三轮测量判定所有 Qt/Tauri 应用的性能。

## 同一输入和后端

- Windows 11 build 26300，Ryzen 9 9950X，32 个逻辑处理器，系统可见内存 47.16 GiB。
- Qt 6.7.3 / MSVC2019；Tauri 2.12.4 / Rust Release / 系统 WebView2；同一份 `showpsisi-core.exe` 与 TSDuck 3.39-3956。
- 同为 1380 × 900 逻辑像素窗口；截图为 2760 × 1800 像素。Web 界面使用普通 HTML/CSS/JavaScript，无大型前端框架或 CDN。
- TSDuck [官方法国地面电视样流](https://tsduck.io/streams/?stream=france-dttv) UHF22，183,939,388 bytes（约 184 MB / 175.42 MiB），978,401 个 TS 包。
- 两者读取 12 个服务、530 条事件、10,961 次 section 出现、370 个不同 section 内容。服务数与官方随附分析报告一致。

## 最终构建的三轮中位数

| 指标 | Qt Quick | Tauri + Web |
| --- | ---: | ---: |
| 从启动进程到界面就绪 | 1,154 ms | 433 ms |
| Analyze 到首批数据渲染信号 | 6.2 ms | 18.8 ms |
| Analyze 到完成状态渲染信号 | 198.6 ms | 195.1 ms |
| 加载前私有提交内存，整个进程树 | 111.1 MiB | 230.7 MiB |
| 加载后私有提交内存，整个进程树 | 137.1 MiB | 278.5 MiB |
| 采样到的峰值私有提交内存 | 137.1 MiB | 278.5 MiB |
| 峰值 working-set 求和 | 128.4 MiB | 400.8 MiB |
| 进程 CPU 时间合计 | 0.766 s | 1.563 s |
| 进程数峰值 | 3 | 9 |

逐轮完成时间：Qt 198.6 / 202.5 / 198.4 ms；Tauri 194.0 / 211.0 / 195.1 ms。两者差异处于这次观察到的波动范围，不能据此宣称某一方加载更快。相同后端占据主要扫描工作，前端没有解析 TS。

Qt 进程树包含 GUI、C++ 引擎和 console host；Tauri 另含 WebView2 的浏览器、渲染、GPU/utility 等子进程。没有只测 Tauri 主进程而漏掉浏览器。私有提交是 Windows private committed bytes，不等同于常驻物理内存；working-set 相加可能重复计算共享页，故优先比较私有提交。

## 口径与限制

使用 Release 二进制；先预热输入文件系统缓存；执行顺序为 Qt/Tauri、Tauri/Qt、Qt/Tauri。每轮在界面就绪后留 1.2 秒 idle，再扫描；完成后等待 0.6 秒再停止。每约 20 ms 对完整的自有进程树采样。

正式测量没有 Playwright、CDP、截图抓取或并行构建；WebView 数据目录复用，最终测量不含首次创建 profile 的开销。运行于用户正常 Windows 会话，没有锁频、清除文件缓存或隔离所有系统活动。

首批/完成数据的渲染信号分别采用 Qt `frameSwapped` 和 Web 两次 `requestAnimationFrame`。它们是渲染提交/机会的近似，**不是相同底层 API，也不是光学测量实际显示屏像素**。首次数据可只有 PAT/section 统计，不代表完整节目表或全部 EPG 已收齐。

CPU 时间覆盖启动、idle、扫描及完成后的 0.6 秒；不是仅解析耗时。20 ms 采样可能漏掉短暂内存峰值。此结果只代表这个样流、当前界面和这台机器；未覆盖冷盘、多 GB 文件、持续直播、复杂 EPG 时间网格或网络输入。

## 磁盘占用估算

`windeployqt --release --no-translations --no-compiler-runtime` 收集的 Qt UI/Qt 依赖约 65.9 MiB；加共用 C++ 引擎与 TSDuck DLL，约 **85.7 MiB**。Tauri exe 内嵌前端资源后，加同一后端约 **28.4 MiB**。

这不是可交付安装包尺寸，也不是整机依赖成本。Tauri 数字**不含系统已安装的 WebView2**；两者均未计入 MSVC runtime、TSDuck 模型/名称辅助文件、样流、SDK、构建产物和安装器。Qt staging 为未压缩文件总量。正式发布还需独立做依赖与许可证打包验证。

## 选型判断

若优先考虑长期打开、同时分析多个码流以及桌面工具的内存预算，我目前倾向 Qt Quick；这个原型已经能达到现代界面的视觉效果。

若更看重 Web 团队开发效率、后续浏览器/远程访问、现有 Web 图表生态和较小的新增应用包，Tauri 仍是可行选择。当前加载速度足够接近，没有理由仅为约十几毫秒的变化放弃某条路线。最终选择应加入用户实际操作体验；本轮没有替用户确认视觉偏好。

## 原始证据与复现

运行 `scripts/benchmark.py` 可复现。`artifacts/benchmark/results.json` 保存每轮事件、资源采样、进程路径、CPU 时间、已退出的进程清单，以及输入/后端/两个 UI exe 的 SHA-256。最终文件的构建身份为：

```text
source: 24143de80d28461d084dfb75279da520f335de36b7c35f6398ed6d510daa5937
core:   5d916171531a477a60d9ff84749a26099c58c16a03b5253289a5a3a37bbb30fa
Qt:     a8a7cd70c42e98675ab1d26150b5f53cdcc4e0f9608688eaa5c7a765727ccece
Tauri:  c3956b4ee0d0e30309922bb45518b415c78a3348d9b66262842fd80acb7ebdee
```

界面内的 “BACKEND SCAN” 只表示后端扫描时间；截图上的单次数字与上表的端到端三轮中位数是不同指标。
