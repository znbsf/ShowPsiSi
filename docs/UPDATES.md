# Qt release updates and project identity

The official repository is <https://github.com/znbsf/ShowPsiSi>. Both workbenches
expose the repository and <https://github.com/znbsf/ShowPsiSi/releases> from
**About / Updates**. Qt displays its CMake project version. Tauri/Web explicitly
opens the release page; it does not claim to download or install native updates.

This is an implementation contract, not evidence that a release has been
published or that Windows installation has passed. See the current delivery
record for platform-specific acceptance.

## User flow

1. Choose **About / Updates → Check for updates**. Nothing contacts GitHub on
   startup. A missing published release is reported separately from up-to-date.
2. Review the stable version and plain-text release notes. The dialog identifies
   the installed, portable, or source/unsupported-platform edition. Source and
   non-Windows builds can check releases and open the official page.
3. The **installed Windows x64 Qt edition** offers **Download installer…**.
   Confirm the version, exact filename, size and SHA-256. Downloading never
   starts installation. Cancel, closing the dialog, a timeout, a network/TLS
   error or a checksum mismatch removes the incomplete staged download.
4. After successful verification, choose **Install and quit…**. A separate
   confirmation asks the user to save/export work and explicitly acknowledges
   that unsaved previews and the current workspace will close. Active analysis,
   export, inspect, comparison and Save-dialog transactions block this action.
   The C++ backend-request guard is rechecked at confirmation time.
5. SHA-256 is recomputed from the staged file immediately before the visible
   installer is launched with `/UPDATE`, `/DIR=<installed package root>` and
   `/NORESTART`. Only successful process launch closes Qt. The user completes the
   wizard. The current app-local package includes the matching runtime DLLs;
   older prerequisite-mode installers can ask separately for Windows administrator
   approval. Process launch alone does not establish installation success.

In-app installation requires both the package marker in `bin/` and the fixed
Inno installation marker in the parent package root, with the matching AppId,
version, frontend and stable channel. A valid Windows package with no
installation marker is identified as portable;
an existing malformed or mismatched installation marker falls back to an
unrecognized/source package and cannot enable installation.

### Portable edition: keep using a ZIP

The portable edition never offers **Download installer** or **Install and quit**.
Its version check selects the exact
`ShowPsiSi-{MAJOR.MINOR.PATCH}-windows-x64-portable.zip` asset from the same stable
release. Once its official URL and expected SHA-256 are validated, **Portable
ZIP…** shows a separate confirmation with the version, filename, size, and a
selectable checksum. **Open ZIP download** hands that exact official URL to the
system browser. The release-page button remains available when no suitable ZIP
or newer release is available.

The browser performs the ZIP download. ShowPsiSi does **not** read or verify those
downloaded bytes, unzip them, overwrite the current folder, migrate to setup, or
quit. The confirmation explicitly requires the user to:

1. Compare the saved ZIP's SHA-256 with the displayed value or that release's
   `SHA256SUMS` (for example, with PowerShell `Get-FileHash -Algorithm SHA256`).
2. Save/export work and close all ShowPsiSi windows before switching versions.
3. Extract into a **new folder**, run its `Launch Qt.cmd`, and use the new folder
   in place of the old one. Retain the old copy until the new version is checked.

The installer and portable ZIP share one release `SHA256SUMS`, with distinct
exact filename entries. A setup checksum cannot authorize a ZIP link. Missing,
duplicate, wrong-origin, wrong-platform, or malformed ZIP metadata fails closed;
there is no fallback that forces installation.

Accepted exports have an authoritative native lifetime guard independent of
frontend selection/query generations. Ordinary window close is refused until
an export returns its terminal response. If an explicit application shutdown
bypasses the window, the shell closes backend stdin and drains accepted writes
rather than killing them after a fixed timeout. Qt and core each hold the
non-owning Windows named mutex `Local\ShowPsiSi.ApplicationLifetime`; multiple
instances remain allowed, while the installer can refuse replacement or
uninstall until all of those processes exit. This does not make export plus
manifest atomic against power loss, external termination or a native crash.

## Release and transport contract

- Metadata is fetched from the fixed HTTPS endpoint
  `https://api.github.com/repos/znbsf/ShowPsiSi/releases/latest`. There is no
  configurable mirror, API credential, remote script or background poll.
- The release must be published, not draft/prerelease, with a strict stable tag
  `vMAJOR.MINOR.PATCH`. Numeric comparison forbids a downgrade or same-version
  reinstall. Build metadata/prerelease assets are not selected.
