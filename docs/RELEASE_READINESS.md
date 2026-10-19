# Windows release readiness

Started 2026-10-19 on `dc37d90` in the assistant's Linux cloud workspace.
This record tracks a release candidate, not a published release or completed
Windows clean-machine acceptance.

## Intended deliverable

The first installer targets **Windows 10/11 x64, Qt workbench, version 0.1.0**.
The source repository is https://github.com/znbsf/ShowPsiSi and stable releases
are https://github.com/znbsf/ShowPsiSi/releases. Tauri remains an alternative
frontend with its existing validation; do not imply it is included in the Qt
installer or has the same native update mechanism.

The installer and built-in update client share these exact identities:

- Tag: `vMAJOR.MINOR.PATCH`.
- Installer: `ShowPsiSi-MAJOR.MINOR.PATCH-windows-x64-setup.exe`.
- Checksums: `SHA256SUMS` (or the official GitHub asset SHA-256 digest).
- No credentials are needed for public release checks.

The app must show its installed version and repository, allow a manual update
check, display the eligible newer stable version, and require an explicit
installation choice. Downloads must be bounded, cancellable and hash-verified.
Malformed metadata, wrong-origin assets, incomplete downloads and downgrade
attempts must not launch a process. Work in progress must not be silently lost
when an update closes the app.

## Runtime and distribution boundaries

The existing TSDuck binary requires Microsoft VC runtime >=14.51.36231.0. The
reviewed portable payload does not include Microsoft binaries. The installer
route therefore checks this prerequisite and, when absent or too old, offers
the official Microsoft installer with explicit user consent. Initial setup may
need Internet access and Windows elevation for that prerequisite. A failed or
cancelled prerequisite must not be reported as successful installation.

Do not represent a hosted Windows runner with an existing runtime as a clean
Windows installation. Application/installer code signing and SmartScreen
reputation are separate from a valid SHA-256 checksum. No signing certificate
has been established for this iteration.

Preserve the exact dependency/license/source inventory gate. A new installer
must not turn an unaudited staged directory into a released distribution.

## Work and acceptance gates

1. Update and read existing operation-parity handoff before repeating discovery.
2. Repair Web BIN export/Use snapshot and Qt comparison selection restoration;
   preserve source scope, export collision refusal and stale-preview invalidation.
3. Reject any service rename that cannot round-trip through the selected
   encoding/descriptor capacity without losing provider/type or other evidence.
4. Protect an active export from normal app-close and update-install shutdown.
5. Build the final combined engine/Qt source and run protocol, lifecycle,
   operation-parity, update-client and packaging tests.
6. Run sandboxed real-browser regressions and inspect both theme layouts.
7. Run Windows production builds and installer fresh-install/reinstall/upgrade/
   uninstall checks. Record prerequisites and any missing platform acceptance.
8. Download the exact candidate artifact, validate archive/manifest/checksums,
   identify source SHA and retain the distribution review.
9. Update README, release notes and this report to match observed results.

## Initial checks and discovered risks

The existing portable-package unit suite passed 25 tests; theme contrast passed
6 tests. The baseline strict native runner passed 204 tests including the real
French recording, with zero skips. These are baseline checks, not acceptance of
subsequent changes.

A fresh native reproduction found that an over-capacity SDT service descriptor
or an unrepresentable name could produce a successful preview but lose the
service descriptor/name on export. This is a release blocker until round-trip
validation and regressions pass. Normal app shutdown during export can also
interrupt the child engine and leave an incomplete final-looking output; the
GUI lifecycle must guard this, without claiming arbitrary power-loss atomicity.

## Current state

Cloud combined validation now passes 208 strict engine/package tests, 60 Qt
UI/resource/evidence tests plus the retained smoke, 38 sandboxed Chromium tests,
40 updater cases, 17 installer contracts and 25 portable-package cases. A separate
live Qt diagnostic check and nine Linux Tauri Rust tests also passed. These suites
overlap in some packaging checks; their counts must not be added as a unique total.
The production Linux Tauri executable and final Windows CI remain separate gates.

Independent review found and repaired descriptor round-trip corruption, stale
installer stage/version binding, and unsafe replacement during active native
processes. Final Qt editor screenshots were checked after correcting vertically
clipped combo-box labels. Original failed attempts remain in the local evidence.

The user authorized publishing this branch and its PR on 2026-10-19. Hosted
Windows compilation/install/upgrade checks are next. No release assets have
been published for this iteration. Detailed local evidence is retained under
ignored `artifacts/release-readiness/` and component-specific artifact directories.
