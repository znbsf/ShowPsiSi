# Cloud development and validation

This work is performed in a Linux cloud workspace, not on the owner's Windows PC or television. Windows prototype evidence in `STATUS.md` is historical; it does not validate the new UI build.

## Build the shared engine

Install the matching TSDuck + TSCore **3.45-4798 runtime and developer SDK**, a C++20 compiler (GCC 13+ on Linux, VS 2022 on Windows), and CMake >=3.22. The SDK can be installed normally or extracted into a workspace directory. Do not put SDKs, generated streams or build products in Git.

```sh
cmake -S . -B build -DBUILD_QT_UI=OFF -DTSDUCK_ROOT=/path/to/tsduck/usr
cmake --build build --parallel 4
python scripts/make_fixture.py
python -m unittest discover -s tests -p test_engine.py -v
```

When using extracted Linux packages, choose the packages for the actual distribution (Ubuntu 24.04 in CI; Debian 13 in this cloud workspace). Add their library directories to `LD_LIBRARY_PATH`, including transitive dependencies. Both `libtsduck.so` and `libtscore.so` are required; missing SRT/RIST/OpenSSL or other transitive libraries are loader failures, not protocol-test skips. `SHOWPSISI_CORE` overrides the executable path for Python clients and test helpers. No global installation or proxy change is required.

For Qt, supply `CMAKE_PREFIX_PATH` pointing to a Qt >=6.5 SDK with Quick and QuickControls2, enable `BUILD_QT_UI`, and install OpenGL development dependencies. This development session uses Qt **6.7.3**. For headless tests use `QT_QPA_PLATFORM=offscreen` and `QT_QUICK_BACKEND=software`; this verifies software-rendered UI, not GPU performance or native desktop integration.

## SDK migration and regression gate

TSDuck 3.45 separates generic TSCore headers/libraries from MPEG-TS-specific
TSDuck code. Set `TSDUCK_ROOT` to one complete matching SDK prefix, such as the
`usr` directory produced by extracting both Linux `.deb` files with
`dpkg-deb --extract`. CMake uses both `include/tscore` and `include/tsduck`, links
both libraries, and stages the matching XML/name databases. An old SDK or mixed
header/runtime combination is unsupported. See [dependency identities and
Windows setup](DEPENDENCIES.md) for the pinned official assets and SHA-256s.

Use a fresh build directory or `cmake --fresh` when moving from 3.39 to 3.45.
Do not reuse old CMake include/library cache entries. The production build keeps
test cancellation gates disabled by default. To run the strict native gate,
build the separate opt-in cancellation helper too:

```sh
cmake -S . -B build -DBUILD_QT_UI=OFF -DSHOWPSISI_BUILD_CANCELLATION_TESTS=ON \
  -DTSDUCK_ROOT=/path/to/tsduck/usr -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 2
python scripts/make_fixture.py
SHOWPSISI_CORE="$PWD/build/bin/showpsisi-core" \
SHOWPSISI_TEST_CORE="$PWD/build/bin/showpsisi-core-test" \
  python scripts/ci/windows_native_checks.py --artifacts artifacts/linux-native --engine
```

Despite its historical filename, the strict runner is shared by Linux and
Windows. It runs engine, protocol, SDK migration, HTTP, native cancellation and
MCP transport suites, retains native startup diagnostics, and rejects missing
binaries, zero coverage or unexpected skips. Only the separately sourced optional
French recording may be absent, with its exact existing skip reason. SDK migration
checks include linked-runtime consistency and Unicode file/extension/export paths.

The CI topology remains five jobs: Linux engine/web, Linux Qt, Linux Tauri build,
Windows MSVC engine/Qt, and Windows Tauri build. Ubuntu 24.04 downloads both pinned
SDK packages and verifies their hashes before installation. Windows extracts the
official installer payload without executing it, uses VS 2022 with Qt's unchanged
`msvc2019_64` kit, and checks both TSDuck/TSCore DLLs and data. Native dependency
and loader diagnostics are retained even when a regression fails.

Browser CI still uses the runner's official `/opt/google/chrome/chrome` binary
with an explicit sandbox-enabled preflight. Do not replace it with an unpacked
Chromium binary, add `--no-sandbox`, or count preflight failure as an application
test result. Compilation, offscreen Qt checks, sandboxed browser tests and actual
native Tauri interaction each retain their own evidence boundary.

## Browser validation

```sh
python -m pip install playwright
python -m playwright install chromium
python scripts/cloud_preview.py --port 8765
python -m unittest discover -s tests -p test_cloud_preview.py -v
python -m unittest discover -s tests -p test_web_ui.py -v
```

The development server binds loopback only, serves the actual web assets, and forwards requests to the real native engine. It is **not a Tauri runtime**. Native file dialogs are explicitly unavailable. Export is restricted to its output directory. Host/origin/token checks reject cross-origin requests. Stop the server when finished. Do not expose it to a LAN or public network.

`tests/render_web_snapshot.py` produces a separate offline visual-inspection page from captured real-engine responses. A snapshot is not proof of live backend integration; edits, exports and native dialogs are not simulated as successful operations.

