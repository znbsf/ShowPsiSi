# ShowPsiSi prototype status

Owner: current Codex task. Updated: 2026-10-17 (Asia/Hong_Kong).

## Scope and acceptance

Build two running Windows prototypes (Qt Quick and Tauri/Web) using the same native C++/TSDuck engine and request protocol. Compare visual interaction, time to first data/completion and the full owned process tree's resource usage. Provide a private-descriptor extension and service-organization rule example. Expose the same engine operations to CLI and MCP clients; edits produce previews and separate outputs.

Inputs: reproducible synthetic DVB TS including changing SDT versions, private descriptors and invalid CRC, plus two official TSDuck French terrestrial TV recordings. A user-specific sample remains optional; synthetic performance is not representative-stream acceptance.

## Baseline

Workspace initially empty, not a Git repository; no project runbook/profile or relevant memory result found. TSDuck 3.39-3956 developer library and MSVC 14.29.30133 available. WebView2 available. Qt/Rust not on PATH or in standard SDK locations.

## Validation plan

| Layer | Required observation | Status |
| --- | --- | --- |
| Native engine | Actual TSDuck callbacks, repeat/version/CRC provenance, matching exports | passed: 10 integration tests; 12 real services match official reference |
| Extensions | PDS-scoped descriptor decode and organization rule without source change | passed: scope mismatch and alternative sort configuration tested |
| Agent interface | Discover schemas, query evidence, preview edit, export via CLI/MCP | passed: MCP discovery -> inspect -> Chinese rename -> export -> reparse |
| Qt Quick | Real compiled application, first-data/completion events, screenshot and interactions | passed: own-window mouse interaction checks; real and synthetic screenshots |
| Tauri | Real compiled application using WebView2 and same backend, screenshot and interactions | passed: actual WebView2 controls via Playwright, no page errors |
| Comparison | Release builds, same sample/backend/settings, sequential trials and child-process accounting | passed: 3 alternating trials of final corrected binaries; full raw records in artifacts/benchmark/results.json |

## Experiment boundaries

Dependency downloads and builds are local to this workspace. No global proxy/tool configuration, device operations, or service installation. Initial dependency/build probe budget: one direct attempt plus at most two evidence-driven retries per failing route. Benchmark initially three alternating trials per UI; stop and record invalid environment on rendering failure, parser mismatch, abnormal system contention, or user pause. No unrelated process is stopped. Owned prototype/helper processes must be tracked and stopped after automated measurements.

## Outstanding

Both prototypes are built locally and runnable with `Launch Qt.cmd` / `Launch Tauri.cmd`. Source, schemas, examples and local SDK bootstrap/build scripts are present. The private source repository is [znbsf/ShowPsiSi](https://github.com/znbsf/ShowPsiSi). A fresh clone requires dependency setup, compilation and fixture generation as described in README. No PR, global service or model integration created.

Source distribution includes the two real-stream UI screenshots in `docs/images/` and the benchmark report. SDKs, build outputs, WebView profiles, local test artifacts, generated fixtures and downloaded TS binaries remain outside Git. The `artifacts/` references below describe local validation records, not files included in the repository.

Official samples downloaded from TSDuck: UHF22 (183,939,388 bytes, 12 services) and UHF33 (83,464,668 bytes, 1 service), provenance in `samples/real/provenance.json`. Synthetic fixture has known SDT changes, scoped private descriptors and injected faults.

Independent `tstables` XML readback confirms both GUI exports renamed service 103, incremented SDT to v4, and retained valid CRC. Source remains unchanged. Evidence: `artifacts/export-readback.json`, `artifacts/engine-tests.log`, UI test JSON/screenshots.

No UI winner selected by the user. Current measurements favor Qt for private memory and Tauri for startup time; both load the real sample in roughly 0.2 seconds after Analyze. Read `docs/BENCHMARK.md` for the final build identities, exact metrics and limits.

Human visual preference and real receiver/playback acceptance are pending. Windows only has been built/tested. Private compiled DLL plugins, comprehensive standards validation, arbitrary table editing, full remux with media/PCR, streaming input and a production EPG time grid remain beyond the minimal prototype. These are documented in README; do not treat this baseline as their completion.

All automated helper/prototype process trees are explicitly stopped after each check. No persistent monitor or background service was started. Resume from the existing source and evidence instead of repeating dependency downloads or the earlier UI fixes.
