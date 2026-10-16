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
| MPEG systems | PAT, CAT, PMT, TSDT; registered MPEG descriptors and extension descriptors | Core fixture tests exercise PAT/PMT/CAT, multi-section PAT generation boundaries, and HEVC/ISO-639 descriptors in PMT. Generic registry decoding supplies additional table/descriptor fields. |
| DVB-S/S2/S2X, DVB-T/T2, DVB-C/C2 | Common DVB SI such as NIT, BAT, SDT, EIT, TDT/TOT; registered satellite, terrestrial, cable and generation-specific delivery-system descriptors | Pinned-compiler synthetic NIT tests assert DVB-S/S2, DVB-T/T2 and DVB-C delivery parameters plus official references. Special-descriptor fixtures also assert DVB AC-4, subtitles, application signaling and a PMT-discovered AIT with application/profile/object-carousel metadata. The optional recorded terrestrial sample remains additional evidence. S2X/C2 and untested parameter combinations remain SDK-level. The RF modes are not distinct table parsers. |
| ATSC transport-stream PSIP | MGT, TVCT/CVCT, ATSC_EIT, ETT, STT, RRT, DCCT, DCCSCT | Synthetic MGT/TVCT/STT/ATSC_EIT tests include a TVCT on an MGT-advertised nondefault PID, service-location components, captions, multiple-string text and content advisories. Other registered models are SDK-available. This does not claim ATSC 3.0 IP/ROUTE/MMT support. |
| ISDB | Shared MPEG/SI plus BIT, CDT, DCT, DLT, ERT, ITT, LDT, LIT, NBIT, PCAT, SDTT | Synthetic BIT/CDT/SDTT/LDT/NBIT/ITT API tests and an ISDB NIT assert terrestrial delivery, TS information, partial reception and system-management descriptors. Japan/Brazil character and regional interpretations must not be inferred from the word ISDB alone. |
| SCTE | Registered splice information and cable emergency alert models/descriptors | A PMT-discovered SCTE-35 PID test asserts time-signal PTS, segmentation fields/UPID and avail information. Other paths remain SDK-available; no full SCTE broadcast conformance claim. |
| DTMB | MPEG TS and recognized PSI/SI inside a provided TS can use the relevant common decoders | Pinned `Standards` enum has no DTMB member. No verified DTMB-specific signaling fixture or complete DTMB decoder claim. Official Chinese sources distinguish GB 20600 RF transmission from GB/T 28161 service information and GB/T 28160 EPG; see the DTMB audit below. Unknown signaling stays raw. |
| Operator / private / special | Registered private PDS descriptors, table-specific descriptors, extension descriptors; declared local extension fields | Scoped private descriptor fixture exists. Arbitrary unpublished syntax is not automatically knowable. No decryption, invented descriptor names, or blanket private-protocol support. |

## DTMB scope audit (official sources checked 2026-10-16)

The Chinese national standards portal lists separate documents:

- [GB 20600-2006](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=41F48525779777A75F0898B87E9BD24E): terrestrial transmission framing, channel coding and modulation.
- [GB/T 28161-2011](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=59E83CA701AEB4248E115BC043688FEC): digital-television service information.
- [GB/T 28160-2011](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=0AACD4802F1BB724F1140ABF21F4A48B): digital-television electronic programme guides.

The three official catalog entries were marked current on the audit date. This
check establishes document identities and their different subjects; it is **not**
a completed clause-by-clause implementation comparison. No normative PDF or
DTMB-specific conformance vector was imported into the project. The portal's
catalog text alone does not establish that all descriptor syntax, character sets,
reserved identifiers or receiver obligations equal DVB behavior.

For a demodulated TS from a DTMB service, the application's verified common MPEG
PSI and recognized SI decoders may be useful. Report the actual tables, descriptors
and raw bytes observed. Do not identify a transport stream's RF modulation from
PAT/PMT alone, silently label a DVB preset as DTMB, or claim that a common-decoder
pass validates GB 20600, GB/T 28161, GB/T 28160 or a broadcaster's private profile.
The remaining acceptance work is a documented source capture/profile, applicable
SI/text/EPG requirements and independent expected results, then positive and
malformed-input API regressions against those requirements. RF reception, AVS
media decoding and receiver conformance remain outside this PSI/SI editor.

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
standard flags are NONE, MPEG, DVB, SCTE, ATSC, ISDB, JAPAN and ABNT. Plain `isdb` selects common ISDB context only. The explicit profiles follow the
pinned `tstabcomp --help` definitions: `isdb-japan` uses ARIB-STD-B24 and JST;
`isdb-brazil` uses ISDB+ABNT, RAW-ISO-8859-15 and UTC-3. The core reports
`text_charset` and `time_reference` and copies them into native decoder contexts.
These settings interpret stream text/time; they do not identify the actual
broadcast country from RF data.

