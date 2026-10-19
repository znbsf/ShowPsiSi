# DVB-I input and evidence design

The bounded local C++ importer/API and independent Qt/Web document workspaces
are implemented. See [DVB-I workbench](DVB_I_UI.md) for interaction scope.
Network retrieval, playback and full-schema/receiver behavior remain unsupported.
Current contract, security limits and verification boundary: [DVB-I API](DVB_I_API.md).

## Normative baseline

The official [DVB-I publication page](https://dvb.org/?standard=service-discovery-and-programme-metadata-for-dvb-i)
currently distinguishes published **ETSI TS 103 770 V1.2.1 (2024-09)** from
**BlueBook A177r8 / draft V1.3.1 (2026-06)**. Use an explicit schema/profile version;
do not silently treat a newer draft as the published edition.

The [published specification](https://www.etsi.org/deliver/etsi_ts/103700_103799/103770/01.02.01_60/ts_103770v010201p.pdf)
defines service lists, service identifiers, alternative instances, delivery
parameters and regional LCN tables. This input is XML metadata, not TS packets.
The official page also links schemas/examples and the reference client. Their
redistribution terms must be checked before bundling anything.

## Implementation sequence and remaining boundary

1. Local XML import into the shared C++ engine. No network dependency, no media
   fetching, no application execution. Preserve input bytes and their SHA-256.
2. Namespace-aware inspection with bounded document size, nesting, node/text
   counts and diagnostic limits. Reject DTD/external entities; do not fetch XSDs,
   XInclude, URLBase, application links, logos or media during parsing.
3. Services/list/instance/LCN projections using stable DVB-I identifiers. Same
   display name is not identity. Duplicate identifiers produce explicit conflicts.
4. Shared Qt/Web input chooser: TS capture or DVB-I XML. The existing TS session
   remains intact when an independent metadata import fails. Avoid making
   non-TS input look like a successful TS scan with fake PID/CRC values.
5. Source-linked XML tree with line/path evidence. Jump to the original XML;
   never invent section byte offsets, PID, CRC, packet position or PAT/PMT.
6. Optional explicit HTTP retrieval in a later increment. Bound time/bytes/
   redirects; preserve source and cache validators; do not log credentials or
   silently follow application/media links. Network errors remain distinct from
   XML/semantic validation failures.

## Shared evidence requirements

A document has its own revision and hash. A source locator identifies that
revision, namespace-expanded element path and precision. Source replacement
invalidates old locators. XML text reformatting cannot retain stale byte offsets.
The authoritative original remains separate from the formatted display.

The semantic topology may show List → Service → Instance, with alternative
regional LCN assignments and delivery candidates as relationships. A broadcast
instance can reference DVB ONID/TSID/SID, but joining it to captured SI requires
matching all available identifiers and retaining both sources. A matching name
or LCN is never sufficient. Announced delivery is not proof of reception.

Preserve multiple language names, regions, unknown extension elements and
unsupported delivery types. Search and pagination must report whether they
cover all objects or only loaded objects. A summary must not erase alternatives.

## Test loops and stop conditions

- Namespace prefix changes/default namespaces, wrong/unknown namespace versions,
  extension elements, duplicate identifiers, missing mandatory identifiers,
  malformed numbers and conflicting regional LCNs.
- Multiple instances of one service; duplicate names across services; DVB-S/T/C
  and broadband delivery coexistence; missing/ambiguous broadcast association.
- Unicode, XML entities, escaped content and UI plain-text rendering; no script
  interpretation. Test DTD/external entity/XInclude handling and bounded failure.
- Truncated documents, excessive depth/nodes/text, oversized inputs, cancellation,
  failed replacement and stale inspector results. Preserve previous evidence.
- Real C++ importer → JSONL/MCP → Qt/Web selection/source jump, both themes,
  keyboard navigation and large lists. Pure parser tests alone are insufficient.
- A separately licensed real example plus independently authored negative
  fixtures. Record exact standard edition, fixture provenance, supported
  elements and unresolved semantics; no edition-wide conformance claim.

Each increment closes only after implementation, adversarial tests, independent
review and combined regressions pass. A real HTTP source or complete EPG
schedule parser is not implied by passing local service-list import tests.
