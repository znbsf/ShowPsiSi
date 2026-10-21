# Unified Qt inspector — local implementation checkpoint

2026-10-21. **Incomplete delivery: source implemented and native component tested;
the complete application build and pixel review are blocked.** No remote push,
PR, release, installation or replacement of the owner's application occurred.

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
