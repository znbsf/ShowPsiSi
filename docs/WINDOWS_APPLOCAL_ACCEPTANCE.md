# Windows app-local runtime acceptance

This is an acceptance procedure, not a record of a completed clean-Windows run.
It complements the package/source identity gates, static PE closure, portable
preflight and actual loaded-module checks. Do not label an equipped hosted
runner, a Linux unit test, or an offscreen Qt screenshot as clean desktop
acceptance. The helper and these instructions stay outside distributable payloads.

## Four independent conclusions

1. **Inventory:** the exact eligible x64 release DLLs, source and hashes are
   reviewed, and every normal/delay import in the final PE inventory resolves.
2. **Observed loading:** the real Qt and core processes load the matching VC
   bytes from this package's `bin`, including transitive Qt imports. An adequate
   shared runtime on the runner cannot satisfy this assertion.
3. **Clean offline standard-user operation:** an independently recorded
   disposable Windows baseline without shared VC v14 runs the exact installer
   and ZIP offline under a real standard account, without a runtime installer
   or elevation. Neither inventory nor loaded paths proves this alone.
4. **Native workflow:** actual window interaction, file dialogs, parser,
   preview/export/readback, restart and installation lifecycle work on that
   exact candidate. Starting a process alone does not prove this.

Report each conclusion separately as passed, failed, or not run. Keep the
supported Windows 10 1809+/11 **native x64** boundary. Windows UCRT and
D3Dcompiler_47 remain OS dependencies; no System32 copies belong in the package.

## Test images and identity

Use disposable images, never an owner's working PC. Do not uninstall, rename,
quarantine, overwrite or change permissions on shared runtime/Windows files to
simulate a clean image. Provision an appropriate fresh image or mark the test
blocked. Do not disable security software, signing checks, script policy or UAC.

Required image coverage:

- Windows 10 1809 client (the declared floor), native x64, no shared VC v14,
  genuine non-administrator account. If unavailable, the floor remains untested.
- A documented Windows 11 client build, native x64, no shared VC v14, same account
  and offline conditions. Avoid a default VM account that is an administrator.
- A separate image with a recorded newer/suitable shared VC v14: bundled module
  paths must still win. Do not use its success for the first two rows.
- Existing v0.2.0 installation with its actual system-runtime prerequisite,
  retained settings and external export fixtures, for upgrade/uninstall checks.

Record the exact image origin/build, snapshot identifier, candidate source SHA,
ZIP/setup SHA-256, manifest/runtime metadata hashes, and test start/end UTC. A
remote branch name or a green result for another SHA is insufficient. Review
VM provisioning separately if it would install software or change access.

`scripts/ci/record_windows_acceptance_host.ps1` reads the native architecture,
Windows build, current token's administrator status, all five required System32
VC files, other v14 family files, Windows UCRT/D3Dcompiler, and optionally exact
input file hashes. It never executes a candidate or downloads anything. It uses
built-in Windows PowerShell/.NET, not Python, VS, PowerShell 7, or a Qt SDK.
An existing output is refused; partial/failing reports are retained.

In an already provisioned test VM, create an evidence directory outside both the
package and installation, then run from native x64 Windows PowerShell:

```powershell
& .\scripts\ci\record_windows_acceptance_host.ps1 `
  -Output 'C:\Acceptance\before.json' -Profile CleanNoSharedVc `
  -Artifact @('C:\Inputs\candidate-setup.exe', 'C:\Inputs\candidate-portable.zip')
```

Use `-Profile Observe` to record an equipped/lifecycle image. A successful
`Observe` report is only successful collection. `CleanNoSharedVc` also rejects
Server, old builds, ARM64/emulated processes, any required/additional shared v14
DLL, missing UCRT/D3Dcompiler, non-interactive/service tokens and filtered-admin
accounts. It does not prove
that VS or every developer tool is absent: retain the image provisioning record.
An incomplete snapshot is a failure, never evidence of absent DLLs.

