# Unified Qt inspector — local implementation checkpoint

2026-10-21 update. **Complete Windows application now builds and runs; native
synthetic-stream workflow and five screenshots reviewed at verified 150% DPI.**
Same-owner-stream and original Library reference pixel access remain pending. No remote push,
PR, release, installation or replacement of the owner's application occurred.

## Current runnable result (supersedes earlier blocked checkpoints below)

### Final SDT name association acceptance

The legal synthetic PAT/PMT/SDT fixture now covers two named services, a service
without a name descriptor, a PAT service absent from SDT, the same SID in another
TSID, and the same TSID/SID in another ONID. Every section passes CRC validation.
The conflicting identities are deliberate test observations, not a claim that
multiple actual transport identities represent a normal single broadcast.

This exposed two defects. The summary's unqualified `state` resolved to the
TextLabel's inherited QQuickItem state, so the full GUI could not find service
names even when engine and JavaScript tests passed. It now explicitly reads
`view.state`. The engine now marks whether a nonempty name came from a decoded
descriptor; internal fallback `Service 103` is no longer presented as a wire
name in the PAT summary. Existing SDT source IDs and ONID/TSID/SID are retained,
and extensions cannot override the provenance flag. Ambiguous ONIDs remain
explicitly ambiguous because PAT does not provide an ONID to disambiguate them.

Validation: native service-name scenarios **4/4 pass**, real engine identity and
source-descriptor assertions pass, model identity assertions pass, section tests
**18/18**, unified engine test **1/1**, existing model **43 assertions**, and full
native application **24/24**. The existing resume-state wait is now recorded as
an explicit assertion; earlier reports described 24 but stored 23 named checks.
No scan behavior was changed. The final two native application logs are empty.

Evidence under `artifacts/unified-inspector`: `service-identity-evidence.json`,
`service-engine-test.log`, `service-model-test.log`, `service-native-test.log`,
`service-final-regression.log`, `service-section-tests.log`,
`service-unified-test.log`, `service-existing-model.log`.
Final native runs: `service-visual-1792593649263583200` and
`full-app-keyboard-1792593652693953200`.
Four pixel-reviewed 150% screenshots from the same final executable are copied
as `service-distinct-4097-150.png`, `service-distinct-4098-150.png`,
`service-ambiguous-4097-150.png`, `service-ambiguous-4098-150.png`.
They show Alpha News/Beta Music, transport-separated Other Transport, explicit
ambiguity and unknown names without clipping or an additional selection pane.

The last build exited zero. All six authorized Qt tools were restored to exact
original full security descriptors with unchanged hashes (`approved-six-operation.json`).
No additional tools, parent directories, DACLs, owners or protection settings
were changed. No Library retry, push, publication or installation was made.
Only the unavailable owner stream and original Library reference pixels remain
external acceptance boundaries; earlier checkpoint limits below are historical.

### Layout feedback repair

The remaining layout warnings are now resolved in the tested paths. With
`QT_LOGGING_RULES=qt.quick.layouts.debug=true`, each warning was preceded by
`QQuickGridLayoutBase::rearrange 2 LookupTable` for `satelliteResult` or
`identifierResult`. All four combinations of basic/advanced and empty/auto-load
produced exactly two warnings before the fix, proving a startup lookup-layout
issue independent of scanning or the unified inspector.

LookupTable was itself a ColumnLayout whose implicit width came from child
preferred widths calculated as fractions of LookupTable.width. The resulting
width feedback occurred even while the lookup results were hidden. The root is
now an Item with width assigned by its containing layout; its inner ColumnLayout
is anchored to that width and only supplies implicit height. Column proportions,
wrapping, focus and accessibility are retained. No warning filter or timer was
used to conceal the problem.

After rebuilding, all four diagnostic runs have zero recursive-layout warnings;
the full 24-check native run and both existing identifier/satellite lookup tests
pass. The final native application log is empty. Reproducer:
`tests/verify_lookup_layout.py`. Evidence under `artifacts/unified-inspector`:
`layout-after.log`, `lookup-visible-tests.log`, `layout-final-regression.log`,
before debug logs in `full-app-keyboard-1792592690806945500`, after debug logs in
`full-app-keyboard-1792592858868958500`, and full-app log in
`full-app-keyboard-1792592873295417200/application.log`.

The final 150% PAT/PMT/BAT/TDT/TOT PNG hashes exactly match the previously
pixel-reviewed integrated screenshots. New pagination and EIT captures and the
two advanced-test screenshots were also inspected. Copies are named
`layout-fixed-<scene>-150.png`. This iteration made no Library upload attempt.
The six approved build tools again have their original full security descriptors
and hashes, recorded in `approved-six-operation.json`. Original stream/reference
availability remain the external acceptance limits; SDT-name visual coverage is now complete below.

