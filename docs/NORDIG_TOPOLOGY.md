# NorDig list and simulcast declaration objects

This development increment extends `query_topology` without adding an operation,
a NorDig activation switch or a receiver selection action. It uses the existing
namespace-backed NorDig LCD v2 decoder and the graph's selected complete,
valid-current NIT sections. Existing per-service LCN/list alternatives, ordinary
snapshots, diffs and export behavior are unchanged.

## Pinned specification and interpretation

[NorDig Unified Requirements 3.2.2](https://nordig.org/wp-content/uploads/2016/03/NorDig-Unified-Requirements-ver.-3.2.2.pdf),
§12.2.9.1–3, defines the NIT transport-loop lists and identifies a v2 list within
its original network by `channel_list_id`. The implementation therefore joins
list declarations by ONID and list ID, retaining their transport/service entries
and name/country disagreements. The publication is November 2025; this is a
bounded inspection projection, not NorDig receiver certification.

[NorDig Rules of Operation 3.2.2](https://nordig.org/wp-content/uploads/2016/03/NorDig-Rules-of-Operation-ver.-3.2.2.pdf),
§12.1.10.5, requires earlier PDS 0x00000029 for NorDig-specific signalling,
including private bytes inside DVB descriptors. The existing decoder enforces
wire namespace context rather than interpreting a private tag by itself.

Unified Requirements §12.3.5 describes NorDig simulcast replacement using SDT
linkage type 0x82. This is distinct from the EACEM/DTG HD-LCN descriptor family.
The later bounded declaration projection is described below; receiver
hide/replace/reorder policy is not implemented.

Ordinary DVB and default/explicit auto inspection already recognize NorDig when
its on-wire PDS namespace is present. No separate enablement is required. The
existing topology adapter requires the explicit DVB analysis family; auto
*topology* remains unresolved because its family-wide semantics are ambiguous.
A topology view filter does not change the analysis interpretation.

## Additive graph contract

- `channel_list` is a root node keyed by namespace + ONID + list ID. Its parent is
  null, even if exactly one NIT network is currently observed. Every declaring
  network keeps an `announces` edge; one network ID is never chosen arbitrarily.
- List attributes include `channel_list_name`, `country_code`,
  `selection_status: selection_required`, `selected: false` and
  `transmission_completeness: unknown`. Conflicting name/country declarations
  use the existing null attribute plus source-linked `attribute_conflicts` form.
- `channel_list_entry` is a child keyed by that list plus the full ONID/TSID/SID
  triplet. It carries logical number, visibility and the existing allocation
  status. Different transport streams aggregate under their list. Different
  ONIDs never merge, even if names, list IDs, TSIDs and SIDs match.
- Conflicting number/visibility declarations and duplicates within one list
  remain explicit conflicts. Different services sharing a number stay separate:
  no service-category priority, simulcast identity or selection is inferred.
- Each entry has a `references` edge to an observed exact-triplet SDT service.
  Without that service, the entry remains an unresolved declaration. It does not
  create a service, borrow an equal SID from another transport or infer reception.
- Empty lists, hidden/reserved allocations and SDT-absent declarations survive.
  Every entry retains `selected: false` and `receiver_policy_applied: false`.

The existing graph revision, packet cutoff, pagination and fixed resource caps
apply. Incomplete newer NIT generations do not restore old complete lists;
version reuse cannot recover stale sibling sections. A complete selected NIT
is not proof that every network/channel-list transmission was captured.

## Original-byte evidence and validation

`inspect.evidence_anchors` adds original-byte anchors for each NorDig list,
list ID/name/country and service/number/visibility entry. Number and visibility
anchors both span their shared two-byte wire word. Aggregation retains all
section-specific sources, including multiple network declarations. No offset is
claimed in merged SDK XML. First-loop/private-namespace lookalikes, invalid CRC,
next tables and malformed nested payloads do not supply graph objects.

`tests/test_nordig.py` and `tests/test_topology.py` exercise list merging and
isolation, conflicts, unknown services, wrong contexts, cutoffs/reused versions,
exact source navigation and bounded metadata/evidence refusal. Qt and browser
source-navigation cases cover Hex selection and restoring the origin on Back.
These fixtures do not establish native Windows or receiver behavior.

## SDT simulcast replacement declarations (later increment)

The DVB adapter adds `simulcast_replacement_reference` children under the
declaring SDT service. Identity includes the target ONID/TSID/SID and namespace;
the node ID also includes the origin service, so unrelated origins never merge.
The origin `contains` its declaration. A `references` edge points to a captured
SDT service only when the entire target triplet matches. Missing targets remain
unresolved declaration nodes; no synthetic service is created. Equal-target
declarations merge evidence, while competing targets remain separate conflicts.
Self references are flagged. Cycles remain finite relationship edges; neither
parent traversal nor receiver actions follow those links.

Admission requires canonical SDT PID 0x0011, long-header table 0x42/0x46, a
selected complete valid-current generation, a complete DVB linkage prefix,
linkage type 0x82, and a preceding valid PDS 0x00000029 in the same service loop.
The application projects only the known common linkage prefix; any private tail
remains opaque in the original descriptor. Missing/wrong/late/overridden or
malformed PDS, intervening private_data_indicator_descriptor, another service/section's namespace, other table/PID contexts and
other linkage types do not create NorDig declarations. No service type or codec
is inferred from the replacement relationship.

Every declaration retains the source service, original PDS word, complete
linkage descriptor and exact target-triplet/type byte anchors. `references` on
this contextual node links to the verified Unified 3.2.2 §12.3.5. The generic
`linkage_descriptor` native XML name deliberately receives no blanket NorDig
reference. LCD v1/v2 exact native names separately link through the standard
registry only when native namespace decoding and the DVB reference context
match; display names/tags cannot supply that match.

`selected` and `receiver_policy_applied` remain false. Media equivalence and
reception/decoder support stay unverified. All captured services remain visible;
no channel-number reassignment, hiding, tuning or playback is performed. Existing
revision/cutoff/paging and fixed graph evidence limits apply. Synthetic real-core
tests cover namespace barriers, contexts, targets, cycles, generation boundaries,
source locators and fixed limits.

Namespace scope follows the wire contract.
[ETSI TS 101 211 V1.13.1 §4.2.7.1](https://www.etsi.org/deliver/etsi_ts/101200_101299/101211/01.13.01_60/ts_101211v011301p.pdf)
ends PDS scope at the next PDS or private-data-indicator descriptor. Both the
original descriptor loop and this projection now clear that scope, including
malformed replacement descriptors; a new valid PDS can establish it again.
The baseline-compatible regression is in `test_protocol_coverage.py`.
SDK merged XML is retained unchanged with an explicit `native_decode_warnings`
interpretation boundary shown by both frontends. Unanchored SDK section text is
suppressed for affected source sections. Standard links with `required_pds`
require the original contextual descriptor; merged SDK private names alone cannot
supply that evidence. Corrected source descriptors remain available beside Hex.
