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

- `qt-comparison.png`: current compiled Qt A/B comparison with packet-bound evidence; software-rendered native test capture. The populated1000×680 companion and interaction JSON remain in ignored validation artifacts.
- `web-comparison.png`: current Chromium/native-engine A/B comparison. It is not evidence of native Tauri.
- The refreshed `tauri-linux-workbench.png` shows the actual compiled Linux Tauri comparison. Native reference-launch failure and successful Copy URL were also exercised; successful OS browser navigation is not claimed.
