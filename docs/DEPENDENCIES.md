# Dependency and source inventory

This project is a local prototype. Dependencies were not installed as system services and global proxy/tool configuration was not changed.

| Component | Version / source | Location and role |
| --- | --- | --- |
| TSDuck | 3.39-3956, pre-existing Windows developer SDK | `C:/Program Files/TSDuck`; linked by shared C++ engine |
| MSVC | 14.29.30133 / compiler 19.29.30154 | pre-existing VS 2019 Build Tools |
| Qt | 6.7.3 `win64_msvc2019_64` | `.deps/Qt`; official Qt archives via aqtinstall 3.3.0 |
| Rust | 1.99.1 (58cf8f9c3, 2026-10-13) | `.deps/rustup` + `.deps/cargo`; minimal profile, no PATH modification |
| Tauri | 2.12.4 | Cargo.lock; release build with embedded web assets |
| Tauri dialog | 2.8.3 | Cargo.lock; native file picker |
| WebView2 | 155.0.4283.45, system Evergreen runtime | pre-existing; actual executable path recorded per benchmark |
| nlohmann/json | 3.11.3 | `third_party/nlohmann`, MIT |
| Python | 3.12.3 | pre-existing; `.deps/py` virtual environment for aqt/psutil |

Rust bootstrap: `https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe`; publisher SHA-256 matched `6f4bef66261261fcb43131be8720bab817d403a09edec7455c371974b90bdb7e` before execution. Compiler components subsequently verified by rustup. Crate versions/checksums are recorded in Cargo.lock.

Vendored JSON header: `https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp`; locally recorded SHA-256 `9bea4c8066ef4a1c206b2be5a36302f8926f7fdc6087af5d20b417d0cf103ea6`. Its `LICENSE.MIT` accompanies the header. This is an identity record, not a claim of independent publisher checksum verification.

TSDuck license is BSD-2-Clause: [official license](https://tsduck.io/license). Qt modules have their own license terms: [Qt licensing documentation](https://doc.qt.io/qt-6/licensing.html). Tauri and its dependencies retain their own licenses. No installer or redistribution license audit has been completed; local runtime size staging is not a release package.

The official sample recordings are separately sourced data, not our own source code; they are excluded from source distribution. See `samples/real/provenance.json`.
