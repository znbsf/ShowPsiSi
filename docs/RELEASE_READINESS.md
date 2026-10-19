# Windows release gates

## Published release

[ShowPsiSi v0.2.0](https://github.com/znbsf/ShowPsiSi/releases/tag/v0.2.0) was
published on 2026-10-19 from `08f29e48a4884eb1879b916361ce7da1828c883a`.
Its Qt Windows x64 installer and portable ZIP use the historical shared-VC-runtime
prerequisite route. See [release provenance and limits](releases/v0.2.0-validation.md).
Protocol extensions and the app-local candidate are not part of those binaries.

## Current v0.3.0 candidate

The candidate combines bounded protocol inspection with five pinned Microsoft
release x64 DLLs staged beside Qt/core. It uses a same-release corresponding-source
ZIP for the original Qt source archives, while notices, source indexes and source
download instructions remain in each binary package.

The exact-inventory engineering distribution review is complete on the documented
[hosted-runner basis](PORTABLE_LICENSE_REVIEW.md#hosted-runner-distribution-basis).
Its downstream REDIST application is an explicit inference, not an independently
verified private agreement or legal guarantee. No new agreement was accepted and
this review is not Release publication approval.

Native Windows/final-payload and clean-machine offline acceptance remain pending.
Current published v0.2.0 assets are unchanged. See [candidate notes](releases/v0.3.0.md),
[installer contract](WINDOWS_INSTALLER.md) and [Windows acceptance](WINDOWS_APPLOCAL_ACCEPTANCE.md).

## Required acceptance

1. Freeze the exact source revision and dependency/source/license inventory.
2. Run all five hosted CI jobs, including production engine/helper, Qt/updater,
   sandboxed browser and Linux/Windows Tauri gates. Keep platform scopes explicit.
3. Validate relocation, normal/delay PE imports, required per-process app-local
   loaded modules, launcher failure cases and exact manifested payload hashes.
4. Exercise installer install/upgrade/reinstall/uninstall, Unicode paths, settings,
   shortcut identity, downgrade/live-process rejection and installed export/readback.
5. Verify the paired corresponding-source archive against the exact original
   sources, hashes, notices and source-download metadata. Missing/mismatched source
   delivery fails packaging and publication gates.
6. Independently record supported clean Windows standard-user/offline installation,
   native GUI/file dialogs, export, restart and real upgrade behavior. An equipped
   hosted runner or offscreen Qt pass cannot establish these outcomes.
7. Disclose unsigned/SmartScreen status and any remaining limitations. Do not
   disable security protections to manufacture acceptance.
8. Publish only under separate authorization, then verify exact public source,
   checksums, binary/source assets and update metadata. CI success alone is not
   a published release.

Installed updates require explicit user actions for download and installation;
active work must block unsafe exit/replacement. Portable updates use a verified
ZIP extracted into a new directory. See [update lifecycle](UPDATES.md).
