# Linux native Tauri validation

Cloud-only validation on 2026-10-16 UTC. This is the compiled Tauri application using WebKitGTK and the real C++ engine, not the loopback browser adapter. No owner computer or device was used. Windows WebView2/macOS and OS browser launching remain untested for this revision.

## Build

Rust 1.99.1, locked Tauri 2.12.4, GTK 3.24.49 and WebKitGTK 2.52.6 on Debian 13. `cargo test --locked --manifest-path ui/tauri/src-tauri/Cargo.toml` passes the two reference-allowlist unit tests. `cargo build --locked` builds the debug application. The build exposed the missing default `icons/icon.png`; the repository now includes an original RGBA icon. Runtime reporting now identifies WebKitGTK/WKWebView/WebView2 according to platform.

Ordinary Linux setup needs the distribution's GTK/WebKitGTK development/runtime packages and the TSDuck dependencies. This cloud workspace instead extracted official Debian packages into ignored `.deps/native-root`, installed official Rust into `.deps/rust`, and set `PKG_CONFIG_SYSROOT_DIR` and `PKG_CONFIG_LIBDIR` for the extracted pkg-config files. No system-wide package installation is required for that route.

Debian's WebKitGTK helper paths are compiled under `/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1`. Setting `WEBKIT_EXEC_PATH` did not relocate this distribution build. A first launch therefore exited 133 with a missing WebKitNetworkProcess error. The successful cloud launch used bubblewrap to map the complete extracted library directory into that path in a disposable process mount namespace:

```sh
export SHOWPSISI_ROOT="$PWD" SHOWPSISI_AUTO=1
export LD_LIBRARY_PATH="$PWD/.deps/native-root/usr/lib/x86_64-linux-gnu:$PWD/.deps/tsduck/usr/lib:$PWD/.deps/tsduck/usr/lib/x86_64-linux-gnu"
export XDG_CACHE_HOME="$PWD/.deps/native-home/cache"
export XDG_DATA_HOME="$PWD/.deps/native-home/data"
export XDG_CONFIG_HOME="$PWD/.deps/native-home/config"
export WEBKIT_INJECTED_BUNDLE_PATH="$PWD/.deps/native-root/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/injected-bundle"
bwrap --ro-bind / / --dev-bind /dev /dev \
  --ro-bind "$PWD/.deps/native-root/usr/lib/x86_64-linux-gnu" /usr/lib/x86_64-linux-gnu \
  --bind "$PWD" "$PWD" \
  ./ui/tauri/src-tauri/target/debug/showpsisi-tauri
```

This preserves WebKit's sandbox. It changes neither host security settings nor host library files. The library mapping must include TSDuck's libusb, pcsclite, curl and rist dependencies; the initial incomplete mapping produced an accurately visible broken-pipe error. After completing dependencies and using writable workspace XDG directories, the successful runtime stderr was empty.

## Native interaction evidence

- Actual native workbench displayed six services, 18 distinct payloads, 2,495 section observations and the expected two CRC failures in the generated source.
- GTK Open File selected `samples/generated/lab.ts`; the application rescanned it.
- Native edit preview changed SID 103 from `Sports UHD` to `Native GTK Test`, SDT version 3 to 4, with recomputed CRC.
- GTK Save File exported a new `edited-si.ts` plus manifest: 404,200 bytes, 14 sections, 10 cycles. The test artifacts were then moved into ignored `artifacts/native-gtk-export.ts` and its manifest. The manifest preserves its original export destination.
- Independent native-core readback recovered the edited service and zero CRC errors.
- Repeating Save to the existing destination displayed GTK's replacement warning. Cancelling preserved both output hashes. This tests the native dialog's cancellation path; it does **not** claim that the warning's Replace branch was accepted. Backend no-overwrite and competing-writer tests are covered by the engine suite.
- Original source SHA-256 before and after: `528c8cd44e1289e8f1d3f59a457bb9247d1f9716df21a4f30c6c6d18cb37ff96`.
- Export SHA-256: `128984101c37eef93f55b550c03ee0ef5163f3950a1fe95a17a125938f9a51d9`; manifest SHA-256: `a2039b43748fa4bb4b6d2ef259a802c03f2369e4ea034ddbef09c22b62a2c2d0`.
- The app was closed normally after these checks; the launcher recorded exit code 0.

![Compiled Linux Tauri workbench using the real engine](images/tauri-linux-workbench.png)

Local build/test logs, trace milestones, export readback and hashes are in ignored validation artifacts. Negative URL tests exercise exact registry matching, rejection of non-HTTPS schemes and control characters without opening an external browser. These are not full standards-conformance or performance claims.

## Backend lifecycle and final build

The Rust bridge now emits `backend_exit` on stdout EOF/read failure, checks child exit before accepting a request, and reports `backend_alive` at boot. The Web UI rejects pending work, clears busy/loading state, disables backend-dependent actions and visibly requests an application restart. It does not restart the engine or retry edits automatically.

Controlled process fixtures verified both a child exiting three seconds into a pending analysis and a child exiting before the UI listener was installed. Both produced the disconnected state instead of hanging. These failure fixtures intentionally do not parse data; all positive analysis/export checks above used the real engine.

After the final embedded web-asset rebuild, the real engine successfully scanned the source again and the native screenshot was recaptured. Closing this final real-engine run returned exit code 0. Process snapshots verified that its Tauri process, core child, WebKitNetworkProcess and WebKitWebProcess were absent after exit; unrelated validation processes were left alone.

Final native executable SHA-256: `0d9ac8c4cce1695b93317509abd8bbbd4fe421d0239daf6f49abc2ec15a58e37`.
Rust source SHA-256: `e876188931b9cb9b0d8ff7495d79d581668099d4751d2c7de80eff1e8a1ba8ec`.
Embedded `app.js` SHA-256: `2175e3443d840077faa24e9110a236c480506a76ab5cf28ba496297f0e8b2d97`.
Machine-readable local evidence: `artifacts/native-tauri-validation.json`.
