# Qt Windows portable candidate pipeline

This implementation stages and tests a **Qt + production core** candidate. It
never publishes a release or installer. Tauri/WebView2 and the Python MCP adapter
are excluded. No owner computer is used. A staged directory or green compile
is not a downloadable cleared distribution.

## Build and staging

The existing Windows MSVC/Qt CI job first runs the existing engine and compiled
Qt regression gates. `scripts/ci/windows.ps1 -Phase Build` records the source
commit, compiler version and hashes of the two production EXEs. Packaging rejects
mismatched build identities. Qt archives are retained during dependency setup so
their exact downloaded names and SHA-256 hashes enter the package build record.

`scripts/package-windows.ps1` takes explicit BuildBin, Qt, Sdk, Output,
LicenseBundle, SourceCommit and Python paths. Output must not already exist.
It copies only the production EXEs, both matching TSDuck/TSCore 3.45-4798 DLLs,
all matching `ts*.xml`/`ts*.names` data, resources and synthetic sample. Qt runtime,
plugins and QML are selected by the pinned kit's `windeployqt --release --qmldir`.
No build-tree wildcard copy, test engine, SDK, Python or PowerShell is shipped.

The ordinary GUI is launched directly or through `Launch Qt.cmd`, using only
CMD/EXEs. Root/schema, sample and core paths are relative to the executable,
not the working directory. Missing packaged schema/core/model data produces a
visible disconnected message. Normal packaged launches clear inherited
SHOWPSISI_* development/test settings. Explicit `--showpsisi-development` allows
trusted local overrides and test hooks; ROOT/CORE/SAMPLE overrides must use
absolute paths. The package marker restricts discovery to the packaged root.

Settings remain ordinary per-user Qt settings. “Portable” means no app installer;
it does not mean all user settings stay inside the extracted directory. Exports
use the existing Save destination flow outside immutable application resources.

## VC runtime prerequisite, not silently installed

Default `-CrtMode Prerequisite` excludes VC runtime DLLs. The user needs the
Microsoft x64 VC v14 Redistributable already installed. The upstream TSDuck
3.45 build used linker/toolset **14.51.36231**; this is distinct from our own
application's compiler version and from the runtime actually loaded on a host.
Microsoft's supported deployment rule requires a runtime at least as recent as
the build tools used by the application/dependencies. The build record includes
the upstream evidence and official Microsoft prerequisite documentation.

The CI validator records version resources of System32 MSVCP140,
MSVCP140_1, VCRUNTIME140 and VCRUNTIME140_1 DLLs, records actual module load paths,
and blocks ZIP creation if the documented minimum is not met. A successful older
runtime launch is reported separately and cannot silently relax that gate.
No runtime installation occurs in this package or on the owner's computer.

Optional `-CrtMode AppLocal` copies only eligible release x64 VC143 CRT files
from the selected Visual Studio REDIST tree, never System32/developer DLLs. These
exact DLLs join the license review and minimum-version gate; this option alone
does not establish redistribution rights or sufficient runtime version.

## Verification and archive gates

`scripts/ci/portable_checks.py` has three modes:

1. `manifest`: validate required/forbidden files and hash every distributed file
   except the top-level manifest itself. Build identities and hashes are retained.
2. `validate`: copy to a path with spaces and Unicode, run from an unrelated CWD
   containing a misleading schema, remove SDK/Qt/SHOWPSISI discovery variables,
   and reduce PATH to Windows System32. Check every PE machine type/import and
   delayed import; check actual loaded module paths. Exercise production core
   capabilities, six-service fixture, named XML/raw inspection, comparison,
   rename/export/readback, source hash preservation, cancellation/rescan and EOF.
   Exercise compiled Qt offscreen smoke with screenshot/trace. Inject qoffscreen
   only into the test copy, never the shipped tree. Start the real CMD launcher
   and direct EXE with poisoned inherited test overrides, verifying their core
   child command line and module locations. Preserve complete package hashes.
3. `archive`: require validation bound to the exact manifest, a satisfied runtime
   version prerequisite, and an inventory-bound completed redistribution review.
   Only then produce the ZIP plus external SHA-256. Existing ZIPs are refused.

A cancellation request against the production fixture may race with completion;
both are reported honestly. Deterministic cancellation tests continue to use the
separate test engine in the regular regression suite, never inside the package.

The review JSON's `review_complete` must be true and `reviewed_files` must exactly
match third-party bin DLL/plugin/QML/data hashes, license/source files and notices.
Our newly built EXEs and generated config are bound to source/build/validation
identities instead of unpredictable pre-approved binary hashes. Unknown/new
third-party files and altered notices invalidate the review. The three publisher-verified Qt 6.7.3 source archives are fetched by
`scripts/prepare-portable-sources.ps1` from fixed official URLs into ignored
`.deps/portable-sources`, rehashed on cache reuse and after copying to package
`sources/`. Their exact download identities and bytes enter source-index/build
information/the manifest. A hash mismatch stops staging. Additional source
archives may be supplied in the explicit license bundle's `sources/` directory.

The checked-in notice/source templates explicitly remain incomplete and the
review remains false until the exact staged component inventory is satisfied.
See [license review](PORTABLE_LICENSE_REVIEW.md). CI retains non-binary validation
and manifest evidence even when ZIP creation/upload is blocked. The workflow
has no release publication or installer step.

## Evidence boundaries

Local implementation verification on Linux: compiled Qt/core build, the existing
Qt integration suite and focused relocation/error-path tests. Local Python tests
cover manifest tampering, required files, forbidden test payloads, stale validation,
unknown runtime files, changed notices and fail-closed archive creation.

The new Windows staging/dependency/runtime/startup checks require a hosted run at
the final source commit. Offscreen checks and visible process startup are not
Windows native file-picker/Save/Cancel/overwrite/GPU/desktop interaction acceptance.
Read-only Windows installation-directory ACL behavior, clean Windows-machine
acceptance, signing, macOS and Tauri/WebView2 remain separate unverified gates.