The architecture check uses [IsWow64Process2](https://learn.microsoft.com/en-us/windows/win32/api/wow64apiset/nf-wow64apiset-iswow64process2).
A 64-bit process or [GetNativeSystemInfo](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getnativesysteminfo)
alone can misidentify x64 emulation on ARM64. Administrator-group SID presence
is checked as well as effective administrator status, so an ordinary
non-elevated administrator token does not pass as a standard account.

Disconnect networking using the test platform's already-authorized isolation
controls and retain that configuration evidence. Adapter status alone does not
prove offline isolation. The helper leaves `offline_verified`,
`no_runtime_installer_verified` and `native_windows_desktop_verified` false:
those require the separate observations below. No security/network setting is
changed by the helper.

## Actual loaded-module evidence

Run package validation with a relocated copy in a Unicode/space path, an
unrelated working directory, and cleared development/Qt/TSDuck environment
settings. Use separate evidence directories; never alter the reviewed payload.

For every observed core and Qt process, keep:

- PID **and creation time**, executable path and exact hash, launch route,
  command line, sample time, original unfiltered module paths, and any process
  inspection error. Do not select a process only by its name or reuse a PID.
- Each relevant loaded VC module's canonical path, filesystem identity,
  SHA-256, fixed file-version tuple and architecture, bound to the reviewed
  manifest/runtime inventory. Check both exact location and bytes: a matching
  hash somewhere in System32 or a neighboring package is still a failure.
- Required normal import closure for each executable, following bundled Qt,
  TSDuck and TSCore libraries; statically cover delay imports and require their
  modules in a sample only after exercising the associated feature.
- Samples after capabilities/startup and after analysis/export plus Qt render
  and required plugin loading. Retain an early-exit code in unsigned hex and
  logs if enumeration cannot run; an empty/unreadable snapshot cannot pass.

Required current inventory includes `msvcp140.dll`, `msvcp140_1.dll`,
`msvcp140_2.dll`, `vcruntime140.dll` and `vcruntime140_1.dll`. The `_2` file is
imported transitively by Qt6Gui/Qt6Quick; do not inspect only the EXE's direct
imports. Qt coverage must observe it. Do **not** require a Qt-only module in
core unless core's actual closure requires it. Across the exercised Qt/core
paths, every declared required runtime must have valid observed evidence.

Reject every observed VC-family module outside the reviewed `bin`, including
newer System32 copies, duplicate names, unreviewed/debug/legacy VC files, or a
same-prefix directory such as `bin-old`. Keep Windows OS components separate.
Do not blacklist the legitimate OS `msvcrt.dll` or `msvcp_win.dll` as though they
were a separately redistributed VC v14 library. The raw evidence must survive a
failed assertion; a failure must not erase earlier valid observations.

A hash of the backing file proves the observed path's on-disk identity at the
sample time; it is not a measurement of every in-memory page or a guarantee
against later replacement. Snapshot enumeration also cannot establish the
absence of short-lived child processes or all dynamic-load feature paths.

## Portable and installer scenarios

For **each clean image**, from a fresh snapshot:

1. Verify exact ZIP hash, extract all files into a new path such as
   `C:\Acceptance\Portable 测试\App`. Keep the original archive and manifest.
   Launch `Launch Qt.cmd` from an unrelated current directory. Confirm a visible
   Qt window and the matching package core child, then capture loaded modules.
2. Repeat through the direct packaged Qt EXE. This bypasses friendly CMD
   diagnostics, but its native dependencies still must resolve app-locally.
   Repeat from Explorer for native launcher/quoting behavior.
3. Parse the packaged deterministic lab sample: expect its documented six
   services and two deliberate CRC errors. Inspect original bytes/XML, preview
   a Unicode service rename, export SI-only TS and BIN to a separate writable
   directory, preserve the BIN manifest, and read both outputs back through
   the production core. Assert the intended name/source identity and unchanged
   input; a successful save notification is insufficient.
4. Exercise actual Save/Cancel, existing destination collision, reopen, close,
   and restart. Confirm no development paths or injected test variables affect
   normal launch. Do not use the offscreen plugin for native desktop evidence.
5. Restore the clean snapshot and run the exact setup normally as the same
   standard user, with a retained explicit setup `/LOG` path. Verify default
   per-user install, optional shortcuts, installed marker, installed launch,
   module paths and the workflow above. No VC_redist download/install prompt,
   UAC request or runtime installer may occur in this app-local route.
6. Uninstall normally after closing Qt/core. Only app-owned installation files
   and registrations are removed; external exports/settings remain. Compare
   before/after host evidence and relevant installation ownership inventory.

Record the complete setup/launcher interval with an already-authorized process
creation audit (for example a test platform's existing observer) and UI evidence
if claiming that no runtime installer/UAC ran. A late process snapshot, unchanged
shared DLL hashes, or a setup exit code alone cannot prove the absence of a
short-lived installer. Observer elevation, if required by its tool, must not
change the application's standard-user execution token. If no such evidence is
available, report the no-installer claim as unverified rather than infer it.

On the lifecycle image test current v0.2.0 → candidate, same-version reinstall,
blocked downgrade, custom Unicode installation path, cancelled setup, Qt/core
active-process guard and active-export refusal. Existing newer shared VC files
must remain byte-identical. Close windows normally; terminate only processes
explicitly created and identified by this test if bounded cleanup is needed.

## Failure and no-fallback cases

Mutate only a fresh disposable **copy** of the candidate. Keep the original
runtime/metadata hashes, the exact mutation and retained stdout/stderr/status.
Run these on the equipped image too, where system fallback could hide a defect:

- Remove each required local DLL, especially `msvcp140_2.dll`. Friendly launcher
  preflight must fail before GUI launch even if System32 has a good copy.
- Replace one local DLL with a too-old version-resource fixture, a wrong-machine
  PE fixture, a truncated file, and a byte-tampered file retaining its version.
  Feed these only to preflight; do not execute mutated native code.
- Missing/malformed runtime metadata, wrong expected hash/version, duplicate or
  omitted inventory item: reject instead of defaulting to system runtime.
- Module evaluator receives a plausible complete list containing a System32 VC
  DLL, another package's DLL, unknown/debug VC DLL, empty list, missing Qt `_2`,
  or inaccessible process: fail and retain the raw observation.
- Assert deterministic exit status and a useful diagnostic naming the stage,
  affected file/path, observed versus expected values when known, and retained
  evidence location. Use decimal plus 32-bit hex for Windows failure codes.
  Do not infer antivirus, ACL damage, or UAC refusal from general access denied.
- Check 32-bit/native-architecture mismatch and Windows support floor refusal
  separately; never patch host version/security values to force acceptance.

Core alone may legitimately lack `_2`; that is a positive evaluator fixture,
while the same omission from the required Qt closure is a negative fixture.
For normal-module race handling, retry only within a bounded readiness window
and retain the original exception. Never convert a timeout or denied read into
an empty successful list.

## Helper verification and release gate

The collector has a native test suite:

```text
python -m unittest discover -s tests -p test_windows_acceptance_host.py -v
```

It exercises real Windows PowerShell collection, exact input hashing, stale
report refusal, retained failure records, and whether the strict clean profile
matches actual host facts. It needs no app installation. On Linux the native
cases are explicitly skipped; that is not a Windows pass. Run it on the Windows
CI host and again when provisioning the acceptance image if Python is already
available. Do not install Python/VS into an image just to make it appear tested;
the PowerShell collector itself can be run independently on a clean VM.

This change's Linux source review does not establish PowerShell runtime success,
module enumeration, offline/native desktop acceptance, code signing reputation,
or distributor entitlement. App-local redistribution remains conditional on the
applicable [Microsoft redistribution terms](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files).
Keep the current exact-byte distribution review gate. No acceptance helper
publishes artifacts or authorizes a release.
