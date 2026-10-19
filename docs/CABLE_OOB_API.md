# J.94 System B revision and subtable query contract

Development contract for ITU-T J.94 (10/2016), Annex B and Annex F. The existing
section inspector remains the exact raw-evidence interface. This increment adds
read-only `query_cable_oob`; it does not establish current SCTE65 equivalence.

## Revision evidence

Only table-level descriptor 0x93 in NIT, NTT or short-VCT is revision evidence
(B.7.6, Table B.43). Its first three payload bytes carry a five-bit version,
section number and last-section number. Future trailing bytes remain raw. Reserved
bits are ignored; section number above last-section number is invalid. The same
tag inside a record descriptor loop or STT is not promoted to table revision.

`inspect.fields.j94_system_b.revision_detection` reports absent, valid, duplicate,
conflicting or malformed evidence, retaining every candidate and byte offset.
Exactly one valid descriptor is required for assembly. Identical duplicate
revision descriptors also block assembly rather than silently choosing one.

The original short-header `version`, `section`, `last_section`, `extension` and
`current` fields remain null. Descriptor revisions never become fabricated MPEG
header fields. Annex F Profile 1 does not supply this revision mechanism; Profile 2
adds it for NIT/NTT/S-VCT. A descriptor observation does not certify a complete
operational profile.

## Query and time identity

Request: optional `analysis_revision`, inclusive completion `at_packet`, `offset`
and `limit`. Requires a successful complete analysis in explicit `j94-system-b`
context. The response echoes analysis revision and exact cutoff on every page;
stale revisions and out-of-range cutoffs are rejected. A nonzero-offset continuation
page must explicitly supply both revision and cutoff; page limits are 1–100.

Group identity is analysis-local PID + table ID + subtype, plus NTT language bytes
or short-VCT vct_id. There is no invented network ID. The newest structural,
CRC-valid observation at the cutoff determines whether revision selection is
possible. Missing or ambiguous revision evidence blocks that group's assembly;
it does not fall back to an older complete generation.

For a valid latest descriptor generation, only same-version/same-last-number
sections observed after the latest incompatible-generation/revision barrier are
eligible. Receive ordinals distinguish multiple sections completed in one TS
packet. Reused five-bit versions cannot resurrect sibling sections from a prior
cycle. Different raw bytes for the same section slot within one generation remain
a conflict; repetitions of identical bytes are not conflicts. CRC-invalid and
structurally unsupported observations remain inspectable and are reported as
excluded evidence without entering generation selection.

## Response and bounded completeness

The response has `groups`, `total_groups`, `offset`, `limit` and `next_offset`.
Each group includes stable identity, descriptor-only revision, explicit status,
`sections_complete`, `subtable_complete`, required/observed/missing section
numbers, source observations and record-level source/byte offsets. Unversioned or
revision-ambiguous groups return observations without assembled records.

Revision coverage means all section numbers 0 through the declared last number
are present. Subtable completeness additionally requires unambiguous slots and
non-overlapping record keys/ranges. NIT carrier/modulation indexes, DCM channel
ranges and ICM map indexes retain observed gaps; a gap between observations is
not proof that an index was required or a transmission lost. VCM records preserve
each section's activation time/splice declarations; future changes are not applied
using STT or the computer clock. NTT preserves language and source/application
identity; duplicate names remain conflicts rather than preferred labels.

Every assembled record carries the exact analysis revision, cutoff, original
section ID, record offset and revision-descriptor offset. Incomplete/conflicting
subtables remain explicitly partial. `network_lineup_complete` is always false.
No cross-subtable synchronization, network/channel-map joins, receiver policy,
firmware/media execution or snapshot export is added. Existing generic `query`,
`diff_snapshots`, services and export contracts are unchanged.

Queries cap eligible/excluded observed section variants at 8192, semantic groups
at 512, and records emitted across a page at 8192. Limit failures return an error,
not truncated apparently complete data; original section inspection stays available.
Excluded evidence is bounded but not paginated separately. Completeness denotes
wire-section/key/range coverage, not complete decoding of every text or opaque
descriptor. Supported coverage and test entry points are recorded in
[PROTOCOL_COVERAGE.md](PROTOCOL_COVERAGE.md#current-protocol-extension-support).
