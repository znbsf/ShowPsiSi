# Cloud development and validation

This work is performed in a Linux cloud workspace, not on the owner's Windows PC or television. Windows prototype evidence in `STATUS.md` is historical; it does not validate the new UI build.

## Build the shared engine

Install the TSDuck **3.39-3956 developer SDK**, a C++17 compiler and CMake >=3.22. The SDK can be installed normally or extracted into a workspace directory. Do not put SDKs, generated streams or build products in Git.

```sh
cmake -S . -B build -DBUILD_QT_UI=OFF -DTSDUCK_ROOT=/path/to/tsduck/usr
cmake --build build --parallel 4
python scripts/make_fixture.py
python -m unittest discover -s tests -p test_engine.py -v
```

When using extracted Linux packages, add their library directories to `LD_LIBRARY_PATH`, including transitive dependencies (the development session needed `libsrt.so.1.5`). `SHOWPSISI_CORE` overrides the executable path for Python clients and test helpers. No global installation or proxy change is required.

For Qt, supply `CMAKE_PREFIX_PATH` pointing to a Qt >=6.5 SDK with Quick and QuickControls2, enable `BUILD_QT_UI`, and install OpenGL development dependencies. This development session uses Qt **6.7.3**. For headless tests use `QT_QPA_PLATFORM=offscreen` and `QT_QUICK_BACKEND=software`; this verifies software-rendered UI, not GPU performance or native desktop integration.

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
