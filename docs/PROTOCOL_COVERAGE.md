# Broadcast protocol coverage and evidence

## What “supported” means

ShowPsiSi consumes MPEG transport-stream packets. It does not tune, demodulate,
decrypt conditional-access content, or validate an RF transmission standard.
Three different claims must remain separate:

1. **Verified application path**: a fixture or captured stream passed through the
   ShowPsiSi JSON API and its resulting fields were asserted by a test.
2. **SDK decoder available**: the linked TSDuck registry contains a decoder and
   its XML model. This is not evidence that every field, malformed input,
   operator variant, UI workflow, or edit/export operation has been tested.
3. **Raw preservation / unknown**: bytes can be retained and inspected even when
   there is no registered semantic decoder. A hex dump is not protocol support.

The SDK used for this audit is **TSDuck 3.39-3956**, verified with `tstabcomp
--version`. Installed `tsduck.tables.model.xml` contains 45 table model entries,
including the two generic table fallbacks, and 307 descriptor model entries.
These are XML model counts, not a count of unique table IDs or a conformance score.
The rebuilt application reports **43 registered table names and 306 registered
descriptor names**. The running application's `capabilities.native_registry` is the authoritative
inventory of the actually linked decoder registry. Future SDK versions may differ.

## Standards and boundaries

| Family | Applicable transport-stream decoding | Evidence and limits |
| --- | --- | --- |
| MPEG systems | PAT, CAT, PMT, TSDT; registered MPEG descriptors and extension descriptors | Core fixture tests exercise PAT/PMT/CAT. Generic registry decoding supplies additional table/descriptor fields. |
| DVB-S/S2/S2X, DVB-T/T2, DVB-C/C2 | Common DVB SI such as NIT, BAT, SDT, EIT, TDT/TOT; registered satellite, terrestrial, cable and generation-specific delivery-system descriptors | Existing DVB synthetic fixture and optional recorded terrestrial sample; delivery-specific descriptor availability is SDK-level unless individually tested. The RF modes are not distinct table parsers. |
| ATSC transport-stream PSIP | MGT, TVCT/CVCT, ATSC_EIT, ETT, STT, RRT, DCCT, DCCSCT | Added synthetic MGT/TVCT/STT tests, including a TVCT on an MGT-advertised nondefault PID. Other registered models are SDK-available. This does not claim ATSC 3.0 IP/ROUTE/MMT support. |
| ISDB | Shared MPEG/SI plus BIT, CDT, DCT, DLT, ERT, ITT, LDT, LIT, NBIT, PCAT, SDTT | Added synthetic BIT/CDT/SDTT/LDT/NBIT/ITT API tests. Japan/Brazil character and regional interpretations must not be inferred from the word ISDB alone. |
| SCTE | Registered splice information and cable emergency alert models/descriptors | SDK-available; no full SCTE broadcast conformance claim. |
| DTMB | MPEG TS and recognized PSI/SI inside a provided TS can use the relevant common decoders | Pinned `Standards` enum has no DTMB member. No verified DTMB-specific signaling fixture or complete DTMB decoder claim. DTMB RF transmission is not interchangeable with a blanket DVB-SI assertion. Unknown signaling stays raw. |
| Operator / private / special | Registered private PDS descriptors, table-specific descriptors, extension descriptors; declared local extension fields | Scoped private descriptor fixture exists. Arbitrary unpublished syntax is not automatically knowable. No decryption, invented descriptor names, or blanket private-protocol support. |

## Complete pinned XML table-model inventory

AIT, ATSC_EIT, BAT, BIT, CAT, CDT, CIT, CVCT, DCCSCT, DCCT, DCT, DLT,
DSMCC_stream_descriptors_table, EIT, ERT, ETT, INT, ITT, LDT, LIT, MGT,
NBIT, NIT, PAT, PCAT, PMT, RCT, RNT, RRT, RST, SAT, SDT, SDTT, STT,
TDT, TOT, TSDT, TVCT, UNT, cable_emergency_alert_table,
discontinuity_information_table, generic_long_table, generic_short_table,
selection_information_table, splice_information_table.

