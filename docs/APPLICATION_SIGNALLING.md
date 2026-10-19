# Application and update signalling inspection

Checkpoint: 2026-10-19. This is inspector coverage, not a HbbTV browser or a
receiver/firmware-update implementation.

## First increment and evidence

`tests/test_application_signalling.py` sends synthetic TS packets through the
real JSONL core. Seven test methods cover:

- Pinned XML/compiler input and exact binary section SHA-256 values.
- AIT organization/application IDs, transport labels, HTTP base/extension and
  initial path, with exact original bytes.
- PAT/PMT discovery of an AIT on a non-reserved PID without `extra_pids`.
- UNT OUI/version, SSU association tag, data-broadcast ID, polling fields and URI.
- CRC-correct but semantically truncated AIT/UNT: generic raw fallback.
- Incorrect CRC: retained bytes and invalid status.
- Every byte-boundary payload truncation with corrected outer length/CRC:
  original bytes survive and the same core process remains responsive.

The AIT and UNT parser paths already existed in the SDK. This increment adds
application evidence and fills missing AIT normative links, rather than claiming
new parsers or complete HbbTV/SSU implementation.

Fixtures live in `tests/fixtures/application-signalling/`. Reproduce with official
TSDuck **3.45-4798**: `tstabcomp NAME.xml -o NAME.bin`. The manifest hashes both
inputs and outputs. Fixture URLs use the reserved `example.invalid` domain.
No test needs to fetch an application or firmware.

## Inspection semantics learned during testing

`native_table_complete` describes section assembly. It does **not** certify the
semantic payload. A complete, CRC-correct section with malformed nested lengths
can correctly report `native_table_complete=true` and
`native_decode_status="generic raw fallback"`. Test the latter and the native
node name before claiming successful semantic decoding. Preserve the original
bytes in both cases. Do not change the assembly flag to disguise parse failures.

## Normative basis

- [ETSI TS 102 809 V1.3.1](https://www.etsi.org/deliver/etsi_ts/102800_102899/102809/01.03.01_60/ts_102809v010301p.pdf):
  AIT §5.3.4; application signalling/name/technical descriptors §5.3.5;
  transport descriptors §5.3.6; initial location §5.3.7. References in the app
  remain standard-level links. Some pinned SDK headers cite predecessor
  TS 101 812; the newer associations were checked directly against this PDF.
- [ETSI TS 102 006 V1.4.1](https://www.etsi.org/deliver/etsi_ts/102000_102099/102006/01.04.01_60/ts_102006v010401p.pdf):
  system software update signalling. Identifying a transport/URI never authorizes
  installing its payload.
- [HbbTV specification library](https://www.hbbtv.org/resource-library/):
  distinguishes published 2.0.4 / TS 102 796 V1.7.1 plus errata from 2.0.5 /
  candidate V1.8.1. These broader runtime specifications do not turn this
  signalling inspector into a conformant receiver.

## Source-card summary increment

The additive AIT summary contract is documented in
[APPLICATION_SUMMARY_API.md](APPLICATION_SUMMARY_API.md). It retains scoped
common/local transport alternatives, duplicate identities, unresolved references
and original-section anchors for existing Metadata/Topology presentation. The
adapters do not execute applications or fetch signalled URIs. The bounded UNT
source cards add compatibility/target/operational declarations and preserve
unknown eligibility, location ambiguity and full-OUI collisions. Cross-table
carousel resolution and DSM-CC assembly remain subsequent increments.

## Next loops

1. Build source-linked application summaries: common versus application-local
   transport labels, missing/ambiguous references, multiple applications,
   control-code transitions and versions. Do not silently pick one transport.
2. Add SSU notification/device-target/compatibility and transport relations.
   Keep unknown private selectors opaque and show why a target cannot resolve.
3. Extend DSM-CC tests from DII/DDB fields to bounded module assembly. Test
   reordered/duplicate/conflicting/missing blocks, version/download-ID reuse,
   cancellation, limits, and incomplete capture. Object-carousel reconstruction
   is a separate stage after module evidence is reliable.
4. Add safe object export only after traversal, symlink, size, decompression and
   filename tests. Extracted data must never execute or install automatically.
5. Add Qt/Web summaries using the shared source-navigation model; verify both
   themes, keyboard access, large datasets, cutoff/snapshot state and raw jumps.

All steps need regression evidence and explicit remaining boundaries before
being promoted from planned to verified. Synthetic tests do not replace a
captured-stream acceptance case.

## Real-capture read-only check

On 2026-10-19 the first protocol increment was also checked against the existing
public [TSDuck France UHF22 recording](https://tsduck.io/streams/?stream=france-dttv).
The default DVB scan retained 1,855 records. Inspection of the 1,482 AIT, UNT and
DSM-CC table-ID records yielded these merged native-tree counts: AIT 1, UNT 4,
DSM-CC user-to-network message 42, download-data message 17, generic raw fallback
6, and no merged native tree 1,412. These count retained variants, not unique
applications, downloads or complete modules.

A representative missing merged tree is a valid-CRC 4,094-byte DDB section with
section number 226; its status is `incomplete table; raw section retained`.
This matters for the next carousel increment: incomplete table/module assembly
must not be confused with missing captured bytes or a fully undecodable block.
Per-section evidence remains authoritative.

The complete scan/inspection took 17.28 seconds on the cloud host. Source SHA-256
before and after was identical:
`24143de80d28461d084dfb75279da520f335de36b7c35f6398ed6d510daa5937`.
The ignored `artifacts/application-signalling/real-capture.json` retains the
binary identity, source provenance, representative native trees and boundaries.
No application, URL or firmware was fetched/executed. This check does not prove
complete carousel assembly, receiver behaviour or all HbbTV/SSU variants.

## Bounded AIT/UNT summary validation checkpoint

On 2026-10-19 the source-hash-verified combined engine gate passed 361 tests
with no skips, including 23 real-core AIT/UNT summary cases. The focused summary,
application-signalling and icon suites also passed all 35 checks. Tests cover
full-OUI hash collisions, malformed and private selectors, section-scoped common
UNT descriptors, operational location precedence, location conflicts, exact
source anchors and captured-generation cutoffs. They do not establish device
eligibility or complete SSU receiver conformance.

The same unmodified public France UHF22 recording produced one AIT summary with
six objects and six relations, and four UNT summaries with 27 objects and 28
relations in total. The UNT PIDs were 1027 and 1037 (OUI 6530), and 1074 and 1071
(OUI 279). Their retained compatibility groups and full-width transport
association tags remain source declarations: private selectors and unresolved
carousel associations keep the summaries explicitly incomplete. Input SHA-256
again matched the value above. Ignored evidence is retained in
`artifacts/application-signalling/real-ait-summary-report.json` and
`real-unt-summary-report.json`; the combined gate is under
`artifacts/dvbi-frozen-final/`. No application or firmware was fetched or run.
