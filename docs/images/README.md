# UI validation screenshots

- `web-workbench.png`: current web UI, real native-engine analysis of the deterministic lab transport stream, selected service and descriptor tree.
- `web-references.png`: current web UI, DVB standards context, mapped official specification reference with revision/access scope.

Captured in headless Chromium on the cloud computer by `tests/test_web_ui.py`.
The header labels this **CLOUD PREVIEW · REAL ENGINE**. These are live-engine
browser integration captures, not mock results, and not native Tauri/WebView2
screenshots. Native file dialogs and native window behavior require separate
platform testing. Reference links were inspected but not opened.

Additional 1100 px, 900 px, and 520 px responsive captures are generated under
`artifacts/web-ui-tests/` by the same test suite.

- `qt-workbench.png`: compiled native Qt, software-rendered cloud screenshot; includes record/field search.
- `tauri-linux-workbench.png`: compiled native Tauri/WebKitGTK, real engine, actual cloud app window. Native file-dialog/export evidence is in ../NATIVE_TAURI_VALIDATION.md.