Auto mode is best-effort evidence accumulation, not a proof of standard identity.
Table ID 0xC7 means ATSC MGT or ISDB LDT; 0xC8 means ATSC TVCT or ISDB CDT.
An ID alone is insufficient. Source PID, explicit standard context, table shape,
and successful full-table deserialization matter. The SDK may prefer a registered
fixed-PID interpretation even with a different requested family: in a tested ATSC
context with explicitly included ISDB PIDs, CDT/LDT still decoded as ISDB. Thus
the context is a disambiguation preference, not a strict protocol rejection filter.
The pinned [registry lookup](https://github.com/tsduck/tsduck/blob/v3.39-3956/src/libtsduck/dtv/signalization/tsPSIRepository.cpp)
returns the first matching registered decoder, checking each entry's fixed PID
and standard flags in one pass. Static registration order can differ between
platform builds. With deliberately contradictory `isdb` context for the same
ATSC MGT/TVCT fixture, Linux produced generic raw fallback while the
[Windows baseline diagnostic](https://github.com/znbsf/ShowPsiSi/actions/runs/38973641571/job/117217715481)
produced the correct MGT/TVCT native fields. Both preserved the exact source bytes;
neither decoded the fixtures as unrelated ISDB LDT/CDT. The portable regression
accepts only those two safe outcomes and verifies raw bytes, required semantic
fields when decoded, and the explicit-family reference policy. This establishes
a bounded cross-platform dispatch difference, not broader Windows protocol
conformance. The reference index remains filtered to the explicitly selected
family, so contradictory `isdb` requests do not acquire ATSC reference links.

When input is ambiguous, choose the known standard explicitly and retain raw
bytes. Enabling every standards flag simultaneously cannot resolve a collision.

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

## Additional descriptor and transport regressions

`SPECIAL_FIXTURE_XML` in `tests/test_protocol_coverage.py` retains the exact source
XML for six additional binary fixtures. They were compiled by the pinned SDK;
the test suite embeds the resulting section bytes, so ordinary tests do not need
`tstabcomp`. When reproducing, use `--atsc` for the two ATSC sources, `--isdb` for
the ISDB NIT, and default compiler context for DVB AIT/PMT and SCTE-35. The ISO-639,
HEVC and application-signaling descriptors are asserted in their containing PMT;
AIT descriptors are asserted in AIT, preserving their table-specific namespace.

| Fixture | Measured application fields |
| --- | --- |
| DVB special PMT + AIT | HEVC profile/level; DVB AC-4 dialog flag; subtitle language/page ID; application type, name, profile version and object-carousel component tag; AIT PID discovered from PMT stream type 0x05 |
| ATSC TVCT + EIT | PCR/component PIDs and language; long channel name; digital caption service/language; EIT event ID/start/duration/title and content rating |
| ISDB NIT | Area code, guard interval, transmission mode, frequency, remote-control key, TS name, partial-reception service and broadcasting identifier |
| SCTE-35 | PMT stream type 0x86 discovers the splice PID; time-signal PTS, PTS adjustment, segmentation ID/duration/type, UPID bytes and avail ID |

The ISDB frequency is deliberately 473,000,000 Hz, exactly representable in this
fixture's 1/7-MHz field. The pinned SDK converts with integer division; arbitrary
Hz values may quantize. This is a signaling-field assertion, not RF tuning.

Separate hand-built sections and TS packetization exercise:

- Same-version current/next tables remain independently inspectable. Derived
  services, SDT history and snapshot exports use current sections only.
- Multi-section PAT association waits for the whole observed generation, including
  a 31-to-0 version transition; incomplete new sections do not borrow older ones.
- Reused 5-bit versions, including byte-identical repeated sections, cannot revive
  a sibling from before an intervening version when inspecting a partial table.
- A missing continuity counter in a spanning section discards the partial section;
  a following intact section recovers with correct start/end packet evidence.
- A byte-identical duplicate TS packet does not duplicate an observation or break
  assembly. A nonzero pointer field can complete one section and start another
  inside the same TS packet.
- ATSC and ISDB native table descriptors agree with flattened inspection while
  preserving the actual on-wire PDS value. Family-specific internal namespace
  selection is not evidence that a private-data-specifier appeared in the stream.

Independent snapshot-comparison regressions additionally verify within-packet
wire observation order when two versions complete in the same TS packet, exact
section-completion cutoffs, deterministic all/filtered pagination, the maximum
allowed offset, repeated-record evidence, duplicate EIT identities and rescheduled
events. A reused event ID with a different start time is removed+added; matching
IDs in different networks remain separate.

Canonical actual-TS service projection comes from SDT PID 0x11 only. An explicitly
included extra-PID SDT still has raw/native inspection and table differences, but
cannot shadow a canonical service by map ordering. Tests cover both arrival orders
and an extra-PID-only capture. This projection rule does not discard source bytes
or imply that a noncanonical placement conforms to DVB.

These tests verify specific cases, not all MPEG transport-error, discontinuity,
EIT segment, version-repetition or packet-loss patterns. In particular, EIT
schedule segment semantics and full registration-dependent codec isolation remain
separate work. There is no new generic edit/encode guarantee for these descriptors.

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

On 2026-10-16, **26 protocol API tests passed** against the rebuilt native core.
The original nine were expanded with seventeen descriptor, discovery,
packetization, generation and independent snapshot-comparison regressions. All six additional XML sources were
independently recompiled with TSDuck 3.39-3956 and matched their embedded section
bytes exactly.
Besides the table fixtures, these check auto-mode fixed-PID evidence, exact-native
or generic-raw handling of contradictory context, PDS isolation across descriptor
loops and files, unknown private byte retention, registry counts, and correct
standard links (including absence of an incorrect B10 link for CDT).
A registration descriptor is included in the private fixture, but a claim that
every registration-dependent private codec interpretation is covered would be
unjustified; that remains a targeted future regression area.
The optional official-reference index is 12,490 bytes on disk, with five sources,
191 descriptor associations and 26 table associations. These associations are
standard-level, not clause-level. CDT/SDTT have no B10 link because their SDK
headers cite ARIB STD-B21 instead.

## DVB delivery fixture source and measured fields

The following 114-byte NIT was compiled by TSDuck 3.39-3956 `tstabcomp`,
packetized, and decoded by the real core in `dvb` context. It covers selected
representative settings, not every delivery-system variant. Assertions check
frequency, symbol rate, modulation, bandwidth, S2 identifiers, and nested T2
cell frequency; all six descriptors carry the official ETSI standard-level link.
A separate test routes this NIT on PID 0x135 discovered from PAT program zero.

```xml
<tsduck>
<NIT network_id="77">
 <transport_stream transport_stream_id="1" original_network_id="2">
  <satellite_delivery_system_descriptor frequency="11538000000" orbital_position="19.2" west_east_flag="east" polarization="horizontal" modulation_system="DVB-S2" modulation_type="8PSK" symbol_rate="22000000" FEC_inner="2/3" roll_off="0.25"/>
  <S2_satellite_delivery_system_descriptor backwards_compatibility="false" scrambling_sequence_index="42" input_stream_identifier="7"/>
 </transport_stream>
 <transport_stream transport_stream_id="2" original_network_id="2">
  <terrestrial_delivery_system_descriptor centre_frequency="650000000" bandwidth="8MHz" priority="HP" no_time_slicing="true" no_MPE_FEC="true" constellation="64-QAM" hierarchy_information="0" code_rate_HP_stream="2/3" code_rate_LP_stream="1/2" guard_interval="1/8" transmission_mode="8k" other_frequency="false"/>
  <T2_delivery_system_descriptor plp_id="3" T2_system_id="9"><extension SISO_MISO="SISO" bandwidth="8MHz" guard_interval="1/128" transmission_mode="32k" other_frequency="false" tfs="false"><cell cell_id="12"><centre_frequency value="666000000"/></cell></extension></T2_delivery_system_descriptor>
 </transport_stream>
 <transport_stream transport_stream_id="3" original_network_id="2">
  <cable_delivery_system_descriptor frequency="450000000" FEC_outer="RS" modulation="256-QAM" symbol_rate="6900000" FEC_inner="none"/>
 </transport_stream>
 <transport_stream transport_stream_id="4" original_network_id="2"><satellite_delivery_system_descriptor frequency="11954000000" orbital_position="19.2" west_east_flag="east" polarization="horizontal" modulation_system="DVB-S" modulation_type="QPSK" symbol_rate="27500000" FEC_inner="3/4"/></transport_stream>
</NIT>
</tsduck>
```
