# Evidence-linked topology API v1

Implementation scope: separate topology feature branch, not the installer release.
This is a read-only C++ projection over the same `latest` / `completeGroup`
selection used by ordinary snapshots. Existing `query`, Services and semantic
snapshot-diff meanings are unchanged. JSONL, MCP and both frontends use one
`api/tools.json` operation, with no frontend protocol parser.

## Request

`query_topology({at_packet?, analysis_revision?, family?, parent_id?, offset?, limit?})`

- A successfully completed analysis is required. `at_packet` is the inclusive,
  zero-based section-completion cutoff, default `packets - 1`; out-of-range values
  fail. Optional `analysis_revision` must equal the current analysis revision.
- `family` is `all` (default), `dvb`, `atsc`, `isdb` or `unresolved`. It filters a
  projection and cannot change the analysis decoder profile.
- Omitted `parent_id` pages all nodes in deterministic parent-before-child order.
  Empty string requests root nodes; a nonempty ID requests its immediate children.
- `offset` defaults to zero; `limit` defaults to 200 and is capped at 500.
  `page.total` is the complete filtered candidate count, not the returned count.
  Keep revision, profile and cutoff fixed while paginating.
- A graph exceeding 20,000 nodes, 40,000 edges or 200,000 evidence constructions
  fails explicitly. Per-object evidence is capped at 2,048 sources and each
  conflicting attribute at 256 candidates. It never returns a silently truncated graph.

## Response

```json
{
  "schema_version": 1,
  "analysis_revision": 1,
  "at_packet": 3,
  "interpretation_profile": "dvb",
  "status": "ok",
  "diagnostics": [],
  "counts": {"nodes": 6, "edges": 5, "unresolved": 0, "raw_sections": 4},
  "coverage": {
    "supported_adapters": ["dvb", "atsc", "isdb"],
    "active_adapter": "dvb",
    "missing_tables": [],
    "unsupported_relations": ["Explicit strings identifying unsupported semantic scope"],
    "limits": {"nodes": 20000, "edges": 40000, "evidence": 200000, "page": 500}
  },
  "nodes": [], "context_nodes": [], "edges": [],
  "projections": [{"family": "dvb", "label": "DVB", "roots": ["dvb:network:10"]}],
  "page": {"offset": 0, "limit": 200, "total": 6, "has_more": false, "next_offset": null}
}
```

IDs are opaque within this analysis/profile. A node has `node_id`, `family`,
`object_type`, `identity` (typed raw numeric identifiers, explicit null unknowns),
`label`, `attributes`, `attribute_conflicts`, `parent_id` (null for roots),
`observation_status`, `resolution_status`, `unresolved_reasons` and `evidence`.
Conflicting field values are null in `attributes`; `attribute_conflicts[field]`
retains every candidate value with its own evidence. No display name is a join
key. Observation and relation resolution are separate; a received declaration
is not proof of media reception. Components are PMT announcements.

`context_nodes` supplies missing ancestors of the current page, in projection
order. Edges on each page are all outgoing edges of its page nodes, with
`edge_id`, `from`, `to`, `relation`, `resolution_status`, `evidence`. Cross-parent
references do not change the chosen deterministic display parent; an edge target
can be on another page. Do not recursively follow relations as tree children.

Delivery declaration nodes have `object_type: delivery_parameters` and retain
`parameters` with explicit Hz/sym/s units plus raw modulation/FEC/bandwidth codes.
Their identity is the exact section/descriptor observation under its transport,
not a deduplicated physical transponder. Satellite lookup adds
`satellite_candidate` children and `candidate_association` edges whose
`resolution_status` is `candidate`. Candidate nodes remain `unresolved`: matching
a nominal orbital slot cannot confirm spacecraft identity or capture-date
assignment. `physical_transponder_id`, `confirmed_satellite` remain null and
`reception_verified` remains false.