### Baseline correction and latest-main integration

The initial choice of owner branch e80dabb was incorrect for the requirement to
retain latest-main analysis features: `merge-base HEAD origin/main` was e80dabb,
meaning that branch was an ancestor of main, not that it contained main. The
earlier ancestry conclusion and statement that the baseline lacked pause/resume
must not be used as final acceptance. Read-only `git ls-remote` confirmed both
main and v0.3.1 at ae2c82e37f7bc56f6e60fcec4c945d57b14cec26. Main includes PR28
and its compact result hydration, in-process pause/resume, full/prefix/range/
distributed analysis and percentage coverage.

Main was merged into this independent branch, preserving every previous local
commit. Only core summary and QML diagnostic dispatch conflicted. Resolution
retains both short-syntax TDT/TOT truthfulness and main's includeDistribution
optimization and busy/presentation guards. The Qt bridge and Web app are
unchanged from main. No parser rewrite or removal of sampling functionality.

Final real Windows app report: `artifacts/unified-inspector/main-integrated-final.log`.
All 24 checks pass, including observed paused state with a frozen packet count,
resume, pause again and cancel, reopen, prefix/distributed 10% exact budgets,
range coverage, all 101 compact-hydrated records, second-page keyboard selection,
and separate EIT sections 0 and 8. The initial integrated test failed because
the old test watched stale analysisState rather than main's separate scanProgress;
that failed log is retained, and the test was corrected without changing the
engine contract. A null-packet source avoids creating millions of artificial
history transitions merely to test pause.

Native file-picker testing also passed using the actual Windows #32770 dialog
owned by the test application: enter a new synthetic TS filename in control
1148, invoke Open, then verify the selected file was loaded. Reproducer:
`tests/verify_native_picker.py`; result:
`artifacts/unified-inspector/native-picker-1792592386665696100/report.json`.
Core section-evidence 18 tests, unified engine regression 1 test and presentation
model 43 assertions pass after the merge.

Seven final 150% screenshots were pixel reviewed, including pagination and EIT:
`integrated-PAT-150.png`, `integrated-PMT-150.png`, `integrated-BAT-150.png`,
`integrated-TDT-150.png`, `integrated-TOT-150.png`, `integrated-page2-150.png`,
`integrated-EIT-150.png`. A stale cancellation warning after a successful rescan
was fixed and rechecked. The invalid Accessible attachment was removed and its
warning is absent; two recursive layout warnings per launch remain unresolved.
The fixture still has no SDT service names; original same-stream acceptance and
original Library reference pixel access remain unavailable.

All approved six-tool build cycles restored exact original security descriptors
and hashes, including the latest `approved-six-operation.json`; no new tool was
modified. The five new integrated full-app images were offered once to the
current official Library prepared uploader. Preparation failed with
`library upload failed: prepare_uploads failed`; no confirmed IDs, no alternate
transfer and no blind retry. These are distinct from the earlier component
upload whose outcome was unconfirmed.

The following earlier checkpoint details are retained as history; the integrated
results above supersede its missing-pause, pagination and file-picker limitations.

Launch `scripts/run-unified-local.ps1`, optionally with `-Sample <absolute TS path>`.
It runs this worktree's `build/bin/showpsisi-qt.exe` with separate settings and
the original shared SDK runtime, without modifying installed application files.

User approval for six exact Qt tools resolved the full build. Two build cycles
completed with exit 0. Both restored all six exact original security descriptors
and content hashes in finally blocks; qmltestrunner was not modified. Evidence:
`artifacts/unified-inspector/approved-six-operation-build1.json` and
`approved-six-operation.json`, plus `approved-six-gui-build.log`.

The complete application (not qmltestrunner) was run with the real C++ backend.
`tests/verify_unified_native.py` reproduces the native diagnostic-session checks.
The 11 checks in `full-app-keyboard/report.json` pass: initial open, five table
selections, Alt+Left restoring field path, repeat scan, F6/Home/Enter selection,
cancel a repeated synthetic stream, and reopen after cancellation. File loading
uses the application's source/scan path via its explicitly enabled local
diagnostic session; the native OS file picker itself was not exercised.

Five full-app screenshots under `full-app-150-corrected` were inspected as pixels:
PAT program/PMT association; PMT descriptor fields; BAT fields with exact hex;
TDT/TOT UTC observations without invented long-header fields. The window is
1280x800 logical and captures are 1920x1200 pixels. The first run accidentally
multiplied system 200% by requested 150%; that evidence is retained in
`full-app-150` but is NOT claimed as 150% acceptance. Test-only high-DPI settings
corrected the second run without changing Windows settings. Convenient unchanged
copies of reviewed screenshots are `full-PAT-150.png` through `full-TOT-150.png`.