If a cloud browser has a separate network namespace, `127.0.0.1` in that browser may not reach this server. Do not switch to the owner's computer or expose the server publicly to work around it. Record the limitation and use supported cloud validation paths.

## Development rules

- Read `REQUIREMENTS_AUDIT.md` before repeating investigations. Record new causes and reproduction steps there or in the relevant test.
- Read `PROTOCOL_COVERAGE.md` for protocol support; distinguish library capability, implementation and fixture-backed validation.
- Keep raw bytes and provenance authoritative. A decode label is not a comprehensive standards-conformance verdict.
- Failed scans must not retain evidence under a different source name. PMT association follows the PAT-selected PID, not just a service ID.
- File exports never overwrite existing files and must report manifest/output failures. Preview tokens belong to one analysis revision.
- Keep production UI independent of the browser-validation adapter. No bundled sample data masquerading as a successful scan.
- Run tests before pushing a feature branch. Do not rewrite main or merge without reviewing outstanding platform limitations.

## Cloud desktop launch fallback (verified 2026-10-16)

A restricted shell may reject Chromium's required socket/IPC operations before any
application test runs. In this environment the supported cloud desktop can launch
the same test command. This is the assistant's cloud desktop, not the owner's PC.

If terminal text entry fails because its focused terminal is not exposed as an
editable accessibility field, use the desktop's Application Finder (Alt+F2).
A short wrapper under `/workspace/shared/` is accessible from both the shell and
the cloud desktop. `/tmp/` may be a different filesystem namespace: a successful
launch action alone does not prove the wrapper ran. If text entry is unavailable,
the documented native per-key input works in the Finder's command field. Inspect
the complete command before pressing Enter, then verify a fresh output log and
exit status in the shared workspace. Do not infer success from a closed dialog.

Keep wrappers, logs and transient screenshots ignored, stop only processes owned
by the validation task, and retain the production browser/native distinction.
Do not disable Chromium/WebKit sandboxing or change host security settings to
work around an execution-environment restriction.


## Qt user-selected export destinations

Qt's edit dialog now selects TS (SI-only transport stream) or BIN (raw sections)
before opening `QtQuick.Dialogs.FileDialog` in `SaveFile` mode. The initial folder
is a writable Documents folder when available, otherwise the user's home; a
successful export remembers its actual output parent for this session. The
source-derived suggested leaf name is sanitized and ends in `-edited-si.ts` or
`-edited-si.bin`. A suffix which contradicts the chosen format is refused.
There is no production fallback to the resource root's `artifacts/` directory.
Scripted captures must explicitly configure `SHOWPSISI_ARTIFACT_DIR`.