- The installed edition selects
  `ShowPsiSi-{MAJOR.MINOR.PATCH}-windows-x64-setup.exe`; the portable edition selects
  `ShowPsiSi-{MAJOR.MINOR.PATCH}-windows-x64-portable.zip`. The selected initial
  URL must match
  that release's path in the official repository byte-for-byte. Metadata URLs,
  query/fragment additions, other owners, tags, architectures and ambiguous
  duplicate assets are rejected.
- A valid GitHub asset `digest` of `sha256:<64 hex>` is preferred. When no digest
  is supplied, a bounded `SHA256SUMS` asset from the same official release must
  identify the exact selected package once. Missing, malformed or conflicting
  entries
  fail closed. A malformed supplied digest is never silently ignored.
- Redirects are followed manually, up to three, only over HTTPS to
  `release-assets.githubusercontent.com` or `objects.githubusercontent.com`,
  with no user info, nonstandard port or fragment. Metadata redirects are
  rejected. Normal Qt certificate verification remains enabled.
- Metadata is limited to 2 MiB, checksums to 64 KiB and an installer to 1 GiB;
  actual installer length must equal the declared release size. Requests use a
  15-second transfer inactivity timeout. A check has a 30-second overall bound;
  an in-app installer download has a 10-minute bound. Failures require an explicit
  retry. Portable ZIP metadata has the same 1 GiB declared-size bound, but the
  external browser owns its transfer and the user must verify its bytes.
- A unique private cache directory and `QSaveFile` without direct-write fallback
  stage bytes. A final installer pathname appears only after exact length and
  SHA-256 validation and successful atomic commit. Cancelled/failed files are
  removed. A launched installer is retained in the app cache for its process to
  read and is never automatically run on a later application launch.

SHA-256 ties downloaded bytes to official GitHub release metadata/checksums. It
is **not an independent publisher signature** and cannot defend against an
attacker controlling that repository/account or its release metadata. The UI
states that independent signing is not enforced. Public distribution should
separately disclose its current signing/SmartScreen status and pass the
installer/redistribution gates.

## Reproducible tests

The transport suite replaces `QNetworkAccessManager` only inside its compiled
test object. It has no production fixture URL, fake success mode, credential or
installer-launch override. It does not contact GitHub or execute an installer.

```sh
cmake -S tests/qt_updates -B build/updater-tests \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.7.3/gcc_64
cmake --build build/updater-tests --parallel 2
ctest --test-dir build/updater-tests --output-on-failure
```

Or configure the main build with `-DSHOWPSISI_BUILD_UPDATER_TESTS=ON`, then run
`ctest --test-dir build -C Release --output-on-failure -R updater` (omit `-C`
for a single-config build).

Coverage includes strict versions, no downgrade, malformed metadata, draft and
prerelease refusal, exact platform/asset origin, size/digest errors, checksum
fallback/duplicates, network/TLS failures, rate limiting, no published release,
manual retry, timeout, cancellation/stale responses, partial-file removal,
checksum mismatch/truncation/oversize, approved/rejected redirects and loop
bounds, file tampering and pending-operation install guards;
installed/portable/source
marker detection, exact ZIP selection/checksum fallback, no portable downgrade,
and browser handoff without any installer download/launch. A non-executable
text fixture stands in for installer bytes. Windows wizard behavior, clean
machine prerequisites, native dialogs and actual updater handoff require
separate Windows evidence.

API references: [GitHub releases](https://docs.github.com/en/rest/releases/releases),
[GitHub release assets](https://docs.github.com/en/rest/releases/assets),
[Qt network request/redirect policy](https://doc.qt.io/qt-6/qnetworkrequest.html).

### Dialog enabled/disabled visual states

`tests/qt_updates/tst_UpdateDialog.qml` loads the actual production dialog with
an inert presentation fixture. It asserts disabled actions do not open
confirmations, checks busy/work-pending transitions, and preserves full enabled
text opacity/ink. Disabled buttons use the workbench's existing 40% opacity
convention so availability is distinct in both themes.

Run Qt's `qmltestrunner -input /absolute/path/to/tests/qt_updates/tst_UpdateDialog.qml`
from an ignored artifact directory with `QT_QPA_PLATFORM=offscreen`,
`QT_QUICK_BACKEND=software` and `QT_QUICK_CONTROLS_STYLE=Basic`. It saves
`update-dialog-disabled-dark.png` and `update-dialog-disabled-light.png`, plus
portable About/confirmation images in each theme, in that directory. These are
rendered component-fixture checks, not network or Windows
installer acceptance.
