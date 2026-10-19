# Bounded PAT/PMT-to-AIT carriage evidence

`inspect.application_signalling` adds local carriage declarations when inspecting
a complete current AIT under the explicit DVB profile. This is an additive
source-card view; it does not change native decoding or semantic-diff behavior.

## Protocol basis and boundaries

[ETSI TS 102 809 V1.3.1](https://www.etsi.org/deliver/etsi_ts/102800_102899/102809/01.03.01_60/ts_102809v010301p.pdf)
§5.3.2.1 and §5.3.5.1 identify an AIT-bearing PMT elementary stream through
stream type `0x05` and the `application_signalling_descriptor` (`0x6F`). Its
optional application-type/version loop may be empty. For a nonempty loop omitting the observed type, this adapter retains the
stream-level declaration and labels the type `not_listed`; the join to the
observed AIT is an inference from its same PID, not an explicit type advertisement.
The cited clause does not require exhaustive type enumeration, and §5.3.4.3
describes the version information as a monitoring optimization.
Table 17 and §5.3.3.2 require the descriptor's reserved-future-use bits to be one.
The adapter combines bounded wire checks with the pinned TSDuck 3.45-4798 typed
PAT, PMT and application-signalling descriptor validation.

Joins use only numeric on-wire identities: one selected PAT transport-stream
identity on PID 0, its program-to-PMT-PID mapping, the matching PMT program
number, and the elementary PID of the inspected AIT. Several programs can
reference the same AIT. No exclusive owner, ONID, service name, runtime support,
application launch, remote service or component-carousel association is inferred.

## Additive contract

The existing summary envelope, objects, relations and source locators are
unchanged. `carriage_context` reports a separate `status`, `scope`, `limits`,
`diagnostics`, and, when cards exist, `carriage_count`. Missing prerequisites and
resource limits also append a readable summary diagnostic. They do not discard
an otherwise valid AIT summary.

Each `application_carriage` object has:

- Identity: `transport_stream_id`, `program_number`, `pmt_pid`, `ait_pid`,
  `application_type`, `observed_ait_version`, `test_application_flag`.
- Attributes: `stream_type`, `descriptor_present`, `valid_descriptor_present`,
  `advertised_application_types`, `advertised_ait_versions`, `application_type_advertisement`,
  `descriptor_validation`, `version_signalling`, `version_signalling_scope`,
  `runtime_compatibility: not_evaluated`, `component_carousel_relation: unsupported`.
- Parent: the observed AIT `application_signalling` context.
- Exact original-section evidence for the AIT type, PAT mapping, PMT program,
  elementary-stream container/PID and every matching descriptor. Descriptor
  values use a containing-descriptor range rather than an invented field offset.

`version_signalling` is `matching`, `conflict`, `not_signalled`, `not_declared`,
or `unavailable_malformed_descriptor`. Candidate type/version arrays contain
validated descriptor entries only, as stated by `version_signalling_scope`.
A valid matching descriptor plus a malformed descriptor keeps the limited
`matching` version fact while `descriptor_validation: mixed` and the card/relation
remain unresolved. Both descriptor sources remain navigable. Missing/invalid descriptors or wrong stream
type keep the reference unresolved; conflicting PAT PIDs, repeated elementary
PID declarations, or advertised-version disagreements remain conflicts.

The relation to the AIT is `declares_carriage` when a stream-type-5 valid
signalling descriptor exists, otherwise `references_ait_pid`. Its resolution
status always remains explicit, including when another descriptor or numeric
mapping conflicts. Carriage is nonexclusive; multiple program cards are retained.

Every source reference is bound to the selected analysis revision and packet
cutoff. Navigation uses the existing `inspect` revision guard and exact topology
anchors in the original section. Generation-safe selection happens before this
adapter. Incomplete generations, version reuse, current/next and same-packet
completion order cannot borrow older missing sections. Multiple selected PAT
transport identities withhold the local join rather than selecting one.

## Resource behavior

Limits apply before semantic container allocation or unbounded work:

- 20,000 selected sections; 1,024 PAT/PMT table groups
- 4,096 PAT mapping entries; 4,096 examined PMT streams; 8,192 descriptors
- 256 carriage cards; 2,048 evidence references on those cards
- Existing total summary bounds: 4,096 objects and 8,192 relations

Relations repeat their cards' bounded evidence for standalone navigation. A limit
returns `carriage_context.status: resource_limit`, an explicit diagnostic, and no
partial carriage graph. Original AIT/native/raw inspection remains available.
Other incomplete/missing/malformed context statuses are also explicit.

## Verification and real capture

`tests/test_application_carriage.py` drives the real core with generated CRC-valid
PAT, PMT and AIT sections. Cases cover shared AIT carriage, valid empty descriptors,
exact source anchors, automatic PID discovery, malformed/reserved data, missing
or misplaced descriptors, conflicting mappings/versions, all relevant limits,
cutoffs, incomplete generations, current/next and same-packet version reuse.

A read-only scan of the public French UHF22 recording found the candidate chain
TSID 3 / program 769 / PMT PID 900 / AIT PID 951. Its original descriptor bytes
`6F 03 00 10 E1` violate the reserved-bit rule above. The card therefore remains
unresolved, with the original bytes and exact source links retained. A tolerant
native descriptor rendering is not promoted to validated carriage semantics.
The capture SHA-256 before/after is
`24143de80d28461d084dfb75279da520f335de36b7c35f6398ed6d510daa5937`.

This bounded source-association slice does not establish full HbbTV, DSM-CC
object-carousel, application-ownership, execution or receiver conformance.