Candidate nodes and edges also carry additive `reference_sources` entries with
`{catalog, source}` from the existing satellite catalog, including its revision,
fingerprint and attributed source. These are external lookup provenance, distinct
from wire `evidence`; they must not be rendered as fields broadcast in the NIT.
The original descriptor remains the precise wire evidence for the advertised
position/frequency. Malformed registered DVB descriptors retain raw evidence with
empty `parameters` and an explicit unresolved reason. A DVB-T unknown/zero center
frequency produces `frequency_hz: null` and `parameter_status: partial` while
retaining known bandwidth/modulation codes and the raw `frequency_code`. This
includes the `0xFFFFFFFF` sentinel normalized by the SDK; it is never 0 Hz or
a guessed frequency from the recording filename. Missing catalogs and valid
positions with no candidates remain explicit without selecting a satellite.

## Exact source contract

Every semantic node and edge has evidence. Each evidence item carries:

```json
{
  "analysis_revision": 1, "at_packet": 3,
  "section_id": "exact opaque section identity",
  "table_identity": {"pid": 17, "table_id": 66, "extension": 1, "version": 1, "section_number": 0, "current": true},
  "assertion_key": "name", "role": "declares",
  "locator": {
    "field_id": "opaque section-scoped field token",
    "container_id": "opaque section-scoped loop token",
    "precision": "field", "resolution_status": "resolved",
    "byte_range": {"offset_scope": "section_bytes", "offset": 21, "length": 12},
    "display_path": "name"
  }
}
```

Source navigation calls `inspect({id: section_id, at_packet, analysis_revision})`.
The optional revision parameter rejects stale evidence. `inspect` adds
`analysis_revision` and `evidence_anchors[]` without changing existing output.
Each anchor has the locator fields plus `label`; anchors describe the original
section, never a merged XML offset. Frontends may expose a dedicated Evidence
anchors group and highlight the returned original bytes. Match returned IDs,
not renderer tree indices or textual names. Unsupported fields use explicit
`precision: section`, null field/container IDs and null byte range.

First supported field ranges include PAT program mapping; PMT program/PCR/ES
headers; SDT triplets and service name/type/provider; NIT transport loop entries;
VCT name/channel number/transport/program/source; and validated Japan remote key
and partial-reception service IDs. Descriptor fallback is `container` precision.

`services[].source_id` remains the existing section-evidence string. It is not
renamed or reused. ATSC numeric source identifiers are `atsc_source_id`.

## Implemented adapter boundaries

- DVB: canonical NIT/SDT and PAT-selected PMT, exact ONID/TSID/SID, all NIT
  membership edges, announced-other vs actual observations, explicit PAT-only
  observations without fabricated ONID, contradictory declarations preserved.
- ATSC 1.0: independently validated complete TVCT/CVCT, distinct lineups, one-part
  CVCT and two-part numbering, reserved numbering retained raw, local
  channel_TSID/program/PAT/PMT mapping, duplicate slot observations, source
  references, inactive/analog/hidden semantics and service-location disagreement.
  No ATSC 3.0. Zero source ID remains unidentified, never a shared source join.
- ISDB: explicit Japan/Brazil/unspecified profiles and basic NIT/SDT/PAT/PMT.
  Japan TS-information remote key, raw transmission types and partial-reception
  references have bounded descriptor provenance. Brazil/unspecified regional
  descriptor semantics are explicitly unsupported pending regional validation.
- `auto`, SCTE and DTMB currently retain unresolved MPEG observations; no family
  is guessed from ambiguous table IDs or names. Select the intended analysis
  profile and rescan for semantic family relationships.
- Bounded DVB-S/S2/C/T delivery declarations are separate `delivery_parameters`
  nodes under their exact transport. Values retain Hz/sym/s units, raw codes,
  source descriptor and `physical_transponder_id: null`. Existing nominal-slot
  lookup supplies `satellite_candidate` nodes and `candidate_association` edges,
  never a confirmed satellite/physical-TP parent. `reference_sources` retains
  the existing catalog fingerprint/revision and each entry’s attributed source.
  Missing catalog, no match, malformed parameters and co-located candidates remain
  explicit; ISDB same tags do not activate these DVB interpretations.
