# Validation

Summary/PID组件回归使用可选SHOWPSISI_BUILD_QT_COMPONENT_TESTS，
以真实生产引擎生成数据，再运行scripts/ci/qt_components.py。
宿主在component-tests/Release，不进入生产包；使用隔离输入/截图，
检查实际测试总数、QML诊断、列对齐、来源/聚合、返回状态及深浅主题。
参见[当前实现与准确测试边界](../docs/NXTSA_UI_UX_PARITY.md)。


Responsive local-file analysis adds `test_responsive_analysis.py`,
`test_analysis_preview_review.py` and `test_qt_analysis_modes.py` to the strict
native gates. These exercise compact result paging, pause/resume/cancellation
and bounded preview coverage against the actual engine. See
[the contract and benchmark limitations](../docs/RESPONSIVE_ANALYSIS.md).

Windows AppLocal packaging helper regressions run with Python 3.12 and pinned
`pefile==2024.8.26`: `test_vc_runtime.py`, `test_applocal_validation.py`,
`test_corresponding_source.py`, `test_portable_package.py`,
`test_installer_package.py` and `test_release_publisher.py`. Use
`python -m unittest discover -s tests -p NAME.py -v` for each named suite.
They cover exact byte/provenance gates, source pairing and publication failure
paths; their Linux passes do not establish native Windows execution.
`test_windows_acceptance_host.py` is Windows-only and belongs in the Windows CI
job, outside Linux's no-skip engine gate. See the separate
[clean-host and module acceptance contract](../docs/WINDOWS_APPLOCAL_ACCEPTANCE.md).

Workbench parity: `test_section_evidence.py` checks all-family content history,
including repeated/reused versions, private, short, next and invalid evidence.
The `workbench` cases in Qt/browser suites and `test_ui_agent.py` check matching
record counts/search/modes, all inspector scopes/views, history filtering and
exact advertised packet jumps using the real engine. Native mouse/keyboard
acceptance remains a separate gate.

Explorer parity: run `-k explorer_counts` with `test_qt_ui.py` and
`test_web_ui.py`. Both use `explorer_fixture.py` through the actual engine:
one PID carries SDT, BAT and unknown/private evidence, with multiple sections,
repetitions and bad CRC. Checks cover logical-group totals, single-list scope,
keyboard focus/activation, cross-PID type filtering, zero-result types and
snapshot counts. `test_ui_agent.py` additionally compares both native frontends'
rendered explorer identities/counts against a separate real-engine analysis.

Satellite candidate contracts run with
`python -m unittest discover -s tests -p test_satellite_metadata.py -v`.
The strict native runner includes them. Run `-k satellite_candidates` against
the Qt/browser UI suites for real control interactions and unchanged source
assertions. Scope and catalog provenance: [satellite association](../docs/SATELLITE_ASSOCIATION.md).

The signal-metadata suite (`test_signal_metadata.py`) runs through the real core
without SDK compiler fixtures. It covers ID registry provenance and unknowns,
bounded wire-string diagnostics, multilingual short/extended EIT text and
fragment conflicts, event/version isolation, and semantic snapshot comparison.
The `signal_metadata` tests in both UI suites operate real controls against that
fixture. Run `python -m unittest discover -s tests -p test_signal_metadata.py -v`;
use `-k signal_metadata` with `test_qt_ui.py` or `test_web_ui.py` for the UI checks.
On Windows set `PYTHONUTF8=1` (including real-engine Python proxy fixtures) and
`QT_QPA_FONTDIR` to the system Fonts directory for readable offscreen captures,
as the hosted Windows setup does. Full suite evidence is separate from builds.

Integration suites use the real native JSONL engine. Selected transport/error
tests deliberately use scripted subprocess fixtures to inject invalid or late
responses; they do not establish parser correctness. Build `showpsisi-core` first
and make TSDuck's runtime libraries available to the dynamic loader. `SHOWPSISI_CORE` can
select an alternate executable; otherwise `build/bin/showpsisi-core` (or `.exe`)
is used.

```sh
python -m unittest discover -s tests -p test_engine.py -v
python -m unittest discover -s tests -p test_section_evidence.py -v
python -m unittest discover -s tests -p test_cloud_preview.py -v
python -m pip install playwright
python -m playwright install chromium
python -m unittest discover -s tests -p test_web_ui.py -v
```

The browser suite also accepts a system Chromium executable through
`PLAYWRIGHT_CHROMIUM_EXECUTABLE`. A `chromium` or `chromium-browser` on PATH is
used automatically. It generates a deterministic 12 MiB transport stream and a
null-packet-only stream in a temporary directory, starts a fresh real engine per
test, and writes screenshots to `artifacts/web-ui-tests/`.

Coverage includes real analysis and selection, empty and missing sources, search,
keyboard record/tree navigation, disclosure controls, XML/hex evidence, preview
invalidation, explicit ATSC/ISDB decoder contexts, invalid extra-PID inputs,
HTTPS reference links, 1100/900/520 px responsive layouts,
historical multi-section native assembly cutoffs across every detail view,
real in-flight backend termination and disconnected/dead-startup handling,
export/reparse/source preservation, no-overwrite protection, and
loopback bridge request/path restrictions. Open/save native dialogs are explicitly
unsupported by the browser bridge. Export correctness is tested over the actual
JSONL API after verifying that the browser save dialog fails honestly.

