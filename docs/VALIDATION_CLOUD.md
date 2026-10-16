# Cloud validation record

Date: 2026-10-16 UTC. Base: `a79ce16ff04e7f418c366db247eb6afce11b495a`.

## Evidence

- GCC 14.2 compiled the C++17 engine against official TSDuck 3.39-3956 Linux SDK.
- CMake built native Qt 6.7.3 with Quick/QuickControls2. Qt smoke used the compiled
  C++ bridge and backend, offscreen software rendering, and real control events.
- 25 engine, 9 protocol, 4 HTTP bridge, 10 browser, 4 native Qt and 2 Rust tests passed (54 total).
- UHF22 sample SHA-256: `24143de80d28461d084dfb75279da520f335de36b7c35f6398ed6d510daa5937`.
- `docs/images/qt-workbench.png` is native Qt; `web-workbench.png` and
  `web-references.png` are Chromium with the real C++ engine. They are not mockups
  or evidence that the native Tauri shell was run.
- Source preservation, no-overwrite, concurrent export, invalid inputs, incomplete
  tables, extension isolation, private namespaces and context reset have explicit tests.

Run commands are in `tests/README.md`, `scripts/check.sh` and
`docs/CLOUD_DEVELOPMENT.md`. Logs and temporary generated data remain ignored.

## Environment issues and resolutions

1. The direct command sandbox could not launch Chromium (socket restriction), and
   its escalation wrapper failed before launch. The documented cloud desktop
   Terminal ran the same Playwright tests successfully. The owner's desktop was
   never substituted. A cloud browser's loopback could not reach the sandbox's
   listener; launching the loopback-only server on the cloud desktop resolved it.
2. aqt's multiprocessing IPC could not run in the sandbox. Its dry-run manifest
   supplied official Qt archive URLs; those archives were downloaded/extracted
   into the workspace. No security setting or global environment was changed.
3. Extracted native SDKs required local library paths (including SRT and ICU) and
   OpenGL development headers. CMake now supports a Linux TSDUCK_ROOT.
4. Git CLI has no authenticated push credentials here. Repository updates use the
   user's authenticated GitHub connector, without copying tokens to the workspace.

## Remaining validation boundaries

Native Linux Tauri was separately built and exercised, including GTK file dialogs and export/readback; see NATIVE_TAURI_VALIDATION.md. At that checkpoint, OS external-browser launching, new Windows builds and macOS remained unverified; see the continued loop below for later results. Linux software-rendered Qt is
not a GPU-performance test. A decoder's registry entry does not establish every
standard edition or operator variation is supported. See PROTOCOL_COVERAGE.md.

## Second review loop

Added Qt search parity and PlainText enforcement for stream-derived labels and tooltips, with a real encoded markup fixture and HTTP trap. Historical native-tree assembly now accepts a packet cutoff and rejects future/superseded evidence. Native/backend EOF settles pending requests and disables disconnected actions; regular-file guards prevent named pipes/devices from hanging analysis. Native Tauri's missing default PNG icon was fixed and the locked Linux build/runtime verified.

The first remote CI run passed at commit `9a8d6a8`. The workflow now also builds/tests native Qt and the Tauri shell; its final status must be checked on the newest PR commit.


## Continued loop after PR #1 merge

Baseline PR #1 merged as `ac039f6`; its post-merge CI run
[38972133391](https://github.com/znbsf/ShowPsiSi/actions/runs/38972133391)
passed all three Linux jobs. Development continued on
`feat/protocol-robustness-next` rather than treating a passing PR as completion.

New core regressions verify reused version generations, unchanged payload recurrence,
multiple versions completing in one TS packet, conflicting current/next evidence,
network identities and canonical service projection. Protocol fixtures also cover
continuity interruption/recovery, duplicate packets, nonzero pointer fields, DVB
HEVC/AC-4/AIT, ATSC captions/advisories, ISDB delivery and SCTE-35.

The new read-only `diff_snapshots` path was independently rerun with 30 engine and
26 protocol tests. Five HTTP bridge tests pass. Browser and native Qt tests cover
persistent layouts, invalid settings, comparison-side cutoffs, restored navigation,
pagination, retry and failure handling. Exact consolidated counts are in STATUS.md.

Windows CI is tracked separately in PR #2. Initial hosted Windows runs successfully
compiled MSVC engine/Qt and passed four baseline Qt tests and a retained native
smoke. They exposed a long/short-path identity assertion and platform-dependent
TSDuck native dispatch. Captured Windows trees were the correct MGT/TVCT, whereas
the contradictory-context Linux fixture used a generic fallback. Portable tests
now require exact raw bytes and expected native semantics or explicit raw fallback;
unrelated ISDB interpretations remain failures. All four jobs passed at PR #2 final head `95c7936` in run 38974640106.
A retained PNG exposed missing fonts despite functional tests passing; the
process-local Windows font path and missing-font diagnostic guard were added.
The final retained screenshot was inspected and readable. PR #2 merged as
`beb2e57`. This verifies its baseline suite, not subsequent feature changes.
Offscreen Qt does not test dialogs or WebView2.


Final continued-loop local total: **92 automated tests** (30 engine, 26 protocol,
5 bridge, 16 Chromium/native-engine, 8 compiled Qt, 7 Rust). The parent independently
reran engine/protocol/bridge/Qt via `scripts/check.sh`; all passed. Native Tauri
comparison/layout was operated on the final embedded assets. Actual xdg-open
returned exit 4 (`gio: Operation not supported`); the old fire-and-forget call
hid this failure. The new checked asynchronous helper surfaces bounded diagnostics
and an honest timeout, without killing a browser. Actual native Copy URL cleared
the failure; no successful OS browser navigation is claimed.
