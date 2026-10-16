# Cloud validation record

Date: 2026-10-16 UTC. Base: `a79ce16ff04e7f418c366db247eb6afce11b495a`.

## Evidence

- GCC 14.2 compiled the C++17 engine against official TSDuck 3.39-3956 Linux SDK.
- CMake built native Qt 6.7.3 with Quick/QuickControls2. Qt smoke used the compiled
  C++ bridge and backend, offscreen software rendering, and real control events.
- 22 engine, 7 protocol, 3 HTTP bridge, 8 browser and 2 native Qt tests passed.
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

Native Tauri build, native file dialogs, OS external-browser commands, new Windows
builds and macOS are not verified by browser tests. Linux software-rendered Qt is
not a GPU-performance test. A decoder's registry entry does not establish every
standard edition or operator variation is supported. See PROTOCOL_COVERAGE.md.
