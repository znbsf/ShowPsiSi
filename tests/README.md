# Validation

All tests use the real native JSONL engine. Build `showpsisi-core` first and make
TSDuck's runtime libraries available to the dynamic loader. `SHOWPSISI_CORE` can
select an alternate executable; otherwise `build/bin/showpsisi-core` (or `.exe`)
is used.

```sh
python -m unittest discover -s tests -p test_engine.py -v
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
