# Dependency and source inventory

This project is a local prototype. Dependencies were not installed as system services and global proxy/tool configuration was not changed.

| Component | Version / source | Location and role |
| --- | --- | --- |
| TSDuck + TSCore | 3.45-4798, official matching runtime and developer SDK | Windows: `.deps/TSDuck-3.45-4798`; Linux: installed or workspace-extracted SDK; both libraries linked by shared C++ engine |
| C++ toolchain | C++20; Visual Studio 2022 or GCC 13+ | Windows scripts discover VS 2022 C++ x64 tools with `vswhere`; Linux CI uses Ubuntu 24.04 |
| Qt | 6.7.3 `win64_msvc2019_64` | `.deps/Qt`; official Qt archives via aqtinstall 3.3.0 |
| Rust | 1.99.1 (58cf8f9c3, 2026-10-13) | `.deps/rustup` + `.deps/cargo`; minimal profile, no PATH modification |
| Tauri | 2.12.4 | Cargo.lock; release build with embedded web assets |
| Tauri dialog | 2.8.3 | Cargo.lock; native file picker |
| WebView2 | 155.0.4283.45, system Evergreen runtime | pre-existing; actual executable path recorded per benchmark |
| nlohmann/json | 3.11.3 | `third_party/nlohmann`, MIT |
| Python | 3.12.3 | pre-existing; `.deps/py` virtual environment for aqt/psutil |

## TSDuck 3.45 migration

The application now requires TSDuck **3.45-4798** and its split **TSCore** library.
The former VS 2019 / C++17 / TSDuck 3.39 build combination is historical and is
not supported by this build route. Qt remains the official **6.7.3
`win64_msvc2019_64`** kit: the kit name does not change when compiling the
application with VS 2022's compatible newer MSVC toolchain.

Windows prerequisites are PowerShell 7, VS 2022 C++ x64 tools with Windows SDK,
CMake/Ninja, Python and 7-Zip on PATH. `scripts/setup-deps.ps1` now calls
`scripts/setup-tsduck.ps1`, which downloads and verifies the pinned NSIS archive,
then extracts only its SDK/runtime payload into the workspace. It **does not
execute the installer**, write the registry or modify the global PATH. The
runtime-only portable ZIP is insufficient for compilation. An existing matching
SDK can be selected through process-local `TSDUCK_ROOT`; `scripts/env.ps1`
validates it and fails clearly on missing split files or the wrong version.

The two include directories are `include/tsduck` and `include/tscore`;
`tsVersion.h` belongs to TSCore. Windows links `lib/Release-Win64/tsduck.lib` and
`tscore.lib`, with both corresponding DLLs deployed beside the engine. XML
models and `.names` files from both libraries must also be deployed, including
`tsduck.tables.model.xml`, `tsduck.dtv.names`, `tscore.time.xml` and
`tscore.ip.names`. On Linux both shared libraries and their transitive runtime
dependencies must be available; official package data lives under
`usr/share/tsduck`, including TSCore data. Do not mix SDK headers, import/shared
libraries, runtime DLLs or data from different releases.

Pinned files from the [official 3.45-4798 release](https://github.com/tsduck/tsduck/releases/tag/v3.45-4798):

| Official asset | SHA-256 |
| --- | --- |
| `tsduck_3.45-4798.ubuntu24_amd64.deb` | `0023689f76e75b64e45253771208bcf8ca95b91fbfd0900da097c729f3c39fde` |
| `tsduck-dev_3.45-4798.ubuntu24_amd64.deb` | `0bfbec4234065bbabd42271b87d8f61f5f1b5169c31e797a2f5952fa736192c2` |
| `TSDuck-Win64-3.45-4798.exe` | `d1d1dae29e82d9c9dde8380fd562d2995e6cb702706031fa9574ebc06092bc57` |

These are downloaded-asset identity records, independently rechecked against the
bytes used for this migration, not a publisher-signature claim. Linux CI verifies
both hashes before package installation; Windows verifies before extraction.
Windows also checks split headers, exact header version, matching SDK DLL copies
and staged runtime/data hashes. The strict native suite probes the real engines
and exercises SDK runtime consistency and Unicode filesystem paths.

Local PowerShell syntax/SDK validation and archive inspection do not establish a
Windows build or UI pass. The five-job hosted workflow remains the platform
validation gate; Windows WebView2 interaction and installers remain separate.

## Other source identities and licenses

Rust bootstrap: `https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe`; publisher SHA-256 matched `6f4bef66261261fcb43131be8720bab817d403a09edec7455c371974b90bdb7e` before execution. Compiler components subsequently verified by rustup. Crate versions/checksums are recorded in Cargo.lock.

Vendored JSON header: `https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp`; locally recorded SHA-256 `9bea4c8066ef4a1c206b2be5a36302f8926f7fdc6087af5d20b417d0cf103ea6`. Its `LICENSE.MIT` accompanies the header. This is an identity record, not a claim of independent publisher checksum verification.

TSDuck license is BSD-2-Clause: [official license](https://tsduck.io/license). Qt modules have their own license terms: [Qt licensing documentation](https://doc.qt.io/qt-6/licensing.html). Tauri and its dependencies retain their own licenses. No installer or redistribution license audit has been completed; local runtime size staging is not a release package.

The official sample recordings are separately sourced data, not our own source code; they are excluded from source distribution. See `samples/real/provenance.json`.
