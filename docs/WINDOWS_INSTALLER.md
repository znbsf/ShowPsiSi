# Windows Qt installer and update asset contract

Implementation date: 2026-10-19. Primary target: Windows 10/11 x64, Qt + the
production shared engine. Setup permits native x64 Windows only; ARM64 emulation
is not enabled because its system-runtime/load-path behavior is not validated.
Tauri/WebView2 remains experimental and is not an
installer payload. This pipeline prepares unsigned CI candidates; it does not
publish a GitHub release or create a release tag.

## User experience

The normal installer is `ShowPsiSi-0.1.0-windows-x64-setup.exe` (version follows
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

The Qt libraries, matching TSDuck data, notices, and three complete Qt source
archives stay inside the installation unchanged. Dynamic Qt libraries remain
replaceable. No SDK, compiler, Python, PowerShell 7 or WebView2 installation is
needed to run the primary application.

### Runtime bootstrap and first-install limitation

This is a single guided setup flow, **not a fully offline runtime bundle**.
A machine already supplying all four checked Microsoft x64 VC v14 runtime DLLs
at version **14.51.36231.0 or later** does not download or install a prerequisite.
Otherwise Setup asks explicitly before downloading an exact verified Microsoft
runtime installer. The Microsoft installer is visible, retains its license
acceptance UI, and may request administrator permission through UAC. Internet
access is required for that first download. Cancellation, UAC refusal, download
or hash failure, too-old runtime, and restart-required outcomes stop before
ShowPsiSi files or registration are changed. Silent setup never downloads or
installs the prerequisite. The app uninstaller never removes the shared runtime.

The build downloads from Microsoft's documented official x64 endpoint, follows
its redirect to an allowed HTTPS Microsoft download host, requires valid
Microsoft Corporation Authenticode and a sufficient file version, and records
the resolved immutable URL, SHA-256, signer, version and size. The resolved URL
and hash are compiled into setup. Target downloads are checked against that
hash; an upstream change fails closed rather than executing different bytes.
`prepare-windows-prerequisite.ps1 -Metadata <previous-vc-runtime.json>` reproduces
that prerequisite selection and rechecks the signature and exact bytes. Downloaded
Microsoft binaries are never embedded in or uploaded with the application.

Why not silently add app-local VC DLLs: Microsoft's [redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
and [VS 2022 REDIST list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution)
permit eligible unmodified release files subject to the distributor's Visual
Studio license terms. The current repository review explicitly covers the
system-prerequisite route; it has no distributor-rights evidence or reviewed
app-local 14.51+ inventory. It therefore remains unchanged. An app-local route
requires that evidence, exact eligible file provenance/notices, and a new reviewed
inventory, rather than simply turning on the existing AppLocal switch. This is
an engineering gate and does not establish legal clearance.

## Build and gating

1. Run the ordinary Windows build, engine/Qt/updater tests, portable stage,
   relocation/runtime validation and inventory-bound archive gate.
2. Run `scripts/prepare-windows-prerequisite.ps1` to prepare runtime provenance
   without executing the downloaded Microsoft installer.
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
a satisfied test-host runtime minimum, and an exact match of
all reviewed third-party binaries, data, notices and covered sources. It uses
an explicit generated file list, never a wildcard across a build tree. No existing
redistribution review entries are altered by this implementation. A green compile
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

Windows hosted smoke exercises actual installation in a Chinese/spaces path,
previous-version upgrade, same-version reinstall, downgrade rejection,
non-installation update rejection, live-app-mutex update/uninstall rejection,
complete installed file identities, per-user
settings preservation, real installed engine export/readback and lifetime-mutex creation/release, actual Qt/core
process startup with SDK paths removed, and uninstall cleanup. The previous-version
fixture tests installer version transitions, not a historical app-schema migration.

A VS-equipped Windows runner already has a runtime. Its smoke **does not** prove
clean-machine installation, missing-runtime download/UAC/Microsoft-license-dialog
handling, native app file dialogs or GPU behavior. Those remain explicit release
acceptance checks on a suitable clean Windows 10/11 environment. In particular,
exercise offline first install, cancellation, UAC decline, restart-required
outcome, and a successful missing-runtime flow without weakening security settings.
Retain the exact installer/hash and actual results. No clean-machine claim is
inferred from a successful process launch or unit fixture.

Before a public release, verify final source/CI identities, source/notice inventory,
installer smoke and clean-machine results; decide signing; verify the uploaded
installer and SHA256SUMS; and state the first-install internet/UAC condition in
the release notes. Unsigned candidates may show Windows publisher/SmartScreen
warnings: do not instruct users to bypass them. Public publication is a separate
authorized action.
