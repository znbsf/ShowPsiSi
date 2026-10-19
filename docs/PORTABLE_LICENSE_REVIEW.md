# Windows Qt/core portable license and source review

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

## Hosted-runner distribution basis

The [runner team's confirmation](https://github.com/actions/runner-images/issues/12945#issuecomment-3348002951)
states that GitHub-hosted Windows builds use licensed Visual Studio Enterprise
without requiring each user to maintain a personal license.
[Microsoft's VS2022 REDIST list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution#visual-c-runtime-files)
permits the listed unmodified runtime files subject to Visual Studio license terms.

Applying those ordinary redistribution terms to this hosted build is an explicit
engineering inference. The private Microsoft/GitHub agreement is not quoted or
independently verified. This review covers the exact pinned release DLLs and
notices only; it is not a legal guarantee, acceptance of new terms, or Release
publication approval. Final native Windows and payload identity checks remain
required. App-local security servicing requires a reviewed application update.

## Historical prerequisite-mode checkpoint

Audit date: 2026-10-17 UTC. Scope: first Windows x64 **Qt + shared core**
portable CI candidate, Qt 6.7.3 `msvc2019_64`, TSDuck/TSCore 3.45-4798,
Microsoft v14 runtime prerequisite (app-local redistribution is optional). Tauri, Rust, WebView2, installer, signing and public
release are excluded. This is an engineering inventory and fail-closed gate,
not legal clearance. Staging and testing may proceed; **redistributable binary
artifact upload remains blocked** until the unresolved items below are closed.
A CI artifact accessible to others must not be assumed exempt from distribution
obligations simply because it is not a GitHub Release.

## Verified inputs and remaining boundary

- Repository `LICENSE`: MIT, copyright 2026 ShowPsiSi contributors.
- Vendored `third_party/nlohmann/json.hpp`: 3.11.3; accompanying `LICENSE.MIT`
  carries Niels Lohmann's notice. Preserve both project and JSON license texts
  as supplied, rather than substituting generic MIT text.
- Official [TSDuck release](https://github.com/tsduck/tsduck/releases/tag/v3.45-4798)
  installer asset was downloaded, **not executed**, and independently hashed:
  `d1d1dae29e82d9c9dde8380fd562d2995e6cb702706031fa9574ebc06092bc57`.
- The same release's official Portable ZIP was inspected without execution.
  Its `tsduck.dll` SHA-256 is
  `23bdf430032084017fadfdea150ebfad21a902187e083d10b355298b1ebcc27a`;
  `tscore.dll` is
  `3b5245650338b3098b3dee57ba75e6eeb6bec9d54d5abeca8a5859860064e371`.
  Compare SDK-extracted DLLs with these; this audit did not extract the NSIS
  payload and does not assume the files are identical merely from version.
- PE imports of those two DLLs show Windows libraries, VC runtime and, for
  `tsduck.dll`, `tscore.dll`. This is **not** a statically linked dependency
  inventory. The binary contains libRIST `v0.2.20` and VATek strings; `1.5.7`
  is the SRT compatibility version. The follow-up build-log audit below identifies
  the actual implementation as Robotweax SRT 0.2.4, not Haivision 1.5.7.
- Initial preparation preceded Windows staging. The hosted reconciliations at
  the end of this document now record the actual deployed inventory, source
  delivery and runtime evidence. App-local VC redistribution is not selected.
  Native interactive desktop acceptance remains separate and unverified.

## Required package materials

The packaging worker owns these generated files; this document does not create
placeholder notices that could be mistaken for complete redistribution material.

| File | Required content |
| --- | --- |
| `LICENSE` | Exact project MIT license |
| `THIRD_PARTY_NOTICES.txt` | Component/version/license, copyright and notice location for every shipped component, including code embedded inside DLLs; prominent Qt LGPL notice |
| `SOURCE_INFORMATION.txt` | Exact covered-source versions, retrieval location, hashes, modification/build information, selected source-provision mechanism and library replacement instructions; no promise that has not been implemented |
| `licenses/nlohmann-LICENSE.MIT` | Existing vendored license |
| `licenses/tsduck/LICENSE.txt`, `OTHERS.txt` | Exact 3.45-4798 documents, not 3.39 copies |
| `licenses/tsduck/Small-Deflate.txt` | Full selected license and copyright from the pinned embedded sources, not only OTHERS' abbreviated entry |
| `licenses/qt/` | Qt GPLv3 and LGPLv3 texts; relevant module and third-party copyright notices and full applicable texts |
| `licenses/runtime/` | Applicable distributor-provided notice/license material for eligible VC/runtime and any other non-Qt runtime files |
| `redistribution-review.json` | Explicit incomplete/complete status, exact inventory binding, component coverage and source/notice evidence; initially incomplete |

### TSDuck / TSCore details

Use the pinned [LICENSE.txt](https://github.com/tsduck/tsduck/blob/v3.45-4798/LICENSE.txt)
and [OTHERS.txt](https://github.com/tsduck/tsduck/blob/v3.45-4798/OTHERS.txt).
The BSD-2-Clause notices cover the core project, not every dependency by themselves.

The 3.45 split changes the previous audit's assumptions:

- TSCore embeds Small Deflate. Its full MIT/Unlicense alternatives and local
  changes are in `src/libtscore/zip/private/sdefl.h` and `sinfl.h`; preserve
  the full selected notice. OTHERS only names the MIT alternative and author,
  so it is insufficient as the sole MIT license copy.
- DTAPI integration is in optional `tsdektec.dll`, not unconditionally inside
  `tsduck.dll`: see [tsDektecSupport.h](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dektec/tsDektecSupport.h).
  Do not stage `tsdektec.dll`, plugins or hardware tools just because they
  exist in the SDK. Retaining the complete upstream OTHERS is reasonable, but
  label it as upstream notices rather than claiming all listed code is shipped.
- [tsduckdll.vcxproj](https://github.com/tsduck/tsduck/blob/v3.45-4798/scripts/msvc/tsduckdll.vcxproj)
  imports RIST, SRT and VATek property sheets. The pinned RIST/VATek sheets
  reference static libraries. Their code may be shipped even without separate
  DLLs and even if this app never calls the transport/hardware API.
- The source-level SRT selector alone was ambiguous, but the **actual release
  build is now verified**: [TSDuck Windows job 103603758775](https://github.com/tsduck/tsduck/actions/runs/34712521690/job/103603758775)
  downloads Robotweax SRT **0.2.4 BCrypt**, RIST **0.2.20** and VATek SDK
  **3.12.1**. Its x64 link command incorporates `robotweax-srt.lib`, `bcrypt.lib`,
  `librist.a`, and `libvatek_core_static.lib`. Its installed-version step reports
  Robotweax 0.2.4 with Microsoft BCrypt, RIST v0.2.20/API 4.13.0, VATek 3.12.10,
  and Small Deflate with fixes. These are direct build/runtime records, not an
  inference from release dates.
- [Robotweax LICENSE](https://github.com/Robotweax/srt/blob/v0.2.4/LICENSE) is
  MIT, copyright 2026 Robotweax GmbH and contributors. Its
  [THIRD_PARTY.md](https://github.com/Robotweax/srt/blob/v0.2.4/THIRD_PARTY.md)
  distinguishes independently authored implementation from Haivision reference
  research. The BCrypt SDK excludes OpenSSL. Preserve MIT notice; do **not**
  classify this implementation as Haivision/MPL or require MPL covered source
  solely because upstream TSDuck OTHERS retains that historical entry.
  Exact source: commit `4162adf50d3ff8e149d7b080130182b04441b0d1`.
- [RIST Windows build job](https://github.com/tsduck/rist-installer/actions/runs/34655754940/job/103447672949)
  verifies builtin cJSON, LZ4 and Mbed TLS. Downloaded official
  [librist v0.2.20 sources](https://code.videolan.org/rist/librist/-/tree/v0.2.20)
  identify cJSON 1.7.13 (MIT), LZ4 1.10.0 (BSD-2) and Mbed TLS 3.6.6
  (Apache-2.0 OR GPL-2.0-or-later; select Apache-2.0). Preserve their full texts
  and copyright notices. No NOTICE file was found in that Mbed TLS subtree.
- [VATek SDK v3.12.1](https://github.com/VisionAdvanceTechnologyInc/vatek_sdk_2/tree/v3.12.1)
  has BSD-2-Clause root license, copyright 2014–2023 Vision Advance Technology,
  and core-source notices extending through 2024. Include both; upstream
  TSDuck's older Richie Chang notice alone is not the whole current notice.
  Windows core uses WinUSB; Linux-only libusb linkage and Qt toolkit programs
  are not implied parts of the Windows static core.
- Verified texts and a source/material hash index are now staged under
  `scripts/portable-licenses/licenses/tsduck/` and `source-index.json`.
  They cover the identified permissive dependencies; Qt is still incomplete.
  Exact binary reproduction is not claimed. Missing reproducible-build evidence
  is a provenance limitation, not by itself a source-delivery obligation for
  MIT/BSD/Apache components. Preserve upstream documents without silently
  rewriting them, and explain the actual Windows selection in package notices.

Runtime data must match 3.45. Its portable ZIP contains 17 XML/names files,
including six `tscore.*` files and eleven `tsduck.*` files. The exact 3.45
archive, rather than a historical file list, is authoritative. Keep matching data and
manifest every file. Do not include separately sourced broadcast recordings.

### Qt 6.7.3 module and embedded-code inventory

Use the pinned `windeployqt --release --no-translations --no-compiler-runtime
--qmldir ui/qt` against the actual executable. Keep its recursive output and
machine-readable listing. [Qt deployment guidance](https://doc.qt.io/qt-6/windows-deployment.html)
explains dependency/QML scanning and its limits for non-Qt libraries. That
current page is operational guidance, not proof of the pinned package contents.

Expected source families are `qtbase`, `qtdeclarative`, and `qtsvg` if selected
by deployment. QML imports in this app are QtQuick, Controls, Layouts and Dialogs.
Their transitive DLLs/plugins/styles must be enumerated from the staged result;
this document intentionally does not certify a guessed flat DLL list. `qttools`
is installed for build/deployment tools; do not ship its developer tools.
Unexpected module families, GPL-only runtime modules or extra binaries reopen
review. A generic top-level LICENSES directory cannot replace copyright notices.

Pinned primary attribution records were read at
[qtbase v6.7.3](https://github.com/qt/qtbase/tree/v6.7.3/src), and
[qtdeclarative v6.7.3](https://github.com/qt/qtdeclarative/tree/v6.7.3/src).
The following is a **source-derived review checklist**, not a claim every optional
component was enabled in the distributed MSVC build. Gather each applicable
`qt_attribution.json`, its `LicenseFile`/`LicenseFiles` and `CopyrightFile`,
and license text for entries using only `LicenseId`; retain relative context.

| Source location | Components/selected terms to account for |
| --- | --- |
| `qtbase/src/3rdparty/` | double-conversion 3.3.0 (BSD-3); PCRE2 10.44 and SLJIT (PCRE exception/BSD-2); zlib 1.3.1; BLAKE2, easing, MD4/MD5/SHA1/SHA3; TinyCBOR 0.6.0 (MIT) |
| Same, GUI/image code | FreeType 2.13.3 (choose FTL for this route, with additional BDF/PCF/zlib texts); HarfBuzz 9.0.0 (MIT); JPEG-turbo 3.0.4 (IJG/BSD-3); PNG 1.6.44; MD4C 0.5.2 (MIT); ICC profile; D3D12/Vulkan allocation helpers when included |
| `qtbase/src/corelib/text/` | UCD revision 30 (Unicode-DFS-2016), CLDR v45 (Unicode-3.0) |
| `qtbase/src/corelib/tools/` | SipHash (CC0) |
| `qtbase/src/corelib/mimetypes/3rdparty/` | Apache Tika MIME definitions (Apache-2.0); preserve applicable notices |
| `qtbase/src/gui/painting/` | FreeType gray rasterizer (FTL); smooth scaling (BSD-2 and Imlib2); region code (X11 and HPND) |
| `qtbase/src/gui/text/` | Adobe glyph list (BSD-3) |
| `qtbase/src/gui/rhi/` | D3D12 mipmap shader (MIT) if included |
| Windows platform code | IAccessible2 1.3.0 (BSD-3), Wintab (LCS-Telegraphics) as enabled |
| `qtdeclarative/src/3rdparty/masm/` | JavaScriptCore macro assembler (BSD-2 with multiple copyright holders) |
| `qtdeclarative/src/quickcontrols/material/` | Angular Material shadow values (MIT), if Material style is shipped |

This list is not exhaustive: inspect all attribution records for staged module
families and source-file notices. Cross-check feature configuration, Qt archive
identities, third-party license files and actual outputs. Examples, tests, macOS,
Android and Linux-only code need not be claimed as Windows runtime components.
Do not silently include `opengl32sw.dll`, `d3dcompiler_47.dll`, OpenSSL DLLs or
other runtime payloads without separately identifying their origin and terms;
these are not covered merely by labeling the folder “Qt LGPL”.

For the LGPL route, preserve prominent usage notice, LGPLv3 **and GPLv3** texts,
and users' ability to substitute interface-compatible Qt libraries. Do not add
an EULA restriction on reverse engineering to debug modified library portions.
The manifest is an audit check, not a runtime lock that rejects user-modified Qt.
See the pinned [LGPL text](https://github.com/qt/qtbase/blob/v6.7.3/LICENSES/LGPL-3.0-only.txt)
and [Qt obligations guidance](https://www.qt.io/development/open-source-lgpl-obligations).

Prepare matching complete library sources with license notices, modifications
and build scripts/configuration needed for the binaries. Official 6.7.3 source
archives for [qtbase, qtdeclarative and qtsvg](https://download.qt.io/archive/qt/6.7/6.7.3/submodules/)
exist. Verify/download/hash the required archives, reconcile them to the exact
binary package and make them available by the selected compliant mechanism.
A link to “latest Qt” or this source index alone is not a completed provision.
An accompanying source artifact is a practical route, but keep it available
where recipients receive the binary and state the exact archive names/hashes.
Record any relocation patch applied by deployment tools. The three official
source archives have now been downloaded and checked against publisher SHA-256
files; exact URLs, filenames and hashes are in
`scripts/portable-licenses/source-index.json` (`qt_source_archives`).
The checked-in `licenses/qt/` contains 57 attribution records and 130 verbatim
source-family license/copyright/attribution files with hashes, covering qtbase,
qtdeclarative and qtsvg. This is a conservative notice superset, not a claim
that every listed component ships in the Windows application. It must not cause
extra runtime modules to be deployed. CI must fetch and hash-check the source
archives, record their presence in each bundle manifest, and provide them with
the reviewed binary. Exact deployed-module/configuration reconciliation and
complete corresponding-source delivery remain unverified until Windows staging.

### Microsoft runtime prerequisite: practical first-bundle route

Use `CrtMode=Prerequisite`: ship no Microsoft runtime DLLs or redistributable
installer. State that the app requires a separately installed Microsoft x64
Visual C++ v14 runtime, minimum **14.51.36231** (or a newer minimum if a staged
component needs it). The upstream TSDuck x64 release link command uses MSVC
14.51.36231, so assuming an older VS2022 app-local CRT suffices is unsafe.

Microsoft's [official current download page](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)
requires the runtime to be at least as recent as the build tools and provides
[the official x64 download](https://aka.ms/vc14/vc_redist.x64.exe).
On 2026-10-17 that file was downloaded read-only, **not executed**: its embedded
FileVersion/ProductVersion strings are **14.51.36247.0**, greater than the
identified minimum. SHA-256 observed:
`843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c`.
This hash is an observation, not a publisher-signature check or a permanent
pin for a moving latest-download URL. No automatic installation is authorized.

This removes Microsoft binary redistribution/entitlement from this bundle's
scope. Describe the app as portable **with a runtime prerequisite**, not fully
self-contained. Explain missing runtime clearly. Keep clean-host testing as a
separate acceptance gate and report the actual installed/runtime versions.
Windows 10/11 supply the OS/UCRT/API-set layer.

If optional app-local mode is used later, copy only eligible unmodified x64
release files from the matching Visual Studio REDIST directory; verify the
newest dependency's minimum runtime, notice requirements and distributor's
entitlement under the applicable REDIST list and terms. Never copy arbitrary
System32/debug files. See [Microsoft redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170).

## Inventory-bound completion gate

1. Stage internally and create a sorted list of relative runtime/resource paths,
   sizes and SHA-256 values. Include all EXEs, DLLs, plugins, QML, configuration
   and data. Record source commit, Qt archives, SDK asset and VS provenance.
2. Map each shipped file to a component; separately map embedded dependencies
   to their containing DLL. Record notice paths/hashes, source identity and
   provision location for every covered component. Preserve the deployment
   listing and recursive PE dependency report as evidence.
3. Hash a deterministic serialization of that inventory. Bind the review to
   this hash, with explicit evidence and unresolved items. Also hash every
   notice and source archive; exclude only the manifest/review's self-referential
   fields from their own digest computation. Do not use a bare reusable true flag.
4. Keep `review_complete: false` while exact Qt inventory/notices, material
   dependency notices/source obligations remain open. The verified Robotweax
   MIT selection does not require MPL source provision; runtime-prerequisite
   mode does not redistribute Microsoft binaries.
   Missing mandatory material fails closed. Do not call a blocked stage a
   redistribution-ready package. Diagnostics-only CI artifacts may be produced
   if they contain no gated binaries/source-sensitive payloads.
5. Recompute before ZIP/upload. A changed, added or removed staged file or
   dependency identity invalidates the previous review. Scope the result to this
   bundle and selected licensing route, not an unconditional legal approval.
6. Runtime relocation, clean-host testing and native Windows GUI acceptance are
   additional independent gates. This review cannot waive them or authorize a
   public release, installer or upload.

## First hosted Windows inventory reconciliation (2026-10-17)

Evidence is diagnostic staging, not a downloadable approved binary package:
PR #9 head `170b2fb3599cb6b2c177a25ebd70fb2c3f77ba44`, tested merge commit
`d5b439220fe8d4a225184a7314cf3dc516301974`. The diagnostic artifact's downloaded
ZIP SHA-256 was checked by the packaging worker:
`7d486320f45e4f4fbd3617865915aafa186e41ff4113c7223602ed39d85b7b6a`.
The extracted manifest SHA-256 is
`d3d10aa6620c7a149f472048eca517fcae99f5572fda60b071b32b3ed45e4f39`.
This records 695 staged files, including 531 under `bin/`, 456 QML-tree files,
29 top-level Qt DLLs, and 148 license-directory files. Only diagnostics were
available locally; hashes below are reconciled against the hosted stage's
manifest, not a second local inspection of every staged binary/archive byte.

### Matched coverage

- `tscore.dll` and `tsduck.dll` hashes exactly match the independently downloaded
  official portable-release DLLs recorded above. All 17 XML/names data filenames
  match that release. The earlier draft's count of 18 was a counting error,
  corrected by reopening the official ZIP; there is no missing eighteenth file.
- Every checked-in license-directory file matches the manifest's hash. The two
  top-level notice/source text hashes match after Windows Git CRLF conversion;
  this is a line-ending difference, not omitted content. The next stage must
  hash the revised text inputs again.
- All three staged Qt source archive hashes match the verified publisher pins.
- `Qt6Core`, `Qt6Gui`, `Qt6Network`, `Qt6OpenGL` and base plugins (platforms,
  generic touch, GIF/ICO/JPEG, network information and TLS) map to **qtbase**.
- `Qt6Svg`, `imageformats/qsvg` and `iconengines/qsvgicon` map to **qtsvg**.
- The remaining Qt6 QML/Quick/Controls/Dialogs/Shapes/Templates/Layout and
  LabsFolderListModel DLLs, their `qml/` resources/plugins, and QML tooling
  plugins map to **qtdeclarative**. All are covered by the prepared source
  families; no fourth deployed Qt source family was found. The kit's qttools
  archive is a build/deployment tool input, not evidence that qttools runtime
  components were shipped.
- There is no `opengl32sw.dll`, OpenSSL library DLL, separate TSDuck plugin,
  Dektec runtime or app-local VC runtime in this inventory. The Qt OpenSSL
  backend plugin is Qt code; its presence alone does not establish that OpenSSL
  implementation code is embedded. Preserve PE/deployment evidence and check
  for unexpected dependencies before final approval.

### Specific remaining issues and next evidence

1. The stage contains **D3Dcompiler_47.dll**,
   SHA-256 `64054871e088d47b4b7380f90efa40cf2f57bd966724764330a029f4fc3aa6eb`.
   This contradicts the intended no-Microsoft-binary prerequisite route.
   Use the supported `--no-system-d3d-compiler` deployment option and verify the
   system library's identity/loading on supported Windows. Microsoft describes
   the OS-provided compiler in its [official DXSDK NuGet package](https://www.nuget.org/packages/Microsoft.DXSDK.D3DX/9.29.952.7).
   Do not silently treat this DLL as LGPL-covered Qt code. Optional QML debugging
   plugins may also be omitted using the pinned tool's supported
   `--skip-plugin-types qmltooling`; this reduces runtime scope.
2. Capture Qt installed build-feature files (`qconfig.pri`, `qmodule.pri`,
   `qconfig.h` where present), their hashes and pre/post-deployment Qt6Core
   hashes. Record whether windeployqt applied its standard path relocation and
   provide the relevant build/deployment instructions with the source material.
3. Persist the recursive PE dependency report, actual system VC/D3D versions
   and relocation test evidence. The first harness failed before application
   launch due to an environment-key casing bug; a build/test pass does not
   substitute for the still-uncompleted relocation acceptance test.
4. Reconcile the next stage's exact hashes after deployment and notice changes.
   Keep `review_complete: false` until material source/notice/runtime-origin
   gaps close. This report does not approve the first manifest or future
   manifests automatically, and does not waive native GUI acceptance.


## Corrected hosted inventory: material review completed (2026-10-17)

The corrected PR head `8911a871de72fbee61af264f7e9c22a2670e2d59` was tested as
merge commit `9e4ab6941d5e7df07f0890b6e73f7f109c97c0d0` in
[Windows job 117380319411](https://github.com/znbsf/ShowPsiSi/actions/runs/39027162704/job/117380319411).
The verified diagnostic artifact SHA-256 is
`7d228948272e6f608115a47531f1d47ea8e6b774faf0093ba32bd74f36f7dc23`.
Its stage manifest SHA-256 is
`9de98ec0697c2f5f3026a6605d13fd56ddf3194e7630971ff6171d3cb53c4286`.

The 683-file inventory removes exactly the Microsoft D3Dcompiler DLL and eleven
QML tooling DLLs from the first runtime inventory. Remaining third-party
runtime bytes are unchanged. All checked-in notice/source-index bytes now
match the stage exactly; all three source archive pins still match. The
Windows checkout policy preserves these inputs byte-for-byte. The prepared
notice superset covers the observed qtbase/declarative/svg modules, and no
additional third-party binary family appeared. TSDuck/TSCore release identities
and all 17 runtime data files remain accounted for.

Installed Qt configuration is captured verbatim with SHA-256 values in
`build-information.json`: shared, relocatable Qt 6.7.3; MSVC 19.29.30151 kit;
OpenSSL support is **not linked** (`openssl-linked` disabled). The OpenSSL
backend's PE imports contain Qt and system libraries, and no OpenSSL library
is distributed. The installed and deployed QtCore SHA-256 values are identical
(`05982ff42ba7ae3074badaee1a09ff7f45e694de815bb06b514b28c28cfe0500`),
so there is no deployment patch to supply for this kit. Full official module
source archives plus their build scripts and captured feature/deployment
information accompany the candidate.

The validation report is bound to the exact manifest above and reports
`passed: true`. It includes 71 PE import inventories, relocated execution,
startup loaded-module evidence and system prerequisites. All four checked VC
runtime files are 14.51.36247.0, satisfying 14.51.36231.0. The system D3D compiler
is 10.0.20348.5499 and remains outside the package. Hosted Windows Server
execution is evidence for this CI candidate, not an independent clean consumer
Windows 10/11 installation test. Interactive native desktop validation remains
false and must not be represented as completed.

### Exact gate record and limits

`scripts/portable-licenses/redistribution-review.json` now records completion
of the **material dependency/source/notice review** for 669 exact file hashes,
including all third-party runtime/QML/data files, notices and source archives.
It records the observed evidence separately from the finalized top-level
notice/source/index text hashes, which the next CI stage must reproduce. The
application's newly compiled EXEs are deliberately outside this reusable
third-party map; each build's full manifest and runtime validation bind those
EXEs independently. Changed dependencies or source/notice files fail the gate.

This scoped result supports creation of the requested portable CI candidate
with accompanying sources and documented Windows/runtime prerequisites. It is
not blanket legal assurance, approval of an unrelated future inventory, native
GUI acceptance, public-release authorization, or permission to ship an installer.
The parent must publish the reviewed inputs and the next CI must revalidate
and match them before a binary ZIP is uploaded.

## Protocol increment: static Expat 2.9.0 (2026-10-19)

Expat is statically linked into the shared core for local DVB-I XML inspection.
The official
[Expat 2.9.0 release](https://github.com/libexpat/libexpat/releases/tag/R_2_9_0)
archive is 534,052 bytes, SHA-256
`1e6371862cc31999b368c3b89b49994f0677e1bab5f1b2b85ae3741f5d803051`.
All 64 vendored upstream files were independently compared byte-for-byte with
that archive. `third_party/expat/SHOWPSISI_SOURCE.json` records the exact subset;
its SHA-256 is `4b0f73db285c97bcfd0d6c4dab25c76ca465fa27da5d8c88ec8d2d4637275cf0`.

Expat's [MIT notice](https://github.com/libexpat/libexpat/blob/R_2_9_0/expat/COPYING)
and full leading copyright/license comments from each vendored library C/header
file are preserved under `licenses/expat/`. The embedded SipHash source carries
the CC0-1.0 dedication and attribution; those comments are retained too. The
upstream CMake BSD buildsystem notice stays with the unmodified repository
source; CMake files are not compiled into the runtime. These permissive terms
do not introduce an accompanying-source obligation. The exact official archive
link and vendored file hashes are provenance, not a future source-delivery
promise. Existing three complete Qt source archives still accompany the binary.

`scripts/ci/static_dependencies.py` pins this source and notice identity
independently of each generated package manifest. Windows CI checks the entire
source inventory before and after compilation and records the static component
in the production build record. Staging checks the inventory again and requires
that same component identity. Archive and installer gates require matching
build/source-index metadata, all exact Expat notice bytes, and the prominent
top-level notice/source text. Removing a static component and regenerating the
package manifest or exact-file approval cannot clear these checks. Static code
cannot be discovered by looking only for imported DLLs.

The exact redistribution review adds these three notice/provenance files and
updates only the three affected top-level notice/index hashes; existing runtime
and Qt source pins are unchanged. Fresh exact-revision Windows static-link,
staged payload, runtime and installer evidence remain separate gates; no
clean-machine or native GUI acceptance is implied.
