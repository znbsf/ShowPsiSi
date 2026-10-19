# Cable out-of-band SI input design

Status: researched design; no new decoder or UI acceptance is claimed here.

## Evidence and edition boundary

The SCTE catalogue identifies SCTE 65 2016 (R2021), but direct full text was not
retrieved. The ANSI preview supplies a contents outline, not a bitfield basis.
The separately published [ITU-T J.94 (10/2016)](https://www.itu.int/rec/T-REC-J.94-201610-I/en)
provides a public normative System B SI definition in Annex B. Its official
[full PDF](https://www.itu.int/rec/dologin_pub.asp?id=T-REC-J.94-201610-I%21%21PDF-E&lang=e&type=items)
was retrieved on 2026-10-19: 4,233,533 bytes, SHA-256
`5a89278f2801748a86a98c95d1e539255eaa43ddc903dfd8d66230ab26089be2`.
The research copy remains ignored and is not bundled with this repository.

This provides a reliable edition-specific implementation route. It does not
prove equivalence to every revision of SCTE 65. Label initial coverage as
**J.94 (2016) System B / cable OOB SI**, with later SCTE crosswalk evidence.

Annex B distinguishes NIT (CDS/MMS), NTT, short-form VCT (VCM/DCM/ICM), and STT.
Its POD/Host section interface associates these with SI_base PID 0x1FFC and
requires CRC even for the short-style section syntax. This differs from the
SDK's ATSC satellite SVCT model and from Japanese table meanings at colliding
IDs. A protocol context and input framing are essential.

## Bounded implementation stages

1. Confirm the application's demux preserves this section envelope and CRC.
   Add explicit family/context dispatch before introducing an adapter. Unknown
   contexts must retain raw evidence, not borrow a different system's decoder.
2. Support local section data with explicit provenance and explicitly framed TS
   captures where available. Do not claim physical OOB/QPSK demodulation, POD
   interaction, CableCARD support or RF reception.
3. Implement NIT CDS/MMS and short-VCT maps independently from DVB NIT and ATSC
   satellite VCT. Keep per-subtype identity and nonstandard version semantics.
4. Add NTT names and STT times with their actual character/time definitions.
   Preserve reserved, unsupported and malformed records as diagnostics/raw data.
5. Join observed carrier/modulation/source/channel references only when all
   needed records exist. Separate partial maps from complete channel lists;
   do not fill missing pieces from future or incompatible generations.
6. Integrate source-linked cable topology with the same inspector navigation.
   Keep channel/source/physical-carrier concepts distinct.

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
Keep unsupported operations explicit until each stage has real-engine tests and
Qt/Web evidence, followed by combined regression and independent review.
