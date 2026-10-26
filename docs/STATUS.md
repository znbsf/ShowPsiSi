# ShowPsiSi status

2026-10-27 step 15 implemented: stable PES/ES inventory, exact source-byte
jumps (including existing packet-window relocation), bounded real frame/PCM
preview and token-scoped Windows output. 29 media/analysis-cancellation checks
plus two browser chains pass; full Qt video, waveform, silent pause/resume and
close-release pass. The accepted single-I-frame remux also renders in Qt with
exact source ES identity. External pinned FFmpeg is optional and not bundled;
preview pacing/downmix is derived, original A/V synchronization is not inferred.
Next: outputs/copy/settings (16), then native/DPI/exit acceptance (17). No CI.

2026-10-26 step 14 implemented: actual PES Teletext page/subpage/capture
navigation in both UIs, 40-column display, supported colours/mosaics/double
height, conceal/flash controls and exact unit source packets. 29 related local
checks pass. Real explicit-PID test-012 page 889 has 9 subtitle events / 18
lines matching independent SRT in core, browser display and full Qt offscreen.
Invalid PAT remains an explicit-PID-only boundary. Next: PES/ES/media (15);
outputs (16) and native acceptance (17) remain. No hosted CI.

2026-10-26 step 13 content browsing implemented in both UIs: DSM-CC module
identity/missing blocks, DSI ObjectLocation, BIOP inventory/bindings, paged
immutable content, strict UTF-8 and read-only class interpretation. 45 local
checks pass; real reconstructed M12 eight-class and M13 configuration window
chains pass in browser and full Qt offscreen. Export remains step 16; native
mouse/DPI remains step 17. Next: Teletext pages (14). No hosted CI.

2026-10-26 step 12 implemented: scoped Service / ES / EPG / Applications
windows in both UIs, exact section navigation and restored context. Ambiguous
SDT/PAT identities withhold PMT association. 36 related local checks pass; full
Qt offscreen service inspection passes. Next: DSM-CC/BIOP contents (13).
No hosted CI. Native mouse/DPI acceptance remains step 17.

2026-10-26 steps 07–11 implemented: independent document instances, observed-PID
and DSMCC branches with exact pointer context, source packet navigation,
verified cross-packet section fragments, and bounded PCR/continuity evidence
with Bitrate/Timing views. Latest combined local suite: 40 passed, no skips.
Qt components: 52 actual cases / 60 PASS including lifecycle; complete Qt
offscreen checks cover real Hotbird windows, packet bytes and measured PCR.
Final native Tauri restaging and mouse/DPI acceptance remain step 17.
Next: step 12 service / EIT / AIT provenance navigation. No hosted CI.

2026-10-26 step 06 implemented: original toolbar bitmap and shared menu rules,
Ready/Start file flow, reversible tree/toolbar/status visibility, and Summary
alongside the left tree. Qt local build + 10 full-app offscreen observations,
47 component cases and 10 browser/resource checks pass. Native desktop
interaction and pixel matching remain separate acceptance. Next: step 07
independent document windows. No hosted CI.