This validates Chromium-rendered web assets and their engine integration. It does
**not** validate the native Tauri window, WebView2, native file dialogs, installers,
or operating-system integrations. It does not replace a Windows native smoke test.

## Interactive preview

```sh
python scripts/cloud_preview.py --port 8765
```

Open the printed `http://127.0.0.1:8765` address from a browser on the **same
machine/network namespace**. The bridge binds only IPv4 loopback and checks the
Host, Origin, and an ephemeral request token. It exposes only the three web
assets and bounded JSON endpoints. It never uploads files. Browser export API
requests are restricted to the preview output's `artifacts/` directory; the native
engine still enforces no-overwrite. One browser session per preview process.

`--sample /local/path.ts` selects initial input; `--output /local/directory`
changes the validation output root. Native dialogs are not emulated: type an
input path instead, and use the CLI/API to test exports.

If a sandbox disallows Chromium's required process/socket operations, run these
same tests in a permitted desktop/CI environment. Do not treat a failed launch
or a screenshot-only snapshot as a passing live integration test.

## Snapshot comparison and layout regressions

The engine suite checks `diff_snapshots` through JSONL and MCP, bounded/stable
pagination, reverse and equal cutoffs, no evidence from future packets, network
identity collisions, unchanged repeat observations, and preservation of preview
state/source bytes. Protocol tests exercise generation reuse, same-packet wire
order and canonical service projection as well as native descriptor semantics.

The browser and compiled Qt suites exercise A/B capture, side-specific evidence,
restored main-snapshot navigation, active-request locking, persisted splitter sizes,
reset and invalid-settings behavior. Qt additionally validates the populated
1000×680 comparison with a tall saved timeline and real scroll-to-visible selection.

The hosted Windows route is `.github/workflows/ci.yml` plus
`scripts/ci/windows.ps1`. It uses official pinned SDKs, explicit native executable
paths, UTF-8 and an offscreen Qt plugin. Its strict Python runner rejects missing
executables, empty suites and unexpected skips. Only the named optional real-file
test is allowed to skip when that exact recording is absent; the result reports
that exclusion explicitly. This is not equivalent to native dialogs, WebView2,
installer testing or real-recording coverage on Windows.

## Cooperative cancellation

Build the optional native helper explicitly for the new deterministic suites:

```sh
cmake -S . -B build -DSHOWPSISI_BUILD_CANCELLATION_TESTS=ON
cmake --build build --parallel 4
export SHOWPSISI_TEST_CORE="$PWD/build/bin/showpsisi-core-test"
python -m unittest discover -s tests -p test_cancellation.py -v
python -m unittest discover -s tests -p test_mcp_cancellation.py -v
```

Retain the normal TSDuck/Qt SDK arguments used by your environment. Windows CI
sets explicit `.exe` paths under its Release output directory. Production
`showpsisi-core` and helper `showpsisi-core-test` are separate executables; helper
hooks are absent from the production build. Required CI suites fail if the helper
is missing rather than treating absent cancellation coverage as success.

The core suite gates queued, progress, read and completion boundaries, checks
bounded FIFO/control bypass and exact typed IDs, and verifies no stale preview or
evidence after cancellation. MCP tests use real subprocesses for outer/native ID
mapping, token-scoped progress, repeated cancellation, EOF drain and callback-safe
close. Qt/Web tests cover visible Cancel/Cancelling, terminal acknowledgement,
rescan, stale UI responses and unexpected backend death. Native smoke evidence
identifies when the compile-only helper is used; no timing benchmark is inferred
from a deliberately gated or paused test process.

## SDK 3.45 and protocol expansion

The pinned SDK is TSDuck/TSCore 3.45-4798. The build requires C++20 and checks
version-specific symbols from both libraries. Changing `TSDUCK_ROOT` re-resolves
all SDK paths rather than silently keeping a previous build directory's cache.

```sh
python -m unittest discover -s tests -p test_sdk_migration.py -v
python -m unittest discover -s tests -p test_protocol_coverage.py -v
python tests/fixtures/tsduck345/reproduce.py --compiler /path/to/tstabcomp
```

The SDK suite checks runtime/header identity, Unicode input/output/root paths,
manifest roundtrip and explicit DTMB context without guessed charset/timezone.
Protocol fixtures exercise new native tables and namespace boundaries; the
fixture directory documents the official compiler commands and expected bytes.
Configure the compiler runtime paths as described in the fixture README.
Registered decoder counts are not a standards-conformance claim. See
[protocol coverage](../docs/PROTOCOL_COVERAGE.md) for measured scope and limits.


## Standards-informed workbench checks

`python -m unittest discover -s tests -p test_ui_contrast.py -v` checks selected
actual authored CSS/QML text, focus and control-border color pairs. It is a
regression test, not a complete accessibility-conformance audit.