Remaining limits: checked core/Qt baseline has no pause/resume API, so that
workflow is NOT RUN (cancel/reopen is not pause/resume). Full-app long-table
pagination and multi-section EIT are not yet exercised. Fixture lacks service
names. Owner stream remains unavailable. User reference pixels remain blocked
by the official materializer. Runtime logs retain an Accessible attachment
warning and two recursive-layout warnings; no crash or unreadable fields were
observed in reviewed scenes. No claim that these warnings are resolved.

Official Library exact-name search returned no confirmed matches for any of
the five prior component screenshots. No Library IDs are confirmed; no blind
repeat upload was made. Local full-app PNGs are available for delivery.

## Source and isolation

- Worktree: `C:\Users\hentai\Documents\Codex\2026-10-21\task-4\ShowPsiSi`.
- Branch: `ui/unified-inspector`.
- Base: `e80dabb692ca055eaf735d170976ab6787f624c5`, the owner's existing
  `ui/ux-refinement` work. Fetched `origin/main` was
  `ae2c82e37f7bc56f6e60fcec4c945d57b14cec26`; ancestry check succeeded.
- Original checkout remains on its branch, with only its original untracked
  `.claude/` directory. Existing scan/lifecycle code was not rewritten.
- No `.agents` skill files were found in the checkout. Repository AGENTS and its
  delivery/architecture/validation guidance were reviewed.

## Implemented

The default Qt view is a unified structure navigator and a wide, flat field
viewer. The previous workspace, timeline, diagnostics and Agent controls remain
available through Advanced workspace. Open/analyze and existing scan controls
remain shared with the original application.

The navigator retains every engine section content identity, version,
current/next state and section number. It shows repeat counts separately,
pages records by 100, and expands long child collections in batches of 100.
The detail side shows a protocol summary, field/value/explanation columns and
optional exact-section Hex. No guessed bit widths or native-field byte offsets
are introduced. Descriptor byte ranges come from the engine.

PAT summaries associate program and PMT PID, and show a service name only when
the TSID/SID match is unambiguous across the observed service identities. PMT,
BAT, SDT and NIT retain decoded structures. An SDK table tree is treated as
section-local only when the engine reports one source whose ID equals the
selected section; a multiple-source assembly is not presented as that section.
The previous Advanced workspace retains merged inspection.

TDT/TOT summaries now expose their existing decoded UTC time and explicitly
omit version/current-next/extension/section numbering. CRC evidence remains
engine-owned: TDT has none, TOT has a CRC. Parsing, content identity, observation
history and scanning were not replaced.

## Verification

Commands used the existing MSVC 19.44, Qt 6.7.3 and TSDuck 3.45-4798 SDKs.
Local generated inputs and evidence are ignored in `artifacts/unified-inspector`.

| Check | Result |
| --- | --- |
| Native `showpsisi-core` compile/link | PASS |
| `python -m unittest discover -s tests -p test_engine.py -q` | 34 run, 33 passed, 1 existing skip |
| `python -m unittest discover -s tests -p test_unified_inspector.py -v` | PASS; real engine, synthetic PAT/PMT/BAT/TDT/TOT |
| `node tests/test_inspector_model.cjs` | PASS, 41 assertions |
| `python -m unittest discover -s tests -p test_section_evidence.py -q` | PASS, 18 tests |
| Qt component tests at 1280×800 logical pixels | Navigation/Back/BAT Hex/keyboard tests passed |
| Final Qt component tests at 150% DPI | 4 passed including setup/cleanup; exit 0 |
| Full application Qt build | BLOCKED: Qt tools cannot create output files |
| Native component screenshot save | FAILED: access denied; retained failing test/log |
| Reference-image pixels | NOT AVAILABLE: official Library helper lacks Windows `os.setxattr` |
| Full-app open/reopen, pause/resume/cancel, all-scene visual review | NOT RUN on new application |
| Owner's HD+ stream | NOT RUN; supplied D: path does not exist here |

The component tests consume JSON produced by the newly compiled real parser.
They exercise the actual QML component with an in-memory selection host, **not**
the complete application bridge. They do not establish native full-app workflow
acceptance. Screenshot and application-build failures remain failures.

The new engine regression covers PAT v31 current versus next, v31→v0→v31,
TDT/TOT A→B→A contents with exact repeat counts, absent short-header semantics,
and TDT/TOT CRC differences. Model checks also reject mismatched/multiple SDK
sources and ambiguous service names.

## Exact blockers and attempted recovery

1. `qmlimportscanner.exe` could read QML but could not create its generated
   output under this worktree or the allowed temporary directory, even with
   escalated execution. A supported local no-import-scan diagnostic reached
   `moc.exe`, which then failed:
   `Cannot create .../build/showpsisi-qt_autogen/include/main.moc. Error: Permission denied`.
   The diagnostic CMake change was removed. No security settings were changed.
   Status: denied file-write operation; no new Qt application executable.
