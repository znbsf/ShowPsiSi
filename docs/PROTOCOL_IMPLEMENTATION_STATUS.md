# Protocol extension implementation checkpoint

2026-10-19 09:13 UTC. Cloud-only development on `feat/protocol-extensions`.
This is an active implementation checkpoint, not a release or conformance claim.
The initial Windows v0.1.0 release is separately gated on main; these changes do
not belong in that frozen candidate.

## Implemented first slices

- NorDig: default DVB namespace-driven parsing; v1 typed projection repaired;
  v2 country/list/name/LCN alternatives and exact sources retained, no activation
  toggle and no silent regional selection. Twenty focused real-core cases.
- SCTE: explicit SCTE EAS discovery repaired; additional SCTE-35 command forms,
  failure/CRC/encryption/raw preservation and signal-only roundtrip. Eighteen
  focused cases; current full SCTE-65 text was not retrieved.
- AIT/UNT base: seven focused checks, pinned compiler inputs and binary hashes,
  every payload-prefix truncation, and captured public French signalling evidence.
- AIT/UNT summaries: source-linked objects and relations, correct common-loop
  scopes, duplicate/ambiguous references and eligibility/execution boundaries.
  Twenty-three targeted summary cases; independently reviewed before promotion.
- J.94 (2016) System B: cable OOB section inspection, NIT CDS/MMS, short-VCT maps,
  NTT MTS and STT. Thirty focused cases after the text/time increment; mandatory
  CRC and active modulation reference failures fixed after independent review.
  Complete channel-map assembly and deployment SCTE65 equivalence remain open.
- DVB-I: local UTF-8 XML import/query/inspect with independent revision and raw
  source hash, explicit namespaces, retained alternatives/conflicts and hardened
  pinned static Expat 2.9.0. Forty-nine focused cases; no media/network fetching.
- Metadata presentation: bounded shared cards for NorDig and AIT/UNT, actual Qt
  dark/light paging and sandboxed Chromium source disclosure/paging checks.
  Exact clickable source routing awaits integration with the topology workbench.

These test counts overlap broader gates and must not be added as a unique total.
The recorded 361-test zero-skip aggregate predates final NTT/STT and combined UI
integration. Run a fresh combined build/gate before making a final-source claim.

## Next loop

1. Finish scoped commits and preserve independent reviews.
2. Merge the separately tested signal-topology feature into this branch.
3. Resolve shared inspect evidence anchors and revision guards, API discovery,
   explicit runner registrations, and publisher test fixtures for static Expat.
4. Add DVB-I input/session UI, cable short-header labels and protocol source jumps
   consistently in Qt and Web. Preserve standard/profile and input distinctions.
5. Add original-section DSM-CC cards, then separately bounded module assembly
   with explicit identity, epoch, incomplete/conflicting block semantics and caps.
6. Rebuild production/helper/Qt; run all engine, parser, security, UI, packaging
   and publisher contracts. Exercise actual browser/native surfaces where available.
7. Review exact dependency/source inventories, push reviewed changes, follow
   hosted CI and fix genuine failures. Publish later only after the first release
   pipeline is complete and the exact feature artifacts pass acceptance.

## Durable routes

- [Coverage and evidence](PROTOCOL_COVERAGE.md)
- [Test and iteration plan](PROTOCOL_TEST_PLAN.md)
- [Application signalling](APPLICATION_SIGNALLING.md) and
  [source-card contract](APPLICATION_SUMMARY_API.md)
- [DVB-I API](DVB_I_API.md) and [input design](DVB_I_INPUT_DESIGN.md)
- [Cable OOB framing/edition](CABLE_OOB_INPUT_DESIGN.md)
- [Protocol UI](PROTOCOL_UI.md)
- [Delivery recovery](DELIVERY_RUNBOOK.md)

Pending real-world samples or unsupported normative variants remain explicit.
A decoded section, a complete table, a complete module/map, a working UI and a
published package are separate acceptance conditions.

## Topology integration checkpoint, 2026-10-19 09:25 UTC

Merged the separately CI-tested topology feature into this development branch.
Resolved shared API discovery, inspector revision/anchor composition, test runners,
Qt/Web metadata rendering and static-dependency publisher-fixture conflicts.
Fresh combined production/helper/Qt build passed 414 engine tests, 88 Qt-related
tests plus smoke, and 59 publisher contracts, all with zero skips. These counts
refer to the first combined source before the final malformed-J.94 anchor guard.

Integration review found long-header locators being exposed on short sections.
The guard now respects section syntax and the explicit J.94 short-table family,
even when a malformed input sets the forbidden long-header bit. A fresh rebuild
then passed 31 J.94 and 33 topology targeted cases. Known independent findings
still pending are UNT declaration presence across a complete sub-table and
metadata pager focus / complete NorDig source context. UI/import/reassembly work
continues; this branch is not ready for release.