- BAT/LCN, actual physical transponder/satellite identification, S2X/T2 expansion,
  PSIP auxiliary/EPG and ISDB BIT/CDT/SDTT/logo/broadcaster relationships remain
  explicit unsupported scopes. Existing raw inspection and Metadata are retained.

Protocol basis for the implemented numbering and descriptor subsets:
[ATSC A/65:2013 §6.3.2](https://www.atsc.org/wp-content/uploads/2021/04/A65_2013.pdf),
[ETSI EN 300 468 v1.19.1](https://www.etsi.org/deliver/etsi_en/300400_300499/300468/01.19.01_60/en_300468v011901p.pdf),
[ARIB STD-B10 v4.6-E2](https://www.arib.or.jp/english/html/overview/doc/6-STD-B10v4_6-E2.pdf).
These bounded implemented subsets do not claim complete or latest conformance.

## Reproduction

`tests/topology_fixture.py` produces exact synthetic wire sections and TS packet
streams. `tests/test_topology.py` drives the production core and MCP, not mocked
protocol outputs. Run with an explicitly selected isolated build:

```sh
SHOWPSISI_CORE="$PWD/build/topology-core/bin/showpsisi-core" \
  python -m unittest discover -s tests -p test_topology.py -v
```

Local example outputs and corresponding inputs are generated under ignored
`artifacts/topology-contract/`. They are test evidence, not bundled fake results.
UI/native platform acceptance is separately owned and must test the combined
source. No publication, merge or release is implied by this API document.

### Local validation checkpoint

Linux cloud build, 2026-10-19, isolated `build/topology-core`, TSDuck 3.45-4798:
production and test-only cancellation engines built successfully. The final
strict engine invocation in `artifacts/topology-engine-final4/` passed **250
checks, zero failures/errors/skips**, including 27 topology tests, nine shared
presentation tests and the existing real-recording baseline. New Qt tests are
registered but their execution is separately reported by the Qt work owner.

A separate real French UHF22 topology run produced **81 nodes, 80 edges and 12
services** at cutoff 978400 from 1855 retained sections; every object had a
nonempty display label, unrelated incomplete EIT schedules did not affect the
supported topology status, and source SHA-256 remained
`24143de80d28461d084dfb75279da520f335de36b7c35f6398ed6d510daa5937`.
Evidence is in ignored `artifacts/topology-contract/real-dvb-report.json`.

The first aggregate run caught the intentionally expanded MCP tool count
assertion (11 to 12), which was updated. A later run correctly refused an
optional-recording skip when the fixture appeared during the run; reruns used a
stable read-only recording and had no skips. The real-capture smoke also exposed
and fixed empty-name display labels and unrelated incomplete-table warnings.
These failures were retained, not suppressed. This checkpoint covers the engine
source plus the current shared presentation work; combined frontend/native
platform acceptance and release remain separate gates.

### Delivery declaration validation checkpoint

The subsequent bounded delivery/candidate increment passed **256 checks, zero
failures/errors/skips** in `artifacts/topology-delivery-engine-final2/`: 32 actual-core
topology tests, ten shared presentation checks and all registered baseline suites.
The synthetic S2/C/T fixture yields three exact-loop delivery declarations and
two co-located nominal HOTBIRD candidates, each with separate wire/catalog
provenance. Malformed BCD, missing catalog, no match, historical cutoff and
private-display-name/ISDB-context isolation are exercised.

The real French recording now yields **88 nodes, 87 edges, 12 services and seven
DVB-T delivery declarations**. All seven carry the original `0xFFFFFFFF` unknown
center-frequency code, null Hz and known 8 MHz bandwidth; these unknowns correctly
make the expanded topology `incomplete`. No RF frequency is inferred from the
UHF filename. Source SHA-256 is unchanged from the earlier checkpoint. The
real-capture smoke found this sentinel case; a dedicated fixture now verifies
both the sentinel and zero without discarding other known parameters. Reports:
`artifacts/topology-contract/real-dvb-delivery-report.json` and
`artifacts/topology-contract/dvb-delivery.json`.
