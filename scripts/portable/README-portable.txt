ShowPsiSi Windows x64 Qt + core portable candidate

Extract the whole archive. Open Launch Qt.cmd or bin\showpsisi-qt.exe.
No Python, PowerShell 7, Qt/TSDuck SDK or compiler is needed to use this GUI.
Default prerequisite mode requires the Microsoft Visual C++ 2015-2022 x64
Redistributable v14 runtime >=14.51.36231 to be installed already. If Windows reports missing MSVCP140 or
VCRUNTIME140 DLLs, obtain the official x64 runtime from Microsoft:
https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist
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
Relocation and offscreen tests do not establish native Windows file-dialog,
GPU, desktop-interaction or clean-machine acceptance. Read validation evidence
for the exact source revision. Do not bypass Windows security warnings.
See LICENSE, THIRD_PARTY_NOTICES.txt, SOURCE_INFORMATION.txt and licenses/.
Qt shared libraries remain replaceable; preserve compatible ABI and plugins.
