# Cable out-of-band SI input design

The implemented subset covers edition-labelled section inspection and bounded
revision/subtable queries. See [the API contract](CABLE_OOB_API.md) and
[current coverage](PROTOCOL_COVERAGE.md#current-protocol-extension-support).

## Evidence and edition boundary

The SCTE catalogue identifies SCTE 65 2016 (R2021), but direct full text was not
retrieved. The ANSI preview supplies a contents outline, not a bitfield basis.
The separately published [ITU-T J.94 (10/2016)](https://www.itu.int/rec/T-REC-J.94-201610-I/en)
provides a public normative System B SI definition in Annex B. Its official
[full PDF](https://www.itu.int/rec/dologin_pub.asp?id=T-REC-J.94-201610-I%21%21PDF-E&lang=e&type=items)
is pinned by source size 4,233,533 bytes and SHA-256
`5a89278f2801748a86a98c95d1e539255eaa43ddc903dfd8d66230ab26089be2`.
The source PDF is not bundled with this repository.

This provides a reliable edition-specific implementation route. It does not
prove equivalence to every revision of SCTE 65. Label initial coverage as
**J.94 (2016) System B / cable OOB SI**, with later SCTE crosswalk evidence.

Annex B distinguishes NIT (CDS/MMS), NTT, short-form VCT (VCM/DCM/ICM), and STT.
Its POD/Host section interface associates these with SI_base PID 0x1FFC and
requires CRC even for the short-style section syntax. This differs from the
SDK's ATSC satellite SVCT model and from Japanese table meanings at colliding
IDs. A protocol context and input framing are essential.

## Input and implementation boundaries

1. The explicit `j94-system-b` context admits TS-encapsulated SI sections at
   SI_base PID 0x1FFC, preserving the short-style envelope and required CRC.
   Unknown/colliding contexts do not borrow an ATSC or ISDB decoder.
2. Captured sections retain their original framing and provenance. No physical
   OOB/QPSK demodulation, POD interaction, CableCARD or RF reception is implemented.
3. NIT CDS/MMS and short-VCT VCM/DCM/ICM remain independent of DVB NIT and ATSC
   Satellite VCT. Their subtype identities and nonstandard version rules remain explicit.
4. NTT names and STT times use the named edition's character/time definitions.
   Reserved, unsupported and malformed values retain diagnostics and raw bytes.
5. Descriptor-revised queries can assemble bounded subtable evidence. Cross-table
   carrier/modulation/channel/name joins, synchronized lineups and receiver
   activation remain unsupported; no future or incompatible generation fills a gap.
6. The inspector exposes original sources and absent long-header fields. A
   source-linked cable topology or general raw-BIN input adapter is not implied.

## Required negative and cross-family tests

- The same table IDs in ISDB/ATSC/cable contexts must not share semantic labels.
- Short-envelope CRC failure, wrong length, truncated subtypes and reserved
  protocol versions; all original bytes retained.
- Multiple NIT record ranges, overlaps, missing ranges and invalid indexes;
  frequency/modulation units and numeric overflow boundaries.
- VCM/DCM/ICM distinctions, duplicate/conflicting virtual channels, missing source
  names, unknown carrier/modulation references and out-of-order arrivals.
- Capture cutoffs, incomplete maps, reset/reanalysis and cancellation must not
  borrow later evidence or stale previous-session state.
- Explicit resource limits and deterministic pagination before large real input.
- Published synthetic-vector provenance plus a separately obtained real capture
  before claiming deployment interoperability.

Do not add these tables to the existing ATSC satellite SVCT registry mapping.
Keep unsupported operations explicit. Extend claims only with real-engine tests,
Qt/Web evidence, combined regression and independent review.
