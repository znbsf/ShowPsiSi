# Signal topology release candidate

This is a development acceptance checklist, not a published release. Publish only
following the first Windows release, with a newly versioned build of the exact
merged source. The initial release download names and version remain unchanged.

## User-visible additions

- A Topology workspace beside Services, Tables and EPG. DVB networks, transports,
  services and PMT components expose their relationships and original SI sources.
- ATSC TVCT/CVCT and explicitly selected ISDB profiles retain their own identifiers
  and interpretation rules. Auto mode does not invent a regional receiver policy.
- Delivery parameters remain distinct from transport-stream identity. Satellite
  catalogue matches are candidates, not verified spacecraft assignments.
- Selecting a relationship or source opens the existing section, tree, XML or
  bytes views at the retained revision. Back restores the topology context.
- Keyboard navigation, bounded loading, loaded-object search, dark/light theme
  and historical snapshot comparison use the existing workbench conventions.

## Evidence already available

PR #22: https://github.com/znbsf/ShowPsiSi/pull/22
Latest reviewed feature head at this checkpoint: 7bce3c29508bc6c0f7f2d620a01692f8017dc0a8.
All five hosted CI jobs passed for that feature revision. Native Qt test surfaces
and sandboxed Chromium tests passed within their recorded scope. The public
French recording produced 88 nodes, 87 relationships, 12 services and seven
terrestrial declarations; unknown wire frequencies remained unknown.

A cloud screenshot review on 2026-10-19 checked the actual dark topology satellite
candidate view: aligned identifiers, distinguishable selection, source cards,
separate unresolved status and the unchanged workbench/timeline layout. That
synthetic screenshot is UI evidence only, not reception or satellite validation.

## Promotion checklist

- [x] First Windows version published and exact public assets read back.
- [x] Merge current main including release transport recovery; retain short-table
      source semantics. Resolve conflicts without dropping tests or evidence.
- [x] Bump all application/package version authorities together and add actual
      version-specific notes. Keep protocol-extension work out of this release.
- [x] Fresh engine/helper/Qt build, strict engine and native Qt tests, sandboxed
      browser regression, Tauri/packaging/updater/publisher tests on merged source.
- [ ] Hosted five-job CI passes for the exact final main commit.
- [ ] Audit that run's installer and portable ZIP, inventories, hashes and actual
      installer lifecycle reports. Do not reuse earlier feature/main artifacts.
- [ ] Publish via the verified request workflow and check public downloads plus
      the update client's version/asset selection contract.

The first-release clean-machine/UAC/real future-version update limits still
apply unless separately verified. Synthetic fixtures, offscreen tests and a
successful build do not establish full broadcast-standard conformance.

## Main integration checkpoint, 2026-10-19 10:00 UTC

Merged main `3ec91ded` into this worktree. A fresh Qt/core build passed 146
publisher, Qt resource-path, Qt UI and Qt topology tests. Initial local launcher
attempts lacked extracted runtime paths/test-helper environment; their failed
logs are retained separately, and the complete-environment rerun passed.

Independent protocol work exposed a pre-existing initial-edge evidence cap and
deduplication bypass. Backported the two-line construction fix plus two ISDB
regressions as `deb5cef`, without NorDig/protocol feature changes. All 35 topology
tests pass on the freshly rebuilt production core. The combined final release
gate remains pending after versioning; the earlier 146-test pass predates this
small backport and is not labelled as its final-source full regression.

First release v0.1.0 published and public assets verified on 2026-10-19.
The next candidate is v0.2.0; all four version authorities were updated together.
Fresh exact-source gates and Windows artifact acceptance remain required.

## Combined safety recovery, 2026-10-19 10:50 UTC

The first v0.2 candidate (`e24ff587`, CI run `39236912182`, #75) passed all
five hosted jobs. It was held before merge after adversarial tests reproduced
baseline defects: short PAT/PMT envelopes could crash discovery or suggest
forged PIDs; short SDT and sibling long-table envelopes could fabricate semantic
records; private descriptor context survived PDI/malformed PDS barriers.

Applied only the reviewed generic fixes (`08b683a`, `a63a456d`, `a0432485`) to
this candidate. No NorDig aggregation, J.94, DVB-I or DSM-CC feature code was
imported. Invalid table bytes remain inspectable, genuine short TDT/TOT/RST
formats remain accepted, and contextual descriptors are distinguished from
unvalidated SDK merged display meanings.

Fresh combined code snapshot `9f80da4a916a20cb9953a8a54a7d19b97e9562eb` passed:

- 265 strict engine/helper tests, zero skips.
- 89 Qt tests, zero skips, plus retained native offscreen smoke.
- 46 sandbox-enabled Chromium/native-core tests, exit 0.
- 77 publisher, 29 installer helper and 6 contrast regressions.
- 45 compiled updater checks; 9 locked Rust tests and optimized Tauri build.

These are cloud Linux gates. The following documentation-only checkpoint does
not change the tested code. Fresh exact-head hosted CI, post-merge main CI and
Windows artifact acceptance remain required before v0.2 publication. Earlier
#75 success is retained as pre-fix evidence, not substituted for those gates.