Descriptor inventory is exposed from the live registry rather than duplicated
here as a stale hard-coded list. Examples verified in the pinned headers include
SatelliteDeliverySystemDescriptor, S2SatelliteDeliverySystemDescriptor,
S2XSatelliteDeliverySystemDescriptor, S2Xv2SatelliteDeliverySystemDescriptor,
TerrestrialDeliverySystemDescriptor, T2DeliverySystemDescriptor,
CableDeliverySystemDescriptor, C2DeliverySystemDescriptor,
C2BundleDeliverySystemDescriptor, and ISDBTerrestrialDeliverySystemDescriptor.
These names establish decoder availability, not that this application tunes those
systems or has tested every descriptor combination.

## Context, collisions, and private namespaces

`analyze.standards` selects `auto`, `dvb`, `atsc`, `isdb`,
`isdb-japan`, `isdb-brazil`, or `scte` (see the live API schema). The SDK's exact
standard flags are NONE, MPEG, DVB, SCTE, ATSC, ISDB, JAPAN and ABNT. Forced
ISDB does not by itself prove Japan or Brazil regional settings.

Auto mode is best-effort evidence accumulation, not a proof of standard identity.
Table ID 0xC7 means ATSC MGT or ISDB LDT; 0xC8 means ATSC TVCT or ISDB CDT.
An ID alone is insufficient. Source PID, explicit standard context, table shape,
and successful full-table deserialization matter. The SDK may prefer a registered
fixed-PID interpretation even with a different requested family: in a tested ATSC
context with explicitly included ISDB PIDs, CDT/LDT still decoded as ISDB. Thus
the context is a disambiguation preference, not a strict protocol rejection filter.
When input is ambiguous, choose
the known standard explicitly and retain raw bytes. Enabling every standards flag
simultaneously cannot resolve a collision.

Descriptor tags also have overlapping namespaces. Preserve containing table ID,
DVB private-data-specifier (PDS), MPEG/DVB extension tag, and registration context.
A PDS applies to the relevant descriptor loop; do not carry it indiscriminately
between loops. Unknown private tags remain generic. Registration identifiers are
recorded through DuckContext and must not accidentally leak between unrelated
analysis sessions. A descriptor's tag alone must never select a private extension.

The generic table tree is produced from a complete matching table generation,
not by pretending one section of a multi-section table is the entire table.
`native_table_complete` reports assembly completeness; the generic XML fallback
is distinguishable from a semantic decoder. Existing high-level services/events
are convenience projections, not an exhaustive representation of all standards.
ATSC/ISDB fields remain accessible in the generic native tree even when no
specialized service-list projection or editor exists.

## PID discovery and packet scope

- PAT discovers PMT PIDs; PAT program zero can advertise a network PID.
- ATSC PSIP uses 0x1FFB; MGT entries advertise additional table PIDs.
- Pinned ISDB constants include SDTT 0x23 / terrestrial SDTT 0x28, BIT 0x24,
  NBIT/LDT 0x25, additional EIT 0x26/0x27, CDT 0x29, and AMT 0x2E.
- `extra_pids` explicitly includes otherwise unadvertised section PIDs. This is
  necessary for operator-private tables and tables whose routing is not covered
  by the application's current discovery path.
- Presence of an ISDB IIP PID constant 0x1FF0 does not make IIP a generic PSI table.
  Nor does seeing an arbitrary PES PID mean its payload should be parsed as SI.
- A table that appears only before its advertising PAT/MGT is discovered is not
  guaranteed to be recovered by forward-only discovery; repeat signaling or an
  explicit PID selection avoids that issue.

## Reproducible fixtures

`tests/test_protocol_coverage.py` contains CRC-correct binary sections generated
using the pinned SDK's `tstabcomp` and the following model-valid XML. The tests
packetize them as TS, invoke the real core, and assert semantic native tree names
and fields. They are deliberately small synthetic fixtures, not captured RF
samples or certification vectors.

