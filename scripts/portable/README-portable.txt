ShowPsiSi Windows x64 Qt + core portable candidate

Requires Windows 10 version 1809 (build 17763) or newer, or Windows 11, native x64,
with its system D3Dcompiler_47.dll. ARM64 emulation is not validated.
Extract the whole archive into a writable folder. Open Launch Qt.cmd.
No Python, PowerShell 7, Qt/TSDuck SDK or compiler is needed to use this GUI.
Launch Qt.cmd uses inbox 64-bit Windows PowerShell for a read-only prerequisite
check. It does not change ExecutionPolicy or any system settings. Missing/old
runtime or a check failure is explained before Qt starts. Directly opening
bin\showpsisi-qt.exe bypasses that preflight and may show a Windows DLL error.
Default prerequisite mode requires the Microsoft Visual C++ 2015-2022 x64
Redistributable v14 runtime >=14.51.36231.0 to be installed already. If needed,
review and install the official x64 runtime yourself from Microsoft:
https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
This package never downloads or installs that runtime automatically.
See build-information.json crt_mode: Prerequisite excludes VC DLLs; AppLocal
includes separately reviewed release VC DLLs. Neither mode installs an SDK.
Keep bin, api, extensions and references together. The bundled synthetic lab.ts
contains six services and intentional malformed signalling; it has no media.
Use Browse to open your own transport stream. Exports go to the location you
choose with Save, never automatically into the installation directory.

Portable means no installer. Qt settings may be stored in your Windows user
profile/registry; this is not a promise of zero writes outside the extracted tree.
For an explicit settings file, developers can set SHOWPSISI_SETTINGS_PATH.
Resource and backend development overrides must be absolute paths. The CMD
launcher clears SHOWPSISI_* and SDK/plugin discovery overrides. Direct EXE
launch also clears SHOWPSISI_* settings. Developers must explicitly launch with
--showpsisi-development to honor trusted local development/test overrides.

Included: Qt Quick frontend, production C++ engine, runtime DLLs/data, synthetic
sample, component notices/source information and SHA-256 inventory.
Excluded: Tauri/WebView2, Python MCP adapter, SDKs, compilers and test helper.
Tauri requires a separate WebView2 runtime decision and is not in this package.

This is an unsigned CI candidate, not a published release or installer.
Release asset name: ShowPsiSi-VERSION-windows-x64-portable.zip. Check its SHA-256
against SHA256SUMS from the same official GitHub release before extraction.
About / Updates can check versions and direct you to the official portable ZIP;
it never migrates a portable copy to Setup. For an update, close every ShowPsiSi
window/core process, extract the new ZIP into a new folder and keep the old folder
until the new copy works. Do not overwrite a running app. Keep your own exports.
Relocation and offscreen tests do not establish native Windows file-dialog,
GPU, desktop-interaction or clean-machine acceptance. Read validation evidence
for the exact source revision. Do not bypass Windows security warnings.
See LICENSE, THIRD_PARTY_NOTICES.txt, SOURCE_INFORMATION.txt and licenses/.
Qt shared libraries remain replaceable; preserve compatible ABI and plugins.
