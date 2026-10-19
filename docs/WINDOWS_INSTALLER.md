# Windows Qt installer and update asset contract

Implementation date: 2026-10-19. Primary target: Windows 10 1809+/11 x64, Qt + the
production shared engine. Setup permits native x64 Windows only; ARM64 emulation
is not enabled because its system-runtime/load-path behavior is not validated.
Tauri/WebView2 remains experimental and is not an
installer payload. This pipeline prepares unsigned CI candidates; it does not
publish a GitHub release or create a release tag.

Setup requires build 17763 or newer, matching the pinned [Qt 6.7.3 Windows support floor](https://github.com/qt/qtdoc/blob/v6.7.3/doc/src/platforms/supported-platforms.qdocinc#L51-L67).
This is a documented support boundary, not a reproduced old-Windows crash.
The companion no-install deliverable is `ShowPsiSi-VERSION-windows-x64-portable.zip`;
both assets share the same version and release `SHA256SUMS`. The ZIP launcher
checks the five app-local runtime DLLs without downloading/installing anything; its
direct EXE bypasses that user-friendly check. See the included README-portable.txt.

## User experience

The normal installer is `ShowPsiSi-VERSION-windows-x64-setup.exe` (version follows
the root CMake project). It defaults to the current user's
`%LOCALAPPDATA%\Programs\ShowPsiSi`, permits a different empty folder, creates a
Start Menu shortcut and optionally a desktop shortcut, and registers a per-user
uninstaller. No administrator privilege is requested for the application itself.
Qt settings and user-selected export files are retained during upgrade/uninstall.
An existing installation reuses its location; downgrades and unrelated nonempty
folders are rejected. A shared application-lifetime mutex blocks setup/uninstall while Qt or its core
is running, including another window. Setup does not forcibly close applications. Close ShowPsiSi
before upgrading; in-app Install and quit hands off to the visible wizard. This
is not a promise of atomic recovery from arbitrary power loss or a crashed
installer; retain a known-good installer and backups of important exports.

The Qt libraries, matching TSDuck data and small notices/license/build materials
stay inside the installation. Three complete original Qt source archives are a
free, versioned same-release asset identified by SOURCE_DOWNLOAD.txt; installers
are gated on that exact paired archive. Dynamic Qt libraries remain
replaceable. No SDK, compiler, Python, PowerShell 7 or WebView2 installation is
needed to run the primary application.

### App-local runtime candidate

The current candidate bundles five unmodified Microsoft release x64 DLLs from
VC runtime **14.51.36247.0**, above TSDuck's **14.51.36231.0** minimum.
This includes `msvcp140_2.dll`, required by Qt's transitive imports.
Setup's AppLocal preprocessor path contains no shared-runtime probe, download,
Microsoft-installer execution or UAC request. It installs the DLLs only into
`{app}/bin`; uninstall removes only manifested app-owned files and leaves shared
Windows runtimes alone. Microsoft-only terms are displayed as informational
installer material and retained beside the portable copy; MIT/Qt LGPL rights
remain separate.

`scripts/prepare-applocal-runtime.ps1` downloads the pinned official source EXE,
checks Microsoft Authenticode, exact SHA-256 and version, then treats it solely
as data. A hash-pinned CAB slice and exact named inner members are expanded by
Windows' inbox `expand.exe`; no EXE/MSI is run. Every selected DLL is independently
signature/hash/version/AMD64 checked. The immutable inventory is
`scripts/portable-licenses/vc-runtime-pin.json`; the package carries
`bin/showpsisi-vc-runtime.json`. PE normal/delay imports must resolve every CRT
family locally, and native process evidence must show the required per-process
DLL subset actually loaded from the package, never System32.

The exact-inventory engineering distribution review uses the documented
[hosted-runner licensing basis](PORTABLE_LICENSE_REVIEW.md#hosted-runner-distribution-basis).
The downstream REDIST interpretation is explicitly an inference, not a quoted
private agreement or legal guarantee. Native Windows and payload checks remain
required before distribution; this review does not authorize a Release.
App-local CRT security servicing is now the application's responsibility: refresh
the official pin and reviewed inventory, rerun gates and ship an application update.
Windows UCRT/D3D remain supported OS components and are not bundled.

The retained Prerequisite code path describes historical v0.1/v0.2 delivery.
It remains guarded separately and now checks all five runtime DLLs. Its failure
with code `0x80070005` reports access denied from the Microsoft installer result;
that code alone does not identify the denied file/registry/policy resource.

## Build and gating

1. Run the ordinary Windows build, engine/Qt/updater tests, portable stage,
   relocation/runtime validation and inventory-bound archive gate.
2. Run `scripts/prepare-applocal-runtime.ps1` before staging, with explicit
   Output, PrerequisiteDirectory and Python paths. Pass the verified runtime
   directory to package-windows.ps1. No downloaded Microsoft installer is executed.
3. Run `scripts/package-installer.ps1` with explicit Package, Validation,
   PrerequisiteDirectory, Output, Work and Python paths. Use the official
   Inno Setup 6.3+ compiler already provided by the Windows hosted image, or pass
   its explicit path. A no-output script compile checks the loaded engine version
   (6.3+ and below 7), because the ISCC driver PE version can be zero. The driver,
   compiler and preprocessor hashes and probe output are recorded; no compiler is
   downloaded or installed automatically. See the official [ISCC implementation](https://github.com/jrsoftware/issrc/blob/is-6_7_1/Projects/ISCC.dpr)
   and [predefined version variable](https://jrsoftware.org/ishelp/topic_predefinedvars.htm).
4. Run `scripts/ci/installer_checks.py smoke`. CI builds a clearly named TEST-ONLY
   0.0.0 installer around the same reviewed payload for the upgrade fixture. It
   is never uploaded as a release artifact or included in SHA256SUMS.
5. Upload the real candidate only after smoke passes. Preserve validation and
   prerequisite metadata even after failure. Do not upload the downloaded
   Microsoft EXE or the test-only installer.

Shortcut validation uses the explicit Unicode [IShellLinkW interface](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishelllinkw),
requires both the exact resolved executable path and matching filesystem identity,
and retains `.lnk` bytes, decoded/expected paths and the former WScript reader's
raw output before cleanup. An early Windows-only Chinese/space-path round trip
tests the reader independently of the installer. This replaces an ambiguous
text-only smoke failure; it does not by itself establish that failure's cause.

The installer independently requires fresh runtime validation tied to the exact
payload manifest, matching application version and clean checkout source commit,
a satisfied selected-runtime-mode minimum, and an exact match of
all reviewed third-party binaries, data, notices and covered sources. It uses
an explicit generated file list, never a wildcard across a build tree. The exact review inventory includes every approved runtime DLL, its metadata and
Microsoft-only terms. It may not be regenerated merely to approve changed bytes. A green compile
cannot bypass missing or changed inventory. Compiler inputs and output identities
are retained for reproducibility; bit-for-bit reproducible Inno output is not
claimed (compiler version, PE timestamps and signing can affect it).

## In-app update interface

- Official repository: `https://github.com/znbsf/ShowPsiSi`
- Stable release tag: `v<major.minor.patch>`
- Installer asset: `ShowPsiSi-<major.minor.patch>-windows-x64-setup.exe`
- Checksum asset: `SHA256SUMS`, containing the exact SHA-256, two spaces, and
  installer filename, followed by a newline
- Installed marker: `<installation-root>/showpsisi-installation.json`, schema 1,
  installer `inno`, frontend `qt`, channel `stable`, source commit and app version
- Stable AppId: `{13C6E0A2-B226-4BAA-A218-8DD167D78D4C}`
- Launch: visible installer with `/UPDATE /DIR="<installation-root>" /NORESTART`
  after explicit user action and checksum verification. The root is the parent
  of `bin`, not the executable directory. No silent flags or process force-kill.

A newly installed Qt EXE remains at `<installation-root>/bin/showpsisi-qt.exe`.
The installer preserves registered location and blocks the update path when the
installation marker is missing. An extracted portable package can still run,
but must use a normal installer flow rather than claim an in-place installed
upgrade. Current stable versions are numeric three-component versions; prerelease
and development tags are not installer update candidates.

## Validation scope and release checklist

Platform-independent tests cover new/changed DLLs, notices/source changes,
stale validation, hash tampering, insufficient runtime, bad download URLs,
unverified publisher metadata, argument escaping, exact installed file hashes,
test-fixture separation and silent bootstrap refusal.

Windows hosted smoke is configured to exercise actual installation in a Chinese/spaces path,
previous-version upgrade, same-version reinstall, downgrade rejection,
non-installation update rejection, live-app-mutex update/uninstall rejection,
complete installed file identities, per-user
settings preservation, real installed engine export/readback and lifetime-mutex creation/release, actual Qt/core
process startup with SDK paths removed, and uninstall cleanup. The previous-version
fixture tests installer version transitions, not a historical app-schema migration.

A VS-equipped Windows runner already has a runtime. Exact app-local module paths
and negative local-DLL fixtures establish independence from its shared CRT for
those observed processes; they do not establish a clean-machine offline install.
The separate [clean Windows acceptance plan](WINDOWS_APPLOCAL_ACCEPTANCE.md)
requires a disposable supported x64 standard-user host, recorded baseline and
real offline installation/startup/GUI/export/upgrade results. Its host collector
alone is not application acceptance. Native dialogs/GPU and actual in-app update
handoff remain explicit checks. Never remove an owner's runtime or weaken OS
security to manufacture a clean test environment.

Before a public release, verify final source/CI identities, source/notice inventory,
installer smoke and clean-machine results; decide signing; verify the uploaded
installer and SHA256SUMS; and accurately state app-local/offline verification limits in
the release notes for the selected runtime mode. Unsigned candidates may show Windows publisher/SmartScreen
warnings: do not instruct users to bypass them. Public publication is a separate
authorized action.