```xml
<tsduck>
  <MGT><table type="TVCT-current" PID="0x123" version_number="0" number_bytes="0"/></MGT>
  <TVCT transport_stream_id="1"><channel short_name="LAB-HD" major_channel_number="7" minor_channel_number="1" modulation_mode="8-VSB" channel_TSID="1" program_number="101" source_id="101"/></TVCT>
  <STT system_time="1450000000" GPS_UTC_offset="18" DS_status="false"/>
  <BIT original_network_id="2" broadcast_view_propriety="true"><broadcaster broadcaster_id="1"/></BIT>
  <CDT download_data_id="3" original_network_id="2" data_type="1"><data_module>CAFE</data_module></CDT>
  <SDTT table_id_ext="3" transport_stream_id="1" original_network_id="2" service_id="101"/>
  <LDT original_service_id="101" transport_stream_id="1" original_network_id="2"><description description_id="9"/></LDT>
  <NBIT original_network_id="2"/>
  <ITT event_id="7"/>
</tsduck>
```

Run after building the current core: `python -m unittest discover -s tests -p
 'test_protocol_coverage.py' -v` (set the runtime library path for an unpacked SDK).
The fixture assertions are the evidence; merely compiling XML with TSDuck is not
an application test pass.

## Verified pinned APIs and upstream source

The inspected official SDK headers are packaged with the pinned developer release.
Source links below target the release tag, rather than assuming current online API
matches the older installed SDK:

- [PSIRepository.h](https://github.com/tsduck/tsduck/blob/v3.39-3956/src/libtsduck/dtv/signalization/tsPSIRepository.h): `getTableFactory(TID, Standards, PID, cas)`, `getSectionDisplay`, `getRegisteredTableNames`, `getRegisteredDescriptorNames`.
- `tsBinaryTable.h`: `toXML(DuckContext&, xml::Element*, const XMLOptions&)` selects registered decoders with generic fallback.
- `tsDescriptor.h`: `toXML(DuckContext&, xml::Element*, PDS, TID, bool)` and `deserialize` preserve table/PDS context.
- `tsTablesDisplay.h`: `displayTable`, `displaySection`, `displayDescriptor`, `displayDescriptorList` supply semantic display with raw fallback.
- `tsNames.h`: `ts::names::TID(const DuckContext&, uint8_t, uint16_t, NamesFlags)`.
- `tsEDID.h`: standard, private-PDS, MPEG/DVB extension, and table-specific descriptor identifiers.
- `tsDuckContext.h`: `resetStandards`, `addStandards`, `setDefaultPDS`, registration-ID tracking/reset.
- `tsStandards.h`, `tsTS.h`, `tsPSI.h`, and `tsduck.tables.model.xml`: standard flags, PID/table ID constants, exact model inventory.

Public specification links are kept separately in `references/standards.json`.
A reference to an overall standard is labeled as such; it does not assert an exact
clause match or imply that the newest standard edition is fully implemented by
TSDuck 3.39. No PDFs are bundled. Reference browsing is optional and does not run
inside the parsing or packet-analysis path.

## Validation result

On 2026-10-16, **7 protocol API tests passed** against the rebuilt native core.
Besides the table fixtures, these check auto-mode fixed-PID evidence, opposite
ISDB context producing generic ATSC fallback, PDS isolation across descriptor
loops and files, unknown private byte retention, registry counts, and correct
standard links (including absence of an incorrect B10 link for CDT).
A registration descriptor is included in the private fixture, but a claim that
every registration-dependent private codec interpretation is covered would be
unjustified; that remains a targeted future regression area.
The optional official-reference index is 12,490 bytes on disk, with five sources,
191 descriptor associations and 26 table associations. These associations are
standard-level, not clause-level. CDT/SDTT have no B10 link because their SDK
headers cite ARIB STD-B21 instead.