The native Qt smoke includes Home/End, collapse/expand/child/parent and Tab exit.
The real-engine Chromium suite includes roving tree focus, pointer isolation,
repeated disclosure, filtered/empty states and the actual Chromium accessibility
tree. Run it using the existing `test_web_ui.py` environment above.

`python tests/capture_ui_ux.py` optionally captures 28/32px density comparisons at
1440×900, 1000×680 and 520×1000 plus a real narrow validation error. It requires the
same live-engine/sandboxed Chromium setup and writes to
`artifacts/ux-standards/web/`. These are browser screenshots, not native Tauri
acceptance. See [the scoped UX review](../docs/UI_UX_STANDARDS.md).

### Qt asynchronous completion and retained evidence

The strict Qt job runs `test_qt_ui.py`, `test_qt_resource_paths.py`, and
`test_qt_evidence.py` on Linux and Windows. Run any of those with
`python -m unittest discover -s tests -p <filename> -v` in the native environment.
On Windows, the suite inherits only `LD_LIBRARY_PATH` from its launcher, so a
manual local run must also put the Qt binary directory on `PATH` and set
`QT_QPA_FONTDIR` (the hosted workflow does this explicitly). A Qt executable that
cannot find its DLLs exits with `0xC0000135` and is reported as a missing result,
not as a product failure.

`test_pid_explorer_logical_tables_and_density_cursor` runs the `refresh`
self-check script. That script selects a snapshot through a density bin click and
verifies the service heading, numeric PID ordering and filtering, logical
tables, and the current-position cursor in the real application, with bounded
waits so a stuck phase reports a failure instead of hanging.

Export regression deliberately delays duplicate Save-dialog acceptance and checks
that refused/repeated/cancelled operations preserve the original output and
manifest hashes and mtimes. Snapshot comparison holds a real-engine query response
until the UI acknowledges waiting; cancellation fixtures use ACK/terminal and
late-frame handshakes rather than elapsed sleeps. All waits keep their deadlines.

Set `SHOWPSISI_QT_TEST_ARTIFACTS` to retain per-test explicit JSON/log/PNG/trace
files, including incomplete results and failed assertions. Each file is capped at
5 MiB. The shared context preserves the original exception if copying fails.
See [CI completion contracts](../docs/CI_TEST_CONTRACT.md) for reproduced causes.

## Section evidence contract

`test_section_evidence.py` covers section/header/CRC identity, repeat versus missing
coverage, current/next/PID separation, generation-safe merged provenance, legal EIT
schedule segment holes, short TOT CRC validation, and bounded histogram output for
a 20,000-repeat burst. See [the additive contract](../docs/SECTION_EVIDENCE.md).

## UI agent diagnostics and tree parity

Set `SHOWPSISI_QT` and `SHOWPSISI_TAURI` to freshly built binaries, then run
`python -m unittest discover -s tests -p test_ui_agent.py -v`. These are real
frontend/engine tests: they assert rendered tree colors and glyphs, exercise the
limited navigation API, reject arbitrary evaluation, and verify real PNG/state
bundles while preserving the sample hash. Qt uses offscreen rendering; Windows
Tauri uses WebView2. Missing binaries are reported as skips. Evidence (including
failures) is retained under `artifacts/ui-agent-tests`; override it with
`SHOWPSISI_AGENT_TEST_ARTIFACTS`. Each test isolates preferences and WebView data.
Python-backed Qt fixtures explicitly use UTF-8 to match the JSONL protocol on
Windows. See [UI agent contract and usage](../docs/UI_AGENT_DEBUG.md).

## Signal topology

`python -m unittest discover -s tests -p test_topology.py -v` exercises the
production C++ graph and MCP contract across DVB, ATSC 1.0 and explicit ISDB
profiles, exact source locators, adversarial identity/generation/cutoff cases and
bounded pagination above 2,500 programs. Included in the strict engine runner.
`topology_fixture.py` is the shared deterministic wire generator for frontend
checks; it does not return mocked topology data. See
[the API contract](../docs/TOPOLOGY_API.md) for explicit unsupported semantics.

## Protocol source navigation

`test_qt_protocol_cards.py` and `test_web_ui.py` include real-engine NorDig SDT
simulcast field jumps and three-table PAT/PMT/AIT carriage sources in both themes.
They retain exact revision/cutoff/byte-range and Back-context assertions. Run the
complete Qt/browser gates after integrating protocol changes, using immutable
core/helper/API/reference inputs. See the [protocol test contract](../docs/PROTOCOL_TEST_PLAN.md)
and [supported subsets](../docs/PROTOCOL_COVERAGE.md#current-protocol-extension-support).

```sh
python scripts/ci/windows_native_checks.py --qt --artifacts artifacts/protocol-qt
python -m unittest discover -s tests -p test_web_ui.py -v
python -m unittest discover -s tests -p test_cloud_preview.py -v
python -m unittest discover -s tests -p test_ui_contrast.py -v
```

The runner name does not identify the host OS. Offscreen Qt and sandboxed
Chromium checks do not prove native Windows/macOS dialogs, WebView2, GPU,
clean-machine installation or receiver conformance.
