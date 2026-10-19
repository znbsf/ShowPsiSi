# Application signalling source-card contract

`inspect` adds an
`application_signalling` envelope for AIT/UNT table identities. This is a read-only
summary for the existing Metadata/Topology interaction, not a new tab or a
receiver runtime. AIT and the bounded UNT notification adapter require explicit
`dvb`; other interpretation profiles retain native/raw evidence without reusing
these semantic adapters.

## Envelope and source navigation

Fields: `schema_version: 1`, `analysis_revision`, `at_packet`,
`interpretation_profile`, `status`, `objects`, `relations`, `diagnostics`,
`evidence_anchors`, `scope`, `unsupported_relations`.

Objects reuse topology-style `node_id`, `family`, `object_type`, `identity`,
`label`, `parent_id`, `attributes`, `attribute_conflicts`, `observation_status`,
`resolution_status`, `unresolved_reasons`, and `evidence`. Relations use `edge_id`,
`from`, `to`, `relation`, `resolution_status`, and `evidence`. Neither object IDs
nor names are global service identities. IDs are opaque in the stated analysis.

Every semantic object and relation has original-section evidence carrying
revision, cutoff, section identity, table identity, assertion key, role, and a
locator. The locator matches the topology contract: `field_id`, `container_id`,
`precision`, `resolution_status`, `byte_range`, `display_path`. Supported spans
use `offset_scope: section_bytes`. Organization/application IDs and control code
have exact field ranges. Descriptor-derived values use honest containing-
descriptor ranges. No merged XML byte offset is asserted.

Each inspection appends only anchors for its exact inspected section to the
ordinary `inspect.evidence_anchors` list. A relation may reference another
section in the selected complete AIT generation; inspecting that source at the
same cutoff returns its own anchors. The revision field follows the same analysis
counter as ordinary results. Combined frontend integration must retain the
shared topology revision-validation contract on source navigation.

Statuses include `ok`, `incomplete`, `unsupported_profile`, `unsupported_table`,
`invalid`, `incomplete_or_superseded`, `malformed`, and `unresolved`.
Missing/invalid/incomplete/superseded generations never borrow a prior complete
application summary. Bounds are 4096 objects and 8192 relations; overflow returns
an explicit diagnostic and no partial semantic graph while retaining the raw
inspection result.

## AIT subset

- An `application_signalling` context records PID, application type, test flag,
  version and current/next. Each raw application-loop occurrence becomes its own
  `application` object with numeric organization/application IDs and control code.
- `application_properties`, `application_name`, `application_location`, and
  `application_transport` preserve validated SDK values and exact descriptors.
  Unsupported/private descriptors remain opaque references, never guessed from
  names or colliding tags.
- Common-loop transport declarations apply to the selected AIT sub-table.
  Application-local declarations apply only to that application. They add
  alternatives rather than silently overriding common declarations.
- Every application transport label produces a `maps_to` relation to all matching
  in-scope declarations. Multiple matches remain a conflict; no match produces
  an unresolved `application_transport_reference`. Empty labels and missing or
  multiple application-property descriptors are explicitly unresolved/conflicting.
- Duplicate organization/application IDs retain each wire occurrence, control
  code and source. The SDK map is not used to silently discard duplicates.
- HTTP bases, extension strings and initial paths stay separate. No resolved URL
  is fabricated and no URI is fetched. Object-carousel component tags and remote
  triplets are references only. The separate [PAT/PMT carriage view](APPLICATION_CARRIAGE.md)
  adds numeric, nonexclusive program-to-AIT declarations. Component-carousel and
  exclusive application-ownership joins remain unsupported. Other protocol selectors
  remain raw hex.
- Control-code semantics depend on application type. The summary records the
  code without performing or claiming any lifecycle transition or HbbTV runtime
  conformance. Fetch/execution fields state `not_requested`/`not_executed`.

Basis: [ETSI TS 102 809 V1.3.1](https://www.etsi.org/deliver/etsi_ts/102800_102899/102809/01.03.01_60/ts_102809v010301p.pdf),
§5.3.4–5.3.7; pinned TSDuck 3.45-4798 typed table/descriptor validation.
This bounded subset is not complete standard conformance.

## UNT notification subset

UNT uses the same envelope, objects, relations and original-source anchors.
Each original section produces an `update_notification` context retaining full
24-bit OUI, action, version, current/next and processing order. OUI-hash mismatch,
cross-section full-OUI collision and unsupported action types produce explicit
raw-only diagnostics instead of combining unrelated device groups.

`update_device_compatibility` preserves ordered descriptor type/specifier/model/
version selectors and opaque sub-descriptors. Explicit wire-length/count checks
reject omitted or excess compatibility selectors even where the SDK tolerates
an exhausted bounded buffer. `update_target` retains each
platform's separate target and operational loops. Smartcard, manufacturer serial
bytes, MAC, IPv4 and IPv6 target declarations preserve fields/masks; no device
is matched and firmware suitability remains null. Wrong-loop and private
selectors remain opaque, unresolved evidence.

Supported operational/common cards include SSU carousel association references,
URI/polling values with explicit minutes/hours units, update advice, event names
and schedule declarations. Subgroup identifiers keep their own defining OUI;
it is never silently equated to the notification OUI. Association tags remain
16-bit values, with no inferred PID or component mapping. A schedule with an
impossible interval is unresolved, and `available_now` remains null.

Compatibility presence is required across the selected UNT sub-table, so an
empty/common-only section does not become a false missing-device diagnostic
when another selected section contains the declarations. Common UNT declarations
apply only to their original section. Operational
location declarations take precedence over same-section common locations, with
both sources retained by `overrides` relations. Multiple locations stay conflicts;
missing or malformed locations do not become usable fallbacks. Invalid override
relations remain unresolved. Other descriptor-specific precedence policies are
not flattened or applied. URI fetching, device eligibility, carousel joins and
firmware installation remain unsupported.

Basis: [ETSI TS 102 006 V1.4.1](https://www.etsi.org/deliver/etsi_ts/102000_102099/102006/01.04.01_60/ts_102006v010401p.pdf),
§9 and Annex C, plus pinned SDK typed validation. Compatibility presence is
checked at sub-table scope, so a valid empty section does not create a false
missing-compatibility diagnostic. Explicit wire-count guards reject missing or
unclaimed selector bytes. No full SSU conformance claim.

## Reproduction

`tests/test_application_summaries.py` drives the production core. Synthetic
fixtures verify scoped labels, multi-section common declarations, duplicate IDs,
version/current-next cutoffs, malformed data, private/unknown protocols, original
byte anchors, resource bounds, and no source mutation. The earlier
`test_application_signalling.py` retains its pinned compiler fixtures and all
payload-prefix truncations. Use `SHOWPSISI_CORE` to select the production binary
from the same source revision as the tests and API files. See
[test commands](../tests/README.md).

## DSM-CC source cards

Supported exact-section DII/DDB cards now share this envelope. Individual DDB
message decoding is independent of complete native-table assembly; both statuses
remain visible. See [DSMCC_RECONSTRUCTION.md](DSMCC_RECONSTRUCTION.md) for the
bounded decoder contract, tested scope, and separately staged reconstruction.