2. QtTest `grabImage(inspector).save(...)` failed at
   `artifacts/unified-inspector/PAT.png` with `Cannot open device for writing:
   access denied`. No image was produced, and no pixel review is claimed.
   `qml-component-test.log` preserves the failure. Independent non-capture tests
   were run separately at 150% DPI and retained in `qml-component-dpi150.log`.
3. Official Library preparation for all three user IDs returned transfers. The
   unmodified official helper downloaded the first reference but failed before
   installation at `os.setxattr`, unavailable in Windows Python. No completed
   materialized image exists. No alternate URL or environment transfer was used.
4. A separate-settings launch using `QML_IMPORT_PATH` still resolved the existing
   application's embedded QML. This did not run the new view and is not a valid
   comparison build. Only our two launch processes were stopped afterward.

## Resume

First restore a supported Qt build/screenshot file-write capability in the
selected environment and a Windows-compatible official Library materializer.
Do not change the original checkout or installed application to achieve this.
Build the isolated worktree normally, then run the complete app with isolated
settings and the retained synthetic fixture. Finish the five screenshot scenes,
tree/Back/search/page/reopen/lifecycle checks and visual repair loop. The owner
stream comparison remains pending until its authorized path is accessible.

The existing compiled engine can be run at `build/bin/showpsisi-core.exe`.
There is **no validated new GUI launch path** in this checkpoint.

## Read-only permission diagnosis and independent review follow-up

The pre-existing Qt tools have an inherited Low/NoWriteUp mandatory label from
the original repository root. A formally elevated Medium parent was measured
starting a Low Qt child. Targets have ordinary integrity. Vendor signatures for
moc, qmlimportscanner and qmltestrunner are valid (The Qt Company Oy, 6.7.3.0).
No labels or permissions were changed. The exact baseline and limited approval
proposal are in ignored `artifacts/unified-inspector/qt-security-readonly-baseline.json`
and `qt-label-approval-plan.md`. Changing shared tool files cannot be scoped to
this task's callers alone. Other required build tools are not implicitly included.

Independent code review fixed Back while inspection is pending (history is no
longer consumed), preserves expanded-page limits on Back, resets limits for a
new source, guards missing selections, and uses path lookup rather than flattening
the entire decoded tree to select one node. Model assertions now total 43.
Native non-capture component tests at 150% DPI pass (5 including setup/cleanup).
No denied screenshot or build write was retried during this follow-up. This does
not resolve the pending complete-app and visual acceptance gates.

## Authorized build and visual iteration (2026-10-21)

The user subsequently approved temporary Medium/NoWriteUp labels for exactly
the original SDK's moc.exe, qmlimportscanner.exe and qmltestrunner.exe. Baseline
hashes, full security descriptors and valid Qt signatures were checked before
execution. Only the label was changed; parent directories, DACLs and owners
were not changed. All three original descriptors and hashes were restored and
verified in a finally block, including after the failed application build.
`approved-qt-operation-first.json` records this cycle. A second capture-only
cycle changed only qmltestrunner and again restored its exact original state;
`approved-qt-operation.json` records that cycle.

The full GUI build still exits 1: unapproved tools under the same original SDK
bin directory, `rcc.exe` and `cmake_automoc_parser.exe`, cannot write generated
resource sources and the metatype timestamp in this worktree. Their inherited
Low/NoWriteUp labels remain untouched. Both signatures are valid Qt 6.7.3.0.
`approved-gui-build.log` preserves complete commands and errors. This is a
Windows file-write denial, not an automatic approval rejection. Authorization
was not expanded to either tool or any later build tool.

The real native Qt component suite passes 6 tests (including setup/cleanup).
Five synthetic-parser-data screenshots were saved and visually inspected.
The first images exposed DPI cropping and offscreen selected navigation nodes.
The second iteration uses whole-item QQuickItem capture and scrolls the selected
node into view. All five `PAT-review2.png`, `PMT-review2.png`, `BAT-review2.png`,
`TDT-review2.png`, and `TOT-review2.png` were inspected as pixels: complete field
tables, exact BAT hex, PMT descriptor, PAT current/next versions, and distinct UTC
observations are visible. Short syntax does not display invented version/current
or section identities. The fixture lacks SDT names, so PAT service-name visual
acceptance remains uncovered. The capture log is `approved-component-capture.log`.

These are **component screenshots, not a completed full-application run**.
Opening/reopening files, pause/resume/cancel, full bridge interaction, and the
owner's same-stream comparison remain NOT RUN. User reference image pixels
remain unavailable through the failed official Library helper. There is still
no validated new GUI executable/launch path. The next step requires a separately
approved, precisely scoped resolution for the remaining build-tool write
denials; the existing three-tool approval does not cover those tools.