`DontConfirmOverwrite` suppresses a misleading Replace offer; the shared engine
still exclusively creates the output and adjacent manifest. Either collision is
reported inside the edit dialog, preserving the preview for a different path.
Cancel writes nothing and returns focus to Save. An invalidated scan/preview
cannot later export a stale picker selection. BIN has no packet framing, PID or
timing by itself; both formats omit media and PCR. These are not full remuxes.
See the [official FileDialog API](https://doc.qt.io/qt-6/qml-qtquick-dialogs-filedialog.html).
The implementation was compiled and exercised with Qt 6.7.3.

Validation on the assistant's own Linux cloud computer, 2026-10-16 UTC:

- All **15 compiled Qt integration tests passed**, with **20 assertions** in each
  save-flow scenario, plus independent native-core TS readback and raw BIN section
  checks. The scenarios cover external Unicode paths, missing/mismatched suffixes,
  cancel, output/manifest collisions, unchanged source, stale preview, remembered
  folder, compact controls, safe names and cleared feedback when reopening edit.
- A separate POSIX scenario chmods a copied application resource root read-only
  and exports elsewhere. Windows runs the separate-root flow without claiming
  equivalent ACL validation. Existing scan cancellation, disconnected/stale
  backend, comparison, layout, keyboard and PlainText regressions still pass.
- Actual GTK3-native file dialogs were exercised in the compiled Linux Qt app:
  cancel preserved preview/focus; two traced repeated accepts of an existing
  target reached the backend and showed its refusal without a Replace prompt;
  output/manifest hashes stayed unchanged. An initial untraced picker closure
  was inconclusive and is excluded from that acceptance evidence.
- Native TS export was **404,200 bytes**, BIN **968 bytes**. Independent TS
  readback recovered edited SID 103 (`Final Qt`) with zero CRC diagnostics. The
  BIN manifest's section lengths, offsets and one-cycle/no-null semantics matched
  its bytes. The source SHA-256 remained
  `528c8cd44e1289e8f1d3f59a457bb9247d1f9716df21a4f30c6c6d18cb37ff96`.
- Both native runs closed with exit 0, empty stderr and no remaining owned app,
  engine or launcher process. Final format-menu contrast and edit-feedback
  clearing were subsequently rebuilt and covered by the complete offscreen suite;
  they were not a third native-dialog run. Windows/macOS native Save dialogs
  remain unverified. This change does not make the two-file export crash-atomic.

Ignored local evidence: `artifacts/qt-save-final-{build,tests}.log` and
`artifacts/qt-save-native/validation.json`, traces, screenshots and exported files.

## Qt test-result publication race (2026-10-17)

The PR6 post-merge main run [38983420832](https://github.com/znbsf/ShowPsiSi/actions/runs/38983420832)
passed four jobs but failed Windows Qt's active-backend-death test with an empty
result JSON. The harness stopped the application as soon as the result path
existed; `QFile` creates that path before its buffered JSON is flushed. This is
a result-publication race, not evidence that the Save-dialog behavior failed.
The failure remains recorded rather than being replaced by a successful rerun.

All four Qt unittest result waiters and the retained CI smoke now use a shared,
bounded complete-JSON reader before stopping the producer. Original deadlines
and application assertions remain in force. Missing or persistently malformed
results fail with the last content and process state; complete non-object results
are rejected, and `passed: false` is returned to the existing failure assertion.
An observed producer exit triggers a final read in case its last flush raced the
previous read. Eight harness regressions cover these cases, including an actual
empty file followed by partial and complete writes. They are distinct from the
16 compiled Qt integration tests.

The initial PR7 head `6fcb13577678b06d146965464a1336f7fc3f4aa3` passed all five
jobs in [38990955608](https://github.com/znbsf/ShowPsiSi/actions/runs/38990955608),
including Windows TSDuck/TSCore 3.45 migration and all 16 native Qt tests. Its
Windows screenshots have readable text and populated native views. This initial
run predates the publication-reader correction; it is not acceptance evidence
for that correction. Windows native Save-dialog interaction remains unverified.

Correction validation in the Linux cloud workspace: the strict native runner's
retained real Qt smoke passed, followed by all **24 tests** (16 compiled Qt
integration scenarios plus eight publication-reader regressions), zero skips,
failures or errors. Evidence is retained locally in
`artifacts/sdk345-publication-strict/` and its sibling log. A first local attempt
omitted the extracted SDK's transitive SRT library path and was interrupted;
that loader/setup failure is excluded from acceptance. The successful run used
the documented explicit library paths. Fresh Windows CI is still required for
the correction itself.

### Final hosted acceptance (2026-10-17 UTC)

The pending Windows check above was subsequently completed. Final feature head
`70ed914d49bbe485befdfdead03ffced682f5bb2` passed all five jobs in
[run 38991403217](https://github.com/znbsf/ShowPsiSi/actions/runs/38991403217).
PR #7 merged as `e5793c77ebb23efec5ad661a598c507ca3490403`, and that exact merged
revision passed all five jobs in
[run 38991857522](https://github.com/znbsf/ShowPsiSi/actions/runs/38991857522).
The post-merge Linux and Windows Qt logs each report **24 tests passed**:
16 compiled native Qt integration scenarios and eight publication-reader
regressions, with no skips, failures or errors. This supersedes the pending-CI
status above without erasing the original failure or the initial-head boundary.

These hosted Qt checks use offscreen rendering. Windows native Save-dialog
interaction and WebView2 interaction remain unverified, as do macOS builds and
installers; successful Windows Tauri release compilation is not GUI acceptance.

## Local Windows Qt interaction tests (2026-10-20)

Scripted Qt tests (`tests/test_qt_*.py`) skip unless `SHOWPSISI_QT` names a built
`showpsisi-qt.exe`; a run that reports only skips is not a pass. On a developer
Windows machine, four separate environment causes produced "no result/trace"
failures that looked like application hangs:

1. Missing runtime DLLs. Without the Qt and TSDuck `bin` folders on `PATH`
   the process exits with `0xC0000135` before QML loads. `scripts/env.ps1` (or
   the same `PATH` entries) is required, plus `TSPLUGINS_PATH`.
2. Host write restriction on freshly built unsigned binaries. On one owner
   machine, the unsigned `showpsisi-qt.exe` could not create files outside the
   repository tree (`%TEMP%`, profile and Documents all failed, while signed
   tools could write there). Test results, traces and exports under the default
   temporary directory therefore never appeared. Pointing `TEMP`/`TMP` at an
   ignored repository folder such as `build\tmp` avoids it. This is a host
   policy observation, not an application defect, and must not be "fixed" by
   changing security settings.
3. Offscreen fonts. Without `QT_QPA_FONTDIR` (CI uses `%WINDIR%\Fonts`) text may
   render as missing glyphs, which invalidates screenshot evidence.
4. Non-UTF-8 console locale. On a GBK (Chinese) Windows locale,
   `test_protocol_presentation.py` decodes engine output with the locale codec
   and fails with `UnicodeDecodeError`; set `PYTHONUTF8=1` for local runs.

Build with `cmake --build build --target showpsisi-qt` in an MSVC environment,
then from the repository root set `PATH`, `TSPLUGINS_PATH`, `TEMP`/`TMP` and
`SHOWPSISI_QT` and run, for example,
`python -m unittest discover -s tests -p test_qt_ui.py`.
`scripts/ci/windows_native_checks.py --qt` lists the full Qt suite set. Local
passes do not replace the hosted `qt-native` job and do not establish
interactive Windows UI behaviour.