2026-10-26 ordered plan steps 01–05 implemented and pushed (application source
`ec2b993`): rejected candidates preserve the old session; Back restores exact
field and pane positions; unmapped bytes clear stale ranges; Summary has six
matching metrics; tree/hex/focus keyboard navigation is aligned. Both native
release candidates build locally and display the same real Hotbird PMT.
Local evidence and the corrected asynchronous preview test are recorded in
[NXTSA parity checkpoint](NXTSA_UI_UX_PARITY.md#前五项交付检查点2026-10-26源码-ec2b993).
No hosted CI was started or polled. Plan 06–17 remains pending; the next item is
the original application frame. The proposed delayed-start card never became
a saved automation; work resumed directly after the user follow-up.


2026-10-25 generic SI hierarchy and interaction correction: available native
structures are now projected for every table family, preserving exact wire
loops and explicit assembled-table scope. The 52 pinned reference inputs pass
904 model assertions. Both trees now distinguish text single/double click from
single-click +/-. Field grid columns remain aligned on resize/scroll, and field
folding retains viewport position. 38 component cases and 22 full-app checks
passed; native Windows mouse checks verified the repaired behavior and column
drag alignment. Final local candidate is open; patch remains uncommitted.
[Scope and evidence](NXTSA_UI_UX_PARITY.md#generic-hierarchy-and-interaction-local-acceptance).

2026-10-25 SI internal hierarchy correction: left trees now expose PMT ES and
descriptors, NIT/BAT ONID/TSID transports and descriptors, and other supported
wire-loop nodes. Cached branches coexist and child selection restores the exact
owner before field/hex navigation. Long labels scroll horizontally. 83 model
assertions, 33 component cases and 14 full-app checks passed; a native Windows
teletext-descriptor click also verified field/dual-hex positioning. Candidate
is open locally; these changes remain uncommitted.
[Scope and evidence](NXTSA_UI_UX_PARITY.md#internal-si-tree-local-acceptance).

2026-10-25 local interaction repair: SI detail no longer clears during an
in-flight selection, and keyed navigation preserves clicked-row position.
Field columns support drag sizing, double-click fit and horizontal scrolling.
31 component test cases and nine full-app SI checks passed; the new local
candidate is open for user review. Native click/drag automation stopped when
concurrent user input was detected. See [evidence](NXTSA_UI_UX_PARITY.md#treecolumns-local-candidate-result).
Changes remain local and uncommitted.

2026-10-25 local Qt build blocker resolved: the actual Qt scanner runs at Low
integrity and cannot write to the Medium worktree. Building current sources
into an existing inherited-Low output directory succeeds without ACL changes.
The locally built full app passed nine offscreen classic-SI checks. See
[diagnosis and evidence](NXTSA_UI_UX_PARITY.md#local-build-blocker-resolved-2026-10-25).
The earlier pending-build notes below are historical; native desktop/dialog
acceptance remains separate. Build-script follow-up changes are local only.

2026-10-25 follow-up: the classic SI tree now organizes declared networks / TP /
programs, with SDT names and resolved LCN. Unknown or conflicting identities
remain explicit; program selection retains field/hex linkage. Local real-engine
checks: 4 inspector + 35 topology tests; 70 model assertions; 31 Qt component
passes at 150% (including setup/cleanup). Complete Windows build is moving to
the existing hosted route because the shared SDK integrity labels are unchanged.
Hosted and complete application acceptance are pending, not implied by these checks.

2026-10-25 latest user correction: core SI now follows original NxTSA visuals:
white/light-gray surfaces, actual original bitmap icons, boxed/dotted trees,
red field values, yellow selection, and source-packet / Section dual hex panes.
The source-packet pane and both directions of selection are functional with
real engine output, not screenshot mockups. See [visual requirements](UI_UX_STANDARDS.md)
and [current parity evidence](NXTSA_UI_UX_PARITY.md). Complete app/native acceptance
remains pending under the previously documented Qt generator write blocker.
The earlier dark core-SI preview below is superseded by this visual slice.

2026-10-25 core SI priority: Qt now has table-family navigation, an expandable
Field / Bits / Value / Comment table and bidirectional Section-byte selection.
C++ `inspect.si_structure` supplies exact MSB-first ranges; unknown ranges stay
explicit. Real-engine component checks and original Hotbird PMT evidence are in
[the current UI parity record](NXTSA_UI_UX_PARITY.md). This is source/component
implementation; complete new Qt build/native acceptance and the original
separate TS-packet hex pane remain pending.

2026-10-25 — NxTSA复刻P1（源码/组件阶段）：
已fetch远端main de2b1d5，在codex/nxtsa-summary-pid保留当前改动。
新增C++全PID统计/query_transport与Qt Summary/Error、排序分页、来源导航和返回状态，
修复PID/extension碰撞、聚合来源误跳和筛选后Back；保留既有工作区。
严格引擎30组/650项（649通过、1项可选样本缺失skip），
Qt组件100%/150%各25 PASS（21实际用例+4setup/cleanup），深浅主题截图已复核。
**完整新Qt仍受SDK生成工具写入权限阻塞；新代码实机NOT_RUN**，
用户可见Qt仍为旧main CI产物，不能把组件测试等同完整应用通过。
[当前P1合同、准确边界和下一Raw Packet设计](NXTSA_UI_UX_PARITY.md)；
[初始45个原版/旧main Qt操作场景](NXTSA_BEHAVIOR_REFERENCE.md)保留版本范围。
本阶段未push、发布或安装；托管CI与完整候选包仍是后续门槛。

Latest operation audit and handoff, 2026-10-18, on merged main `88506ba`:
real Windows Qt/WebView2 edit, export and A/B comparison checks found remaining
functional gaps, including Web BIN export / Use snapshot, Qt selection restore
and source-evidence navigation. These are **not fixed** by the documentation
handoff. Successful export readback, repro steps, local evidence and next
acceptance gates are recorded in [the operation handoff](OPERATIONS_PARITY_HANDOFF.md).
PR #18 and its postmerge CI are complete; this audit supersedes broad native
Save-dialog unknowns below only for the explicitly exercised sample and flows.

Workbench parity and all-table history, 2026-10-18, based on main `35bb665`:
Qt/Web share `ui/tauri/web/workbench.js` for table/section counts, multiword
search, ordering, structure-tree nodes and history scope. Both retain invalid
groups, grouped/flat modes, 100-item pages and all six inspector views.
Engine `table_history` covers all captured families, including short/private/
next/invalid evidence; its first completion packet is the exact jump cutoff.
History navigation also reveals its source table/invalid evidence. Legacy SDT
`history` remains available for API compatibility. See the [workbench contract](UI_AGENT_DEBUG.md#record-inspector-and-history-contract).

Local Windows validation: strict engine regression 204 passed; final Qt 43 UI + 6
resource + 10 evidence tests and retained smoke passed, including the added
101-table paging/snapshot-clamping check. Final native diagnostic checks cover
both evidence scopes and all six views for every sample family, exact history
jumps, record/section counts, searches, CRC visibility and immutable input.
Actual Windows Qt and WebView2 mouse input selected and expanded PMT, inspected
Decoded text, and followed its history to packet 1. Saved readback matched the
selected source ID, cutoff, group/section counts and history entry exactly.
The final Qt history scope control was also operated to expose all 19 sample
transitions. The inspection caught and fixed its collapsed control width.
Shared-tree array labels, compact layout and second-page section selection
have dedicated regression coverage. Final native input also verified the Qt
evidence-scope buttons and WebView2 group selection, Space/Enter folding.
Both use a source-section selector and direct Section/Merged scope buttons;
source selection preserves the historical comparison cutoff.

Hosted PR validation caught Linux font-dependent wrapping in the inspector tabs,
loss of matched branch descendants and the descriptor_tag search label, and a
source-selector disclosure race before the browser toggle event. The follow-up
reduces tab padding, keeps matched subtrees on both frontends, restores the label,
and reads live disclosure state before replacement. The original 90px compact
inspector threshold and browser assertions remain unchanged; final results are
bound to the PR head below through hosted checks.

Evidence remains ignored under `artifacts/workbench-*`. Original captures and
isolated settings are preserved. One retained smoke launch without the documented
offscreen/software environment exited during the scripted native save-dialog
flow; the configured smoke passed. One compact test invocation lacked the font
path and produced unreadable text; its valid-environment regression passed.
These do not establish native file-dialog acceptance for this change. Browser
Chromium follows the established hosted CI route, complementing actual Windows
WebView2. Publication/merge acceptance is recorded on the delivery PR.

Explorer parity, 2026-10-18, based on main `25a62e9` (including satellite
Metadata): both frontends now use one All tables + PID/type navigation list,
with engine logical-group counts and the same selection/focus contract.
Web's duplicated family list moves to a Tables toolbar Type selector, also
available in Qt. Known empty types, detected extension names, private evidence,
bad-CRC visibility, historical snapshots and existing record views remain.
See [the navigation and diagnostic contract](UI_AGENT_DEBUG.md#explorer-navigation-contract).

Local Windows Qt regression: 41 UI + 6 resource + 10 evidence tests, plus retained
smoke, passed; contrast 6 and both real-frontend diagnostic tests passed.
Actual native Qt and WebView2 interaction used the same shared-PID wire fixture:
SDT/BAT selection, focus-only arrow navigation, Enter activation and cross-PID
PMT selection passed. Readback matched every explorer PID/name/count/selection
and the active PMT scope. It also found and fixed Web's zero-result empty-state
removal. Final browser/cross-platform acceptance and publication are recorded
with the delivery PR; these local checks do not replace hosted CI.
Ignored evidence: `artifacts/explorer-qt-full`, `artifacts/explorer-agent`,
`artifacts/explorer-native`; originals and isolated test settings are retained.

Satellite candidate association, 2026-10-18: developed on
`codex/satellite-association` from `87ef81057fc164836f946116cf1523df65035546`
(merged PR #15). Shared C++ lookup and Qt/Tauri Metadata retain wire parameters,
transport/section provenance and catalog sources. The 22-record reference
snapshot matches nominal GEO slots only; all results remain candidates and
transponder/capture-time identity remains unverified.
See [scope and reproducible checks](SATELLITE_ASSOCIATION.md).
Local checks: strict engine regression 203 tests (202 passed, one optional
untracked recording absent), Qt regression 56 passed plus retained smoke,
Rust 6 passed, and real Windows Tauri/WebView2 satellite controls passed.
The final ISDB guard and 22-record catalog passed the full engine gate and
native Tauri run; Qt's complete gate preceded that core-only guard, with
the final targeted Qt check retained separately. Hosted delivery remains pending.
Validation uses an exact source mirror under the ignored
`artifacts/satellite-association-validation`; the owner's existing
checkout and running applications are retained.
Evidence: `artifacts/satellite-association-validation/artifacts/windows-engine-final`,
`artifacts/windows-qt`, and `artifacts/native-satellite-final` inside that mirror.
Native Tauri test teardown required terminating its owned process after the
close deadline; no graceful-shutdown claim is made and no owned backend/WebView
process remained. Browser preview's complete suite is delegated to hosted Linux
CI because of the already documented local Chromium startup limitation.

Local integration verified, 2026-10-18: `main` rebased onto remote
`5342976025957aff561da2b324a6440a5039a107` (PR #13), plus the retained
uncommitted UI refresh/agent diagnostics and conflict resolutions. Remote main
was rechecked before launch and still matched. Both frontends now render the
same fixed table colors/glyphs in the left PID explorer, with shared semantic
structure-tree colors in dark and light themes.

Windows local validation: Qt UI38, section evidence12, service metadata15,
contrast5 and live UI-agent2 passed. The final Tauri binary was rechecked after
its last asset rebuild. UI-agent tests validate rendered colors and glyphs in
both themes, bounded navigation, screenshots/state and unchanged source bytes.
Qt's automated UI matrix uses offscreen rendering; Tauri uses real WebView2.
Both final applications were then launched as visible native Windows windows;
actual captures and diagnostic readback confirmed completed analysis and no
backend/frontend error. This does not assert native Save-dialog or full manual
acceptance. The full browser Playwright matrix and hosted CI were not rerun.

Evidence: `artifacts/rebase-qt-tests.log`, `artifacts/rebase-section-tests.log`,
`artifacts/rebase-service-tests.log`, `artifacts/rebase-agent-tests`,
`artifacts/rebase-agent-final`, and `artifacts/rebased-manual-ui-0baeb1c4`.
The launch manifest records binary hashes and owned PIDs; the visible apps are
left running for the user's trial. Original local files and diff remain in
`artifacts/pre-rebase-20261018-121311` and retained stash `1325c76916aa40d5a1998e42afb75e11b1467fdf`.
The newer publication checkpoint below supersedes this local-only status.
See [UI diagnostics](UI_AGENT_DEBUG.md).

## Native interaction and publication check — 2026-10-18

The user requested direct interaction checks followed by commit/push. On the
same `5342976` base plus this patch, actual Windows mouse/keyboard input exercised
Qt SDT/PID filtering, logical section expansion, light theme, XML, ancestor-aware
field search, timeline historical/latest selection, EPG/Issues, Open-file cancel,
and the Save diagnostics button. Native WebView2 exercised PID filtering,
logical expansion, light theme, timeline click and End/Home keys.

This found two Web defects: count badges retained a dark background in light
mode, and a fired keyboard debounce timer kept diagnostic `settled` false.
The badges now use the theme surface; snapshot scheduling clears the timer
handle on execution/cancellation. The rebuilt WebView2 app was operated again:
End reached packet 177999, diagnostics reported settled with no backend/frontend
error, and clicking Save diagnostics produced a complete real PNG/state bundle.
Both production-frontend agent tests passed again; contrast coverage is now 6.
Browser regression assertions require settled state after End/Home.

Raw captures, state and runtime logs remain local in
`artifacts/interaction-check-2eaa37f4` and `artifacts/interaction-final-agent`.
Test profiles/settings are isolated. The new branch is
`codex/ui-parity-agent-diagnostics`, published as PR #15. The first hosted run
`39098070623` passed 31 of 32 browser cases; the new density test incorrectly
expected the old word `packets` instead of the retained evidence label
`Zero-based packet positions · no measured time available`. Its assertion now
checks the full label and five axis ticks. Hosted acceptance requires the rerun.
No source-stream edits or export were performed during this interaction check.

The branch subsequently integrated `5ed626f` (PR #14 signal metadata).
The shared source bar retains charset selection, adjacent PID validation,
scan progress and diagnostics. Combined-source validation is pending below.

## Signal metadata iteration — 2026-10-18

Implemented on `codex/signal-metadata`, based on main
`5342976025957aff561da2b324a6440a5039a107` (including PR #13):

- Typed ID registry lookup and source-linked section identifiers, with explicit
  unknown/context-required states and no claim of verified current ownership.
- Bounded original-byte text diagnostics and per-scan default input charset.
- Multilingual EIT short descriptions and extended fragment/item assembly,
  preserving missing/conflicting/duplicate evidence and event/version boundaries.
- Shared Metadata views, language selection and ID queries in Qt and Tauri.

Local Windows evidence uses official TSDuck 3.45-4798, Qt 6.7.3 and MSVC 2022.
The strict engine regression discovered 189 tests: 188 passed and the optional
untracked real recording was absent. After the final private display-name guard,
all 14 metadata tests passed (one more than that full run). Qt's strict regression
passed 54 tests plus its retained smoke; the final metadata control test passed
again. Locked Rust tests passed 6 and the native Tauri executable rebuilt.

The actual Windows Tauri/WebView2 runtime (Edge 155.0.4283.62) was exercised through
its local debugging interface with the real engine: English extended-text
assembly, Chinese selection/incomplete state, charset diagnostics, ID lookup,
source evidence and unchanged input bytes passed. This is feature interaction
evidence, not native file-dialog or clean-machine acceptance. The validation
launcher forcibly cleaned up its owned native app after the close wait; it is
not graceful-shutdown evidence. Qt evidence is offscreen with system fonts.

Local Chromium's pipe-based test launcher failed before usable pages; browser
suite results must come from hosted Linux CI rather than being claimed locally.
Source files were copied into an ignored writable validation directory because
the managed worktree's child-process write permissions prevented local compiler
outputs; implementation/test inputs were hash-compared. Ignored evidence lives
under `artifacts/signal-metadata-validation/` in the original checkout: build logs,
`engine-final2`, `qt-final`, `qt-metadata-final`, metadata test log and native
WebView2 screenshots/results. Publication/CI state is reported with the PR; these
local counts do not establish hosted delivery or a portable release.

## Previously verified delivered baseline — 2026-10-17 UTC

Merged `main`: [`20ddf5f8ca58f7af0903f53ff31954dfe72b3f87`](https://github.com/znbsf/ShowPsiSi/commit/20ddf5f8ca58f7af0903f53ff31954dfe72b3f87), PR #12.
All five jobs passed on this exact merged revision in
[run 39035573853](https://github.com/znbsf/ShowPsiSi/actions/runs/39035573853).
The [Windows Qt portable artifact](https://github.com/znbsf/ShowPsiSi/actions/runs/39035573853/artifacts/12101824078)
was downloaded and verified against the source/runtime manifest: 683 files,
669 reviewed dependency entries; ZIP SHA-256
`4af65625a50015df173822742d458989215be93a0588b0157a42511782250958`.
CI artifacts expire; this is not a formal release or installer.

- PR #9 delivered the portable package and fail-closed runtime/licensing gates.
- PR #10 refined editor-style layout, keyboard navigation and contrast.
- PR #11 fixed asynchronous acceptance races using explicit acknowledgements.
- PR #12 added section identity/CRC/arrival evidence, generation-aware merged and
  per-section inspection, explicit invalid/missing states, fixed table colors,
  functioning Qt tree expansion and structured XML coloring.
- The PR #12 local core matrix passed 102 tests, including the real UHF22 capture;
  Qt35, Web28 and contrast3 passed. Hosted Windows/Linux Qt35 and Web28 passed;
  hosted CI allows one missing optional real-recording test, unlike the local run.
- Windows portable contents and retained offscreen captures were inspected.
  Full native Windows desktop interaction remains unverified.

## Remote UI refinement — merged; hosted acceptance not refreshed locally

User feedback on 2026-10-17 requests bundled app identity, light/dark themes,
consistent chrome, numeric PID ordering, aligned list columns, LCN/service type
and PMT audio/video PIDs, logical table cards, discreet CRC filtering and labeled
arrival axes. These changes are now in remote `main` at `5342976` (PR #13).
The historical hosted evidence below still applies only to its named revision.
Time labels must retain their evidence basis; packet positions are not wall-clock
timestamps. Conflicting or unsupported channel-number mappings must remain explicit.

## Historical SDK migration snapshot

The following records describe the earlier PR #7 baseline
`e5793c77ebb23efec5ad661a598c507ca3490403`. Their test totals and acceptance scope
are historical, not the current iteration's results.

- PR #1 merged as `ac039f6`: modern workbenches and initial integrity loop.
- PR #2 merged as `beb2e57`: Windows MSVC engine/Qt validation.
- PR #3 merged as `f63bc60`: snapshot comparison, layout persistence and protocol
  generation integrity. All four jobs passed at feature head `98482d1` in
  [run 38976239202](https://github.com/znbsf/ShowPsiSi/actions/runs/38976239202).
- PR #4 merged as `dcadd66`: Windows Tauri release executable compiled and six
  Rust unit tests passed. All five jobs passed in run 38976742240. This is compile
  evidence, not Windows WebView2 interaction or an installer.
- PR #5 merged as `7df3706`: cooperative scan cancellation, MCP routing and
  stale-progress isolation. All five jobs passed at head `935ee17` in
  [run 38980765498](https://github.com/znbsf/ShowPsiSi/actions/runs/38980765498).
  The exact merged main also passed all five jobs in
  [run 38981738934](https://github.com/znbsf/ShowPsiSi/actions/runs/38981738934).
  Windows engine/Qt regressions and Tauri release compilation passed; this does
  not establish Windows WebView2 interaction.
- PR #6 merged as `3e51f4c`: native Qt Save destination and TS/BIN choice.
  All five CI jobs passed at `37e92c0` in run 38982972251; Windows Qt15 passed.
- PR #7 merged as `e5793c7`: TSDuck/TSCore 3.45-4798 migration, expanded protocol
  inspection and contextual workbench UI, plus the Qt test-result publication fix.
  All five jobs passed at final feature head `70ed914d49bbe485befdfdead03ffced682f5bb2`
  in [run 38991403217](https://github.com/znbsf/ShowPsiSi/actions/runs/38991403217).
  The exact merged `main` above also passed all five jobs in
  [run 38991857522](https://github.com/znbsf/ShowPsiSi/actions/runs/38991857522).
- No release or installer published. SDK 3.45 hosted Linux/Windows build and
  regression checks passed within the limits below; this is not all-platform
  native GUI acceptance.

## Current result

Qt Quick and Tauri/Web share one native C++/TSDuck engine and JSONL API. Both have
an editor-style dark workbench, semantic PSI/SI trees, evidence views, keyboard
navigation and search. The parser exposes its linked native table/descriptor
registry, explicit standards/regional context, section-PID discovery and optional
extra PIDs. An offline metadata index provides verified standard-level links.

Interactive development used the assistant's **own Linux cloud computer**;
Windows validation uses GitHub-hosted runners. No owner Windows PC, television
or phone was accessed. The actual native Linux Qt and
Tauri/WebKitGTK applications have been built and exercised, including native
edit/export. Browser validation is separately labeled and never substituted for
a native-runtime claim.

## Verified current behavior

- Cooperative targeted scan cancellation with explicit lifecycle states, cleared
  incomplete evidence and safe rescan. Qt/Web reject stale/foreign progress;
  backend death disables stale actions. MCP input stays responsive and passive
  EOF drains accepted calls. See [cancellation contract](ANALYSIS_CANCELLATION.md).

- Read-only A/B snapshot comparison with deterministic pagination, explicit cutoffs,
  per-side evidence and stable identities. Native Qt and browser workflows preserve
  the main selected snapshot until an explicit navigation action.
- Qt and Web pane sizes persist with bounded restoration and Reset layout.
- Reused-version generations and same-packet reception order preserve evidence
  boundaries. Extra-PID SDT stays inspectable without replacing canonical services.

- 30 engine tests: source preservation, analysis failure reset, exact PAT→PMT
  binding, snapshot inspection cutoff, regional text, extension validation,
  export exclusivity/cleanup, framing and regular-file input guards.
- 43 protocol/reference tests: ATSC and ISDB fixtures; DVB-S/S2/T/T2/C delivery
  parameters; private PDS isolation, nondefault PID discovery and unknown bytes.
  New fixtures cover all 15 newly registered table types, DTMB DRM, explicitly
  signalled text, registration inheritance and safe namespace fallback. All 21
  fixture XML inputs reproduce byte-for-byte with the pinned compiler.
- 6 SDK migration tests: runtime/header identity, UTF-8 filesystem paths,
  root arguments, manifests and no invented DTMB charset/timezone.
- 14 deterministic native cancellation tests and 17 MCP/transport tests: queued,
  progress and completion boundaries, EOF drain, typed IDs, progress tokens,
  response routing and safe close. Test gates are excluded from production.
- 6 HTTP bridge tests and 25 live Chromium/native-engine tests, including backend
  termination, keyboard/tree interaction, historical snapshots and responsive layout.
- 16 compiled native Qt tests: real workflows, search, literal untrusted text and
  tooltips, no remote image fetches, failure-state cleanup, external TS/BIN save
  destinations, cancelled save, stale preview rejection and no-overwrite errors.
  Linux tests also enforce a read-only application resource directory; the
  Windows case uses a separate resource directory without claiming ACL coverage.
  Actual DTMB/DSM-CC fixtures also verify standard selection, empty projections,
  guarded warning/XML display, raw-byte preservation and indexed list labels.
- 7 Rust native-shell tests passed on the merged pre-upgrade baseline: exact URL allowlist plus launcher success/failure,
  spawn errors, bounded diagnostics and unconfirmed timeout. Native GTK source selection, save/export,
  independent readback, overwrite-warning cancellation and backend-death flows
  were also checked in the actual application.
- Both workbenches carry the selected packet cutoff into inspection. A historical
  view cannot silently assemble a later sibling section.

The SDK upgrade has **165 current local tests passed**: engine30,
protocol43, SDK6, cancellation14, MCP17, HTTP6, Qt16, Qt-result publication8 and Chromium25. The integrated
Qt16 run includes both PR #6 export scenarios and the new protocol fixture checks.
The initial SDK head `6fcb135` passed all five jobs in run 38990955608,
including Windows SDK/Qt and both Rust jobs. A confirmed result-publication race
from PR #6's post-merge Windows run was then corrected in the test harness.
The corrected strict Qt gate passed locally and in both final feature-head and
post-merge runs linked above. The post-merge Linux and Windows Qt jobs each
passed **24 tests: 16 compiled native Qt integration tests plus 8 result-publication
harness regressions**, with no skips, failures or errors. These are offscreen
checks; they do not validate the Windows native Save dialog. All five hosted jobs
passed: Linux engine/web, Linux Qt, Linux Tauri build/tests, Windows MSVC
engine/Qt, and Windows Tauri release compilation/Rust tests. The 165-test total
above is the recorded local suite total, not a per-platform CI total.
See [cloud validation](VALIDATION_CLOUD.md),
[publication-race history and final acceptance](CLOUD_DEVELOPMENT.md#qt-test-result-publication-race-2026-10-17),
[native Tauri evidence](NATIVE_TAURI_VALIDATION.md) and [test commands](../tests/README.md).
Earlier pending-CI statements in validation records describe intermediate heads;
this dated snapshot records the final feature head and exact merged revision.
Native Linux Tauri comparison and persisted layout have been exercised on the
new assets. Its actual unsupported desktop-browser helper now reports failure;
Copy URL succeeds and clears the error. Browser navigation itself is not verified.
The CI-only Windows PR #2 is merged as `beb2e57`. All four jobs passed in
run 38974640106, including Windows baseline engine/protocol/HTTP/Qt regressions.
The retained Windows Qt screenshot was inspected after fixing offscreen font
discovery. The expanded PR #3 suite also passed all four jobs: Windows engine29 + one
explicitly allowed absent-recording test, protocol26, HTTP5 and Qt8. Its retained
Windows Qt smoke screenshot was downloaded and visually inspected.

The linked SDK is **TSDuck/TSCore 3.45-4798**, using C++20. The Linux runtime
registers **58 table XML names / 347 descriptor XML names**, including aliases.
The offline standards index associates 227 descriptor names and 49 table names,
without bundling PDFs. These counts are not conformance percentages. See
[protocol coverage](PROTOCOL_COVERAGE.md) for measured, SDK-only and unknown cases.

Explicit DVB uses the SDK strict-DVB flag. Ambiguous DSM-CC module or private-dual
descriptor contexts retain generic bytes and show a warning instead of silently
asserting another namespace. Guarded XML is labelled; wire bytes are authoritative.
The split TSCore/TSDuck libraries, headers and runtime data must match; both
version-specific ABI symbols are enforced.

## UI/UX refresh before rebase, 2026-10-18 (historical local record)

A presentation-only refresh of both workbenches was implemented and exercised on
the assistant's Windows workspace: the compiled Qt application through its
offscreen self-check and test subset, and the real web workbench behind the
loopback bridge with a real Chromium and the real engine. It changes no engine
code, no JSONL schema and none of the boundaries recorded above.
[The refresh record](UI_UX_REFRESH.md) lists each change, the measured results and
what remains unimplemented (field-to-byte highlighting, identifier
cross-navigation, EPG time grid, i18n, drag-and-drop).

These results apply to the former `6e9df85` checkout plus its dirty patch.
The rebase integration at the top of this document supersedes its old family
ordering and flat Qt record-column assumptions with PR #13's numeric PID
explorer, logical table cards and service metadata. Its screenshots are historical.

## Remaining boundaries

- Windows WebView2 interaction, Windows/macOS native Save-dialog interaction,
  macOS builds, installers and actual external-browser launching have not been
  validated in this iteration. Original Windows evidence
  below does not validate later changes.
- No RF demodulation, tuner control, complete DTMB-specific signaling guarantee or
  ATSC 3.0 IP/ROUTE/MMT support.
- No exhaustive standards conformance, arbitrary descriptor/table edit/remux,
  live UDP/SRT input, persistent large-file index or production EPG time grid.
- Exact field-to-byte selection highlighting remains future work. Unknown private syntax is retained, never invented.
- Export output+manifest use exclusive creation and failure cleanup, but are not
  a crash-atomic transaction spanning two files.

## Original Windows prototype evidence

The initial `a79ce16` prototype compared Qt Quick 6.7.3 and Tauri/WebView2 using
TSDuck 3.39-3956. It exercised a generated DVB stream and official French UHF22/UHF33
recordings, MCP edit/export/readback and three alternating benchmark trials.
See [BENCHMARK.md](BENCHMARK.md) for those exact binary identities and limits.
Those historical resource measurements must not be presented as measurements of
the new workbench. Historical SDK locations and experiment retry budgets do not
constrain this cloud iteration.

SDKs, binaries, downloaded streams, local profiles and transient evidence remain
ignored. Source screenshots and reproducible tests are committed. Read
[CLOUD_DEVELOPMENT.md](CLOUD_DEVELOPMENT.md) before repeating environment diagnosis.


## 2026-10-26 — Qt / Tauri core SI synchronization

The two frontends now consume one inspector model and original bitmap assets.
Tauri gains the matching classic SI tree/field/dual-hex view, stable selection,
explicit single-click +/- versus double-click labels, resizable columns with
vertical grid lines, network/TP/program/LCN organization and Summary/PID return.
The prior advanced workspace remains accessible. No protocol parser changed.

Local evidence: shared catalog 904 assertions, Qt 38 component and 22 full-app
checks, real-engine browser 20 core plus 14 extended interaction checks, and the
uncached double-click regression. Current Qt and Tauri native previews both
complete the same Hotbird scan. Native WebView2 capture is verified; Tauri native
mouse automation remains unverified because application authorization timed out.
See [parity evidence and exact binaries](NXTSA_UI_UX_PARITY.md#dual-frontend-local-acceptance-2026-10-26).
Publication continues on the authorized draft PR #30; hosted results must be
read against the new commit, not the earlier branch head.


### 2026-10-27 classic parity step 16

Both UIs now expose source-identified Save/Copy for the active view, bounded
original/derived exports with SHA-256 manifests, and validated OK/Cancel scan
preferences. Existing advanced rename/SI snapshot export remains available.
Six engine export checks, three browser chains and seven full-Qt offscreen
checks passed. Native dialog/mouse/DPI/normal exit remain step 17; no CI used.
