# DSM-CC exact-section evidence and bounded reconstruction

## Delivered source-card slice

`inspect.application_signalling` includes `download_information`,
`download_module_announcement`, and `download_data_block` objects for supported
DII/DDB messages under explicit DVB interpretation. These reuse the source-card
contract in [APPLICATION_SUMMARY_API.md](APPLICATION_SUMMARY_API.md), including
analysis revision, cutoff, original section identity, and exact byte anchors.

An individual DDB can be valid even when its enclosing native multi-section table
is incomplete. Its original section number is preserved and its independent
`block_number` is decoded. No section is renumbered, re-CRC'd or fabricated into
a complete table. Existing native table/XML results remain unchanged.

The `DsmccSection.h` adapter calls the pinned TSDuck protected payload wrapper on
the original, CRC-checked section. It retains SDK validity, buffer-error and
unconsumed-byte checks. Explicit wire guards additionally check framing,
protocol/message IDs, reserved bytes, message length, and exact bounded DII
compatibility/module/private-data loops. Module declarations and compatibility
entries are capped at 256 before SDK allocation. The regression suite exercises
the protected API contract, original version/current flags, actual DDB block
numbers, pinned compiler fixtures, and every payload-prefix truncation.

Only CRC-protected long DII/DDB messages with no adaptation header are supported.
Checksum/private framing variants, other messages, and adaptations return an
explicit unsupported status with original raw evidence. Nonempty module-info is
structurally validated by the pinned SDK's BIOP parser, but retained as opaque
bytes in these cards. Other module-info profiles can remain unsupported. Private
compatibility bytes are never device eligibility decisions.

The exact-section cards retain their own declaration/block scope. Separate
`download_module` objects describe bounded reconstruction at the inspection
cutoff. Zero block size is retained without substituting a default. Duplicate
module IDs remain separate conflicting declarations. No URI fetch, execution,
firmware installation or automatic decompression occurs.

## Bounded captured-module snapshot

Read-only reconstruction uses the same PID, download ID, module ID and module
version, plus the observed announcement epoch and analysis revision. Completion
order includes same-packet observation order. Repeated unchanged announcements
retain an epoch; version transitions start a new one, including version reuse.
Same-version size, block-size or module-info disagreement is a conflict.

DII messages may announce subsets: an absent module is not withdrawn. Blocks
before their applicable announcement remain orphan observations. Missing blocks,
conflicting duplicate bytes, wrong final-block length or ambiguous announcement
state yield no hash. Only a complete captured sequence with checked section CRCs, announced size and
exact block coverage/lengths gets SHA-256. This is a hash of captured module data,
including compressed bytes if present; optional module checksums and signatures
are not evaluated. It does not establish authenticity or device suitability.

Initial limits are 16 MiB per module, 64 MiB of eligible complete-module hash work per snapshot, 256
module identities, and 2048 distinct contributing source sections per module.
Unsupported oversized announcements do not spend the hash-work budget of an
independent small complete module. These constraints apply jointly: a module below 16 MiB can still exceed the source
limit. An announcement consumes a contributing-source slot too, so at most 2047 distinct
block sections fit alongside one DII. Additional declaration/conflict sources
reduce that effective bound. Limits produce `resource_limit` with no hash, never
silent evidence loss. A later paginated module/source query is the route to larger
source sets.
Other explicit work bounds are 8192 source associations across the snapshot,
20,000 capture records to scan, 4096 candidate message variants, 200,000 message
occurrences, 4096 unique module declarations, and 65,536 declaration-occurrence
visits. Counts are checked before the corresponding allocation/iteration.

Each module identity includes `analysis_revision`, `pid`, `download_id`,
`module_id`, `module_version`, `announcement_epoch_order` and
`announcement_epoch_packet`. Its evidence includes every retained contributing
original section, with the exact completion packet/order used in the epoch.
`assembly_status` distinguishes complete, incomplete, conflict, resource limit,
invalid announcement and explicit unsupported cases. `assembled_sha256` is null
unless complete. Source-only cards do not acquire a module hash. The normal
inspect default cutoff remains the last occurrence of the inspected section; an
explicit `at_packet` chooses a later captured snapshot.

Malformed/unsupported replacement announcements, cancellation messages and DDB
messages whose module identity is obscured block safe reconstruction. Their raw
original payload anchors remain navigable. Invalid-CRC and next-table messages
do not contribute to current modules. Blocks outside an announced epoch remain
source cards with an orphan count; no old block is silently replayed.

Cross-PID association, object/filesystem reconstruction, export, decompression
and execution remain outside this slice.

## Sources and tests

Wire semantics: [ETSI TR 101 202 V1.2.1](https://www.etsi.org/deliver/etsi_tr/101200_101299/101202/01.02.01_60/tr_101202v010201p.pdf),
§4.7.9 and Annexes A/B; SSU context:
[ETSI TS 102 006 V1.4.1](https://www.etsi.org/deliver/etsi_ts/102000_102099/102006/01.04.01_60/ts_102006v010401p.pdf).
Pinned implementation review uses TSDuck `v3.45-4798`:
[download-data decoder](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/tables/mpeg/tsDSMCCDownloadDataMessage.cpp),
[user/network decoder](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/tables/mpeg/tsDSMCCUserToNetworkMessage.cpp),
and [long-section payload wrapper](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/tables/tsAbstractLongTable.cpp).
The SDK module assembler is not used; its default block-size/decompression
behavior is unsuitable for this evidence-preserving scope.

`tests/test_dsmcc_summaries.py` and `tests/test_dsmcc_reconstruction.py` use the
production core to cover exact-section cards, PID/download/version isolation,
epochs and same-packet order, reused records, orphan/conflicting/missing blocks,
final-block length, malformed identity barriers, work/source/byte limits and
reanalysis. Complete-module hashes are checked against the original DDB bytes;
incomplete, conflicting and resource-limited modules have no hash.

The public [TSDuck France UHF22 recording](https://tsduck.io/streams/?stream=france-dttv)
provides captured DII/DDB examples, including an incomplete native table whose
individual DDB remains inspectable and announcements above the reconstruction
limit. Captured module bytes are not necessarily a complete application or
firmware image. Tests do not establish BIOP reconstruction, cross-PID association,
decompression, checksums/signatures or complete HbbTV/SSU receiver conformance.
Run the [combined engine tests](../tests/README.md) for the exact source revision.
