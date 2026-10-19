# Portable Windows distribution feasibility

## Current app-local / paired-source candidate (2026-10-19)

The current implementation stages the five exact Microsoft release x64 DLLs
14.51.36247.0 beside the executables, checks all normal/delay imports and requires
native evidence that Qt/core loaded their own required subsets from package bin.
It does not install/elevate a shared runtime. The engineering distribution review for this exact inventory is complete on the
[hosted-runner basis](PORTABLE_LICENSE_REVIEW.md#hosted-runner-distribution-basis).
Native Windows/final payload gates remain mandatory; this is not a legal guarantee.

Large Qt sources move to `ShowPsiSi-VERSION-corresponding-source.zip` on the same
release, using LGPLv3/GPLv3 section6(d) network source access. Small licenses,
notices, source-index, build features, replacement instructions and exact generated
`SOURCE_DOWNLOAD.txt` remain in both binaries. Exact original source archives stay
in the reviewed inventory and are rehashed inside the paired asset. Archive,
installer and publisher gates reject absent/mismatched source delivery. Source
upload/readback precedes public publication; old matching source must remain
available with old binaries. The automatic GitHub app-source ZIP is not a substitute.

Native Windows app-local build/install/launcher/load-path tests and clean-machine
offline acceptance are not inferred from Linux helper tests. See
[Windows acceptance](WINDOWS_APPLOCAL_ACCEPTANCE.md) and [installer pipeline](WINDOWS_INSTALLER.md).
The records below describe the prior prerequisite/in-package-source checkpoint
and remain historical evidence where that older layout is mentioned.

## Historical prerequisite-mode checkpoint

Audit: 2026-10-16 UTC. This is a packaging plan, not a built distribution,
redistribution clearance, release approval or Windows desktop acceptance result.
No release or installer was created by this audit. Work used the assistant's
cloud workspace and read-only upstream/CI evidence; no owner computer was used.

## Conclusion and verified gaps

A Windows x64 ZIP containing the shared engine and both frontends is technically
feasible. Qt is the smaller first offline-runtime target; Tauri additionally
needs WebView2. The existing build outputs are not standalone distributions.

- `ui/qt/main.cpp` and `ui/tauri/src-tauri/src/main.rs` default their resource root
  to the current working directory and look for the engine in `build/bin`.
  The core itself needs `api/tools.json` under its `--root` directory.
- `Launch Qt.cmd` / `Launch Tauri.cmd` require `pwsh.exe`. `scripts/run.ps1`
  assumes a source checkout, `.deps/Qt`, and development build locations.
- `scripts/ci/windows.ps1` deploys Qt with `--no-compiler-runtime`, then tests with
  Qt and TSDuck SDK directories on `PATH`. A successful hosted run can therefore
  depend on runtime files already installed on the runner.
- In [PR #4's retained run](https://github.com/znbsf/ShowPsiSi/actions/runs/38976742240),
  `dumpbin /DEPENDENTS` shows `showpsisi-core.exe`, `showpsisi-qt.exe` and
  `tsduck.dll` importing `MSVCP140.dll`, `VCRUNTIME140.dll` and
  `VCRUNTIME140_1.dll`. `Qt6Core.dll` also imports `MSVCP140_1.dll`.
  The inspected `tsduck.dll` has no additional non-Windows/non-CRT DLL imports.
  This is baseline import evidence, not a complete final dependency closure or
  proof that optional dynamic loads are absent.
- Qt's audited Export button writes to `root/artifacts`; read-only installation
  locations cannot support that default. **A Qt Save-dialog fix is in progress**
  in the current development work. It is not yet accepted by this audit.
- The project does not yet assemble a complete runtime-license inventory,
  required notices or corresponding-source provision for a distribution.

## Proposed runtime layout

```text
ShowPsiSi-windows-x64/
  Launch Qt.cmd
  Launch Tauri.cmd
  README-portable.txt
  LICENSE
  THIRD_PARTY_NOTICES.txt
  SOURCE_INFORMATION.txt
  manifest.json
  bin/
    showpsisi-core.exe
    showpsisi-qt.exe
    showpsisi-tauri.exe
    tsduck.dll
    Qt runtime DLLs and any eligible app-local CRT files
    qt.conf
    platforms/qwindows.dll
    QML modules and plugins selected by windeployqt
    TSDuck XML and names files
  api/tools.json
  extensions/demo.json
  references/standards.json
  samples/generated/lab.ts
  samples/generated/lab.manifest.json
  licenses/
```

The synthetic sample is optional if startup instead presents an empty workspace;
do not leave a default sample path pointing to a missing file. No Python, Rust,
Node, compiler or SDK installation should be required for the GUI/JSONL bundle.
An independently usable MCP adapter would need its own Python/runtime decision;
including its scripts alone does not make MCP self-contained.

Keep all 17 XML/names files from the pinned TSDuck 3.39-3956 runtime initially
(approximately 1 MB): the `dektec`, `dtv`, `hides`, `ip` and `oui` names files;
the `channels`, `etuner`, `keytable` and `tables` model XML files; and the
`hfbands`, `lnbs`, `monitor` and `time` XML/model pairs. In particular, missing
`tsduck.tables.model.xml` or `tsduck.dtv.names` can break decoding despite a
successful process start. The pinned SDK's `SearchConfigurationFile` declaration
documents executable-directory lookup. The [upstream portable builder](https://github.com/tsduck/tsduck/blob/v3.39-3956/pkg/nsis/build-installer.ps1)
also preserves XML/names data. This conservative set is not a claim that every
file is exercised by current application tests.

Use the pinned Qt 6.7.3 `windeployqt --release --qmldir ...` against the actual
QML source, preserving its recursive runtime/plugin/QML output and a file
manifest. The application's own QML and Tauri web assets are embedded in their
executables. Do not guess a flat Qt DLL list or copy the entire SDK.
[Qt's deployment guidance](https://doc.qt.io/qt-6/windows-deployment.html) explains
the deployment scanner and the separate responsibility for non-Qt libraries.

Exclude SDK headers/import libraries, developer tools, test-only core binaries,
build caches, test profiles, separately sourced real recordings and standards
PDFs. Record the exact source commit, toolchain, dependency versions, original
download identities and every distributed file's SHA-256 in `manifest.json`.

## Launcher and resource changes

1. Add an explicit-input staging script, for example
   `scripts/package-windows.ps1`, with required-file checks and a clean output
   directory. It must stage production artifacts from the same source commit.
2. Resolve packaged resources relative to the executable, with validated
   development overrides. Direct EXE launch should work without a shell wrapper
   or the original checkout. Keep the core's explicit `--root` contract.
3. Package-specific CMD launchers can use their own absolute directory, quoted
   paths and disabled delayed expansion. Use process-local environment only;
   no PowerShell 7 requirement, elevation, automatic dependency installation,
   global PATH changes or security-policy changes. Do not inherit test-driver
   settings into ordinary launches.
4. Separate immutable application resources from writable exports, logs and
   profiles. Document whether "portable" means no installation or also means
   self-contained settings: current Qt settings and Tauri browser storage do
   not establish the latter. Finish and test the Qt Save-dialog work separately.
5. Add relocation/package tests and a CI artifact step. Creating a CI artifact
   must not automatically publish a GitHub release or installer.

## License, source and runtime prerequisites

These are requirements to investigate and satisfy, not blanket legal assurances.

- **Project and JSON:** retain the project's MIT `LICENSE` and
  `third_party/nlohmann/LICENSE.MIT`, including their copyright notices.
- **TSDuck:** its BSD-2-Clause license permits binary redistribution with the
  required notices. Preserve the pinned `LICENSE.txt` and [OTHERS.txt](https://github.com/tsduck/tsduck/blob/v3.39-3956/OTHERS.txt).
  The latter covers DTAPI, SRT/MPL-2.0, RIST and VATek. Determine what the exact
  distributed binary contains, including statically incorporated components,
  and satisfy any covered-source availability obligations. A DLL import list
  cannot settle that question. See the [TSDuck license](https://tsduck.io/tsduck-license/)
  and [MPL 2.0](https://www.mozilla.org/en-US/MPL/2.0/).
- **Qt:** audit the actual 6.7.3 modules/plugins and their third-party code.
  For the LGPL route, provide the relevant license texts, prominent notice,
  complete corresponding library sources or an appropriate source-provision
  mechanism, and preserve users' ability to replace/relink the libraries.
  Dynamic linking helps but is not sufficient by itself. Avoid distributing
  unrelated GPL-only tools/modules. [Qt's LGPL guidance](https://www.qt.io/development/open-source-lgpl-obligations)
  describes these obligations; [Qt licensing](https://doc.qt.io/qt-6/licensing.html)
  notes module-specific and third-party terms. Current online documentation is
  not an inventory of the pinned 6.7.3 binary package.
- **Tauri/Rust:** cached licenses for Tauri 2.12.4 and dialog 2.8.3 offer MIT;
  their transitive crates retain their own licenses. Generate and review an
  inventory for the actual Windows target and linked features, with applicable
  notices/source provisions. The audit found 133 uncached package manifests in
  the all-platform lockfile; that count neither identifies shipped packages nor
  proves a violation. A complete Windows redistribution review is still open.
- **VC runtime:** Microsoft allows app-local redistributable DLL deployment
  subject to the applicable Visual Studio terms and REDIST list. Verify the
  distributor's rights and exact files; use eligible release redistributables,
  not arbitrary System32/developer/debug DLL copies. Central runtime deployment
  has servicing advantages, but requires an installation prerequisite rather
  than a fully self-contained ZIP. See [Microsoft redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
  and the [VS 2022 REDIST list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution).
- **WebView2:** Tauri needs the WebView2 Runtime even though its HTML/CSS/JS are
  embedded. Check and explain a missing runtime without silently installing it.
  Bundling Fixed Version requires a separate runtime/terms inventory and an
  update-servicing plan; it is not part of the minimal proposal. See [Microsoft's
  distribution guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)
  and [Tauri Windows runtime options](https://v2.tauri.app/distribute/windows-installer/).

## Acceptance gates

- Extract the ZIP outside the checkout into paths containing spaces and Unicode.
  Launch from an unrelated directory with SDK PATH entries and Qt/SHOWPSISI
  overrides removed. Test direct EXE launch as well as both launchers.
- Check recursive PE dependencies, final architecture and DLL load locations.
  No process may silently use the original Qt/TSDuck SDK. A VS-equipped hosted
  runner alone cannot prove absence of an undeclared system CRT prerequisite;
  require a suitable clean Windows environment before claiming that property.
- Exercise the packaged core: capabilities, fixture analysis, six services,
  named/XML decoding, raw evidence, A/B comparison, rename/export/readback,
  source hash preservation, cancellation/rescan and clean shutdown.
- Fail clearly for missing core/schema/model files and unwritable output.
  Verify exports work when the application directory is read-only. Ensure the
  archive contains no test-gated engine or test-driver configuration.
- Run compiled Qt offscreen smoke/regressions using only the staged runtime;
  retain fresh screenshot, trace and results. Keep any offscreen-only test
  plugin outside the shipped archive, or explicitly inventory it if retained.
  This verifies relocated software-rendered Qt behavior, not Windows native
  dialogs, GPU rendering or desktop interaction.
- Separately exercise Windows native Qt and Tauri/WebView2 launch, file picking,
  save/cancel, overwrite protection, layout persistence, cancellation/rescan,
  backend failure and exit cleanup. Retain actual runtime evidence. These
  Windows native interaction gates remain unverified by this audit.
- Check all license texts, notices, source provision, runtime prerequisites,
  component identities and final manifest before distribution. A green build,
  successful ZIP creation or Qt offscreen pass is not sufficient release proof.

Public release publication and signing are separate decisions after the relevant
gates pass. Existing Windows Tauri evidence is compilation/Rust-test evidence;
neither Linux native Tauri nor Chromium tests establish Windows WebView2 behavior.
