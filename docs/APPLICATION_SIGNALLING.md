# Application and update signalling inspection

This is bounded inspector coverage, not a HbbTV browser or a
receiver/firmware-update implementation.

## Inspection coverage

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
carousel resolution remains a subsequent increment. Exact-section DSM-CC cards
and bounded same-PID captured-module reconstruction are now documented in
[DSMCC_RECONSTRUCTION.md](DSMCC_RECONSTRUCTION.md). Their hashes cover only
complete captured byte sequences with exact source/epoch evidence, not a complete
application, software image, signature check or receiver runtime.

## Carriage, tests and limits

[Application carriage](APPLICATION_CARRIAGE.md) adds bounded, nonexclusive
PAT/PMT-to-AIT source relationships. `tests/test_application_summaries.py`,
`tests/test_application_carriage.py`, `tests/test_dsmcc_summaries.py` and
`tests/test_dsmcc_reconstruction.py` exercise original-byte anchors, conflicting
and missing identities, generation/cutoff isolation, malformed input and resource
bounds through the production core. See [test commands](../tests/README.md).

Signalled URLs and firmware locations remain inert. Device eligibility,
cross-PID carousel association, BIOP reconstruction, object export, decompression,
application execution and receiver conformance remain unsupported. Synthetic
fixtures and bounded public-capture checks do not certify complete HbbTV or SSU.
