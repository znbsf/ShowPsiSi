# Broadcast protocol coverage and evidence

Satellite association adds an application-tested enrichment path for the ordinary
DVB satellite delivery descriptor: strict wire BCD/units, section/transport
provenance and nominal-slot **candidates** from an incomplete local catalog.
It does not establish spacecraft identity, transponder correctness, RF reception,
capture-date assignments or S2X identity support. See
[satellite association](SATELLITE_ASSOCIATION.md) for tests and source boundaries.

Service inspection now scopes EIT and component evidence by complete actual-SDT
ONID/TSID/SID identity and the selected capture cutoff. Conflicting actual
networks or PAT mappings withhold PMT association. AIT carriage is nonexclusive
and requires explicit DVB interpretation; no runtime application execution,
complete EPG schedule or on-air validity is inferred. The service/ES/EPG/AIT
source navigation is tested through the production core and browser UI; real
Qt service rendering is separately covered by full-application offscreen checks.

DSM-CC content inspection now exposes verified uncompressed module bytes,
bounded BIOP objects and exact-key bindings within one PID/download/announcement
epoch. DSI ObjectLocation is a declaration, not receiver activation. Incomplete
modules never yield fabricated bytes or a complete hash; damaged BIOP retains a
validated prefix and does not resolve partial targets as complete. Unknown
compression/profile/encoding stays explicit. Read-only Java class envelope and
names are interpreted without class loading, execution or bytecode verification.
The actual reconstructed M12/M13 content window chain is locally tested in the
browser and Qt offscreen; native desktop and output delivery remain separate.

Teletext now has a production PES-to-captured-page path with explicit DVB PID
signalling or manual PID, source/subpage/capture identity, exact original unit
fragments and 40-column display. Supported Latin Level 1 semantic cells include
colours, mosaics, double-height geometry and explicit visibility controls; C4
clear blanks retain no invented source. Enhancements, boxing and secondary
charsets remain partial/unsupported. A known-invalid-PAT fixture is tested only
with explicit PID 1068; its nine subtitle events match an independent SRT through
the core, browser display and Qt offscreen. This is not PSI discovery acceptance,
live timing or full Teletext receiver conformance.

PES/ES inspection now retains original TS fragments, header/timestamp metadata
and exact paged bytes. A private numeric stream type does not establish codec.
The optional external decoder is verified before execution and has independent
process/memory/output/time bounds. Real MPEG-2 frames and MPEG-audio PCM are
locally tested in both UIs; thumbnail pacing and mono resampling are explicitly
derived. Other advertised input formats remain unverified application paths.
Windows output control uses an exact preview token and an owned buffer; silence
checks establish API queue/stop behavior, not physical audibility. The accepted
single-I-frame remux is a positive pixel fixture; the whole original capture
is not accepted as clean video or original timing. FFmpeg is not bundled.

## What “supported” means

ShowPsiSi consumes MPEG transport-stream packets and independently imported local
DVB-I XML metadata. It does not tune, demodulate,
decrypt conditional-access content or certify a receiver. An optional external,
hash-pinned Windows decoder now provides bounded video-frame and PCM previews;
this is distinct from parsing support, device output and original A/V timing.
Three claims must remain separate:

1. **Verified application path:** a fixture or captured stream passed through the
   real JSONL core and its fields and source bytes were asserted by a test.
2. **SDK decoder registered:** the linked TSDuck registry contains a decoder.
   This does not establish that every field, malformed input, broadcaster variant,
   UI workflow, or edit/export operation was tested.
3. **Raw preservation / unknown:** bytes can be retained without a semantic
   decoder. A hex dump is not protocol conformance.

The current SDK is official **TSDuck 3.45-4798**, with C++20 and separate TSDuck and
TSCore libraries. On 2026-10-16 the running core reported **58 registered table
names and 347 registered descriptor names**. `capabilities.native_sdk` reported
3.45-4798 for the headers, TSDuck runtime and TSCore runtime, with version-symbol
checks enforced. Its installed XML model has **60 table entries** (including two
generic fallbacks) and **348 descriptor entries** (including the generic fallback).
These counts were measured from the binary and model, not assumed from source-file
counts. The old 3.39 baseline was 43/306 registered names. The live
`capabilities.native_registry` is authoritative for the actually linked build.
None of these counts is a conformance percentage.

## Standards and boundaries

| Family | Verified application behavior | SDK-only or excluded behavior |
| --- | --- | --- |
| MPEG systems | PAT/CAT/PMT, ISO-639 and HEVC descriptors; VANC registration inheritance/isolation; PDS-scoped AVS3 descriptor fields and guarded REGID ambiguity; DSM-CC DDB/DII module fields and block bytes | Additional registered descriptors remain individually unverified. No media decoding or general remux guarantee. |
| DVB-S/S2/S2X, DVB-T/T2, DVB-C/C2 | NIT delivery parameters for S/S2/T/T2/C; common SI; AC-4, subtitles, application signaling and PMT-discovered AIT; container_table, DFIT, MPE_FEC/MPE_IFEC fields and opaque payloads | S2X/C2 and untested parameter combinations remain SDK-level. Delivery descriptors do not prove RF support. Font URI, compression wrapper and FEC bytes are not fetched, decompressed or repaired. |
| ATSC transport-stream PSIP/data | MGT/TVCT/STT/EIT, including MGT-advertised PID discovery, captions and multiple strings; AEIT/AETT/DET/DST/LTST/NRT/SVCT synthetic fields | Other registered models are SDK-available. NRT fixture has private data but no resource entries; DST fixture has an application but no tap. No ATSC 3.0 IP/ROUTE/MMT claim. |
| ISDB | BIT/CDT/SDTT/LDT/NBIT/ITT; NIT terrestrial/TS/partial-reception descriptors; AMT IPv4/IPv6 mapping on PID 0x002E; advanced cable normal fields and opaque extension bytes | Other registered models and operator profiles remain unverified. Advanced-cable syntax has an upstream reconstruction caveat. Japan/Brazil text and time profiles must be selected explicitly. |
| SCTE | PMT-discovered SCTE35 time-signal/segmentation; extension tests add EAS fields/discovery, insert/schedule command variants, additional descriptors and exact export/reopen (see current support below) | No emergency receiver, splicer, encrypted cue decoding, SCTE35-2 or SCTE65 claim; complete normative text was not independently reviewed. |
| DTMB | Explicit `dtmb` context; ITU J.1041 DRM descriptor fields and exact license-data bytes; common SDT with explicitly signaled UTF-8 Chinese/Greek text; wrong-family and truncated-DRM fallback | No blanket GB/T 28161, GB/T 28160 or broadcaster-profile support; no GB 20600 RF test, DRM decryption, license access or AVS media decoding. |
| Operator / private | Astra SGT IDs/LCN/flags; scoped PDS and registration context; raw unknowns | Unpublished syntax is not inferred. SGT has no linked public standard in the index. No arbitrary private-protocol or generic edit/encode guarantee. |

Service and EPG lists remain convenience projections, primarily from common DVB
SI. A populated native table tree can coexist with empty Services/EPG projections;
the UIs explain that boundary. Inspect the native tree and original section bytes
for fields outside those projections.

## Identifier, encoding and multilingual metadata

The shared engine exposes nine reference namespaces: original network, network,
bouquet, CA system, private data specifier, MPEG registration, data broadcast,
platform and IEEE OUI. Names come from the installed TSDuck `.names` files,
including registry ranges. Each answer preserves the numeric value, correct hex
width, namespace, standards context, registry file/section, SDK version and an
explicit uncertainty statement. An unknown result is not proof of an unassigned
identifier; a label is not verification of current operator ownership. Auto or
inapplicable standards return `context_required` for regional namespaces. OUI and
MPEG registration are global; Japanese CA IDs use the separate ARIB registry.
No physical-satellite identity or SID/PID/TSID ownership is inferred.

Wire-string diagnostics cover service provider/name, short and extended event
text and items, network/bouquet name, component text, and multilingual network,
bouquet, service and component name descriptors encountered by the application's
descriptor walker. Explicit selectors, default input charset, available versus
declared bytes, decoded text, decoder failures and raw hex remain separate.
Decoder success is not proof that the broadcaster used the expected encoding.
ATSC multiple strings and native-only/private text loops retain SDK/raw evidence
but are not claimed as per-field diagnostic coverage. Charset implementations
outside the tested examples remain SDK capability, not application test evidence.

DVB-layout EIT projections retain all language variants, exact source descriptors,
extended item pairs, fragment numbers, missing/duplicate/conflicting fragments
and assembly scope. Only complete valid non-conflicting fragments within one
event loop are assembled; no merging across events, sections, versions or
languages. The compatibility title/text selects the first usable short
description in language-code order. UI language selection is presentation only.

`test_signal_metadata.py` exercises real wire fixtures: reference names/ranges,
unknown/context states, registration and CA descriptor provenance, explicit UTF-8
and default ISO-8859-1, invalid/truncated selectors, RAW input behavior, language
preservation, fragment reordering/items/duplicates/conflicts, event/version
isolation, provenance-only snapshot changes and private display-name isolation.
Both UI suites exercise the real engine with English/Chinese text and an
incomplete Chinese extended description. These are synthetic signalling fixtures,
not exhaustive charset, broadcaster or standards-conformance certification.

## DTMB scope and text (regional context)

The SDK now has a DTMB standards flag. The `dtmb` choice activates that context;
it does not select a Chinese character set or UTC+8. This follows the pinned
compiler's `--china` behavior. The fixture's `--default-charset UTF-8` is separate,
and the resulting service strings carry the on-wire 0x15 UTF-8 selectors.

`DTMB_DRM_descriptor` represents ITU J.1041 clause 7.2.1. Tests assert the four
format/encryption nibbles, opaque DRM bytes, native hierarchy, flat descriptor
and raw section. This is inspection of encryption signaling, not decryption.
A one-byte descriptor body is kept generic, and DVB context cannot label it as a
DTMB DRM descriptor. The reference index points to the actual ITU source.

The Chinese national standards portal separates:

- [GB 20600-2006](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=41F48525779777A75F0898B87E9BD24E): terrestrial framing, channel coding and modulation.
- [GB/T 28161-2011](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=59E83CA701AEB4248E115BC043688FEC): digital-television service information.
- [GB/T 28160-2011](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=0AACD4802F1BB724F1140ABF21F4A48B): digital-television electronic programme guides.

The catalog entries were checked on 2026-10-16. No clause-by-clause GB/T comparison
or independent DTMB conformance capture has been completed. PAT/PMT cannot identify
RF modulation. A common-SI decoder pass does not validate any of these standards.

Chinese, Greek and accented BMP text are asserted in explicitly encoded SDT and
ATSC multiple-string/fixed-UTF-16 fields. A separate compiler probe found that the
pinned SDT XML compiler dropped a supplementary-plane emoji; that probe is not
presented as successful text coverage. Supplementary broadcast-text fidelity,
GB2312/GB18030 defaults and complete Chinese EPG semantics remain unverified.
UTF-8 filesystem paths and service-edit byte limits have separate engine tests.

## Complete pinned XML table-model inventory

AEIT, AETT, AIT, AMT, ATSC_EIT, BAT, BIT, cable_emergency_alert_table, CAT,
CDT, CIT, container_table, CVCT, DCCSCT, DCCT, DCT, DET, DFIT,
discontinuity_information_table, DLT, DSMCC_download_data_message,
DSMCC_stream_descriptors_table, DSMCC_user_to_network_message, DST, EIT, ERT,
ETT, generic_long_table, generic_short_table, INT, ITT, LDT, LIT, LTST, MGT,
MPE_FEC, MPE_IFEC, NBIT, NIT, NRT, PAT, PCAT, PMT, RCT, RNT, RRT, RST,
SAT, SDT, SDTT, selection_information_table, SGT, splice_information_table,
STT, SVCT, TDT, TOT, TSDT, TVCT, UNT.

The 15 newly registered table names compared with 3.39 all have application
fixtures: AEIT, AETT, AMT, container_table, DET, DFIT,
DSMCC_download_data_message, DSMCC_user_to_network_message, DST, LTST, MPE_FEC,
MPE_IFEC, NRT, SGT and SVCT. This is one or a few representative paths for each,
not all branches. The complete descriptor inventory is exposed by the runtime
rather than duplicated as a stale hard-coded list.

## Context, collisions and private namespaces

`analyze.standards` accepts `auto`, `dvb`, `atsc`, `isdb`, `isdb-japan`,
`isdb-brazil`, `scte`, `dtmb` and the explicit `j94-system-b` extension. Pinned SDK flags include MPEG, DVB, SCTE, ATSC,
ISDB, JAPAN, ABNT and DTMB, plus `DVBONLY` for strict-DVB distinctions. The explicit `dvb` profile includes
that flag to prevent unrelated ISDB descriptor guesses; auto mode stays inferential.
`isdb-japan` selects ARIB-STD-B24 and JST; `isdb-brazil` selects ISDB+ABNT,
RAW-ISO-8859-15 and UTC-3. Plain `isdb` does not infer a regional profile.
The core reports `text_charset` and `time_reference` and propagates them into
native decoding. Settings are interpretation choices, not location detection.

Auto mode accumulates evidence and cannot prove standard identity. Table IDs
0xC7 and 0xC8 overlap between ATSC MGT/TVCT and ISDB LDT/CDT. PID, explicit
standards, complete table shape and successful deserialization all matter.
Context is not a strict rejection filter: fixed-PID/registered evidence can still
select a matching table in a contradictory requested family. The portable
regression accepts only the correct ATSC fields or generic raw fallback for its
contradictory fixture, never an unrelated ISDB table, and checks exact bytes.
Reference links remain filtered to the requested family. Historical Windows
registration-order evidence is retained in the old validation reports; it is not
proof that the upgraded Windows SDK has been tested interactively.

Descriptor interpretation also requires containing table ID, extension tag,
PDS and registration context. The application retains actual wire PDS (zero when
absent) and ordered `registration_ids` for flattened descriptors. Program-level
PMT registrations precede local component registrations. A component's local
registration must not leak into siblings or a later analysis. PDS is loop-local,
not inherited indiscriminately. Positive VANC and missing-registration tests
assert agreement between flattened descriptors and the native table hierarchy.
The legacy missing-PDS tests retain exact unknown private bytes and no false links.

Native JSON attribute keys remain lowercase for API compatibility. The companion
`tsduck_xml` retains the SDK's exact XML spelling, including uppercase acronyms.
A complete section/table generation is distinct from semantic validity:
`native_table_complete` can be true while a malformed payload uses generic raw
fallback. Tests truncate AMT, DET and DSM-CC DDB bodies while recomputing valid
section CRCs and assert this distinction.

### DSM-CC namespace guard

DII itself is an MPEG table, while the tested name and CRC module descriptors are
registered by upstream as DVB table-specific descriptors for TID 0x3B. Explicit
DVB context correctly decodes `dsmcc_name_descriptor` and `dsmcc_CRC32_descriptor`.
Without DVB context, upstream 3.45 can label CRC tag 0x05 as an unrelated MPEG
registration descriptor. The app instead emits generic raw module descriptors
and a `native_decode_warnings` entry in that bounded DII case. Tests exercise
`auto`, `atsc` and `isdb`, checking the native tree, XML, absent misleading links
and original bytes. It does not globally reinterpret every tag 0x05.

DDB/DII tests assert block/module identifiers, sizes, timing, transaction ID,
block bytes and the two DVB module descriptors. They do not establish carousel
file assembly, extraction, decompression, DSI object references or receiver behavior.

### ISDB advanced-cable implementation caveat

The official `tsISDBAdvancedCableDeliverySystemDescriptor.h` says its syntax was
reconstructed from a JCTEA STD-003 block diagram and needs real-signal testing.
The fixture tests that implementation's bit fields, exactly representable
450,000,000 Hz frequency and extension-1 opaque bytes (including compiler padding
to 88 bytes). It is not an independent interpretation of the full JCTEA standard.

## PID discovery and packet scope

- PAT discovers PMT PIDs; PAT program zero can advertise a nondefault network PID.
- ATSC PSIP has standard PIDs, and MGT entries advertise additional table PIDs.
- ISDB known PIDs include SDTT 0x23/0x28, BIT 0x24, NBIT/LDT 0x25, additional EIT
  0x26/0x27, CDT 0x29 and AMT 0x2E.
- `extra_pids` selects unadvertised/operator PIDs. Most new synthetic tables use
  this path; their mere registration does not imply automatic routing discovery.
- An ISDB IIP PID constant does not make IIP a generic PSI table; an arbitrary PES
  payload is not interpreted as SI merely because its PID was seen.
- Forward-only discovery cannot guarantee a table transmitted only before the
  PAT/MGT that advertises it. Repeated signaling or explicit PID inclusion avoids
  that fixture issue.

## Reproducible fixtures and measured paths

Legacy binary vectors in `tests/test_protocol_coverage.py` retain their exact
3.39-3956 compiler provenance and bytes. All 26 legacy tests still run on 3.45.
The six original special-fixture XML strings remain in the test module, and the
original table/delivery source XML is retained below; the SDK upgrade does not
rebrand their origin.

Added sources and hex vectors are in
[`tests/fixtures/tsduck345`](../tests/fixtures/tsduck345/README.md). Its manifest
records exact compiler identity/arguments, XML and binary hashes, PID, context and
CRC-correct bytes. Tests packetize the real bytes as TS and invoke the real core.
No SDK, generated TS/BIN or external standard PDF is checked in.

| Added fixture group | Asserted fields and evidence |
| --- | --- |
| DTMB PMT/SDT | DRM four format/encryption values, license bytes, Chinese/Greek provider/service strings and explicit UTF-8 selectors; wrong-context/truncated fallback |
| ISDB AMT/NIT | IPv4/IPv6 prefixes, service IDs and private data; advanced-cable PLP/carrier fields, extension bytes and padding |
| ATSC AEIT/AETT/LTST | Source/event/data IDs, MGT tag, ETM ID, starts/durations and multiple-string text |
| ATSC DET/DST/NRT/SVCT | Download timing/ID, application/private bytes, Chinese short name, channel and satellite-carrier parameters |
| DSM-CC DDB/DII | Module/block/transaction fields and bytes; correctly scoped name/CRC descriptors and conservative unknown-context output |
| DVB container/DFIT/FEC/iFEC | Container ID, wrapper bytes, font fields/URI, real-time parameters and FEC bytes |
| Astra SGT | Service/network IDs, channel number, new/visible flags and genre |
| MPEG VANC / AVS3 namespaces | VANC program inheritance and ordered local context; AVS3 real-PDS fields; missing identifiers, sibling/session isolation and guarded REGID-only ambiguity |

AVS3 fixtures assert profile/level, frame-rate, precision and colour fields with
an actual loop-local AVSV PDS. A sibling without PDS and a later analysis stay
generic. In the pinned SDK, a registered PrivateDual descriptor can be resolved
incorrectly through AVSV registration alone; that exact observed-registration
conflict is exposed as generic bytes plus a warning, consistently in flattened
JSON and table XML/tree. It is not manually relabeled as a successfully decoded
AVS3 descriptor. These are signaling tests, not AVS3 media decoding.

Legacy regressions continue to cover current/next separation, complete generation
assembly, version wrap/reuse, no borrowing stale sibling sections, packet loss and
recovery, byte-identical duplicate packets, pointer-field boundaries, private PDS,
extra-PID SDT isolation and precise snapshot-comparison cutoffs/order/pagination.
They do not cover all EIT segment, transport error or broadcaster-profile patterns.

## Validation and source references

On 2026-10-16 the upgraded Linux core passed **43 protocol tests**, with no skips,
including all 26 legacy tests. All **21 added XML sources** recompiled with the
actual official 3.45-4798 `tstabcomp` and matched their stored bytes/hashes exactly.
All 21 inputs also have API assertions. The Linux REGID-only AVS3 result is
warned raw fallback; the portable regression also accepts correctly resolved AVS3
with the expected fields, never an unrelated descriptor. Its real-PDS fixture is
strictly semantic. Compilation alone is never claimed as semantic validation.

Run the compiler reproduction and API checks using the commands in the fixture
README. Set `SHOWPSISI_CORE` if the binary is outside `build/bin`, and the normal
runtime library path when using an extracted SDK. Broader engine, MCP, Qt, Web,
Windows and packaging validation is recorded separately; this document does not
turn Linux API results into a Windows/macOS UI pass.

Pinned upstream evidence includes:

- [PSIRepository](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/signalization/tsPSIRepository.h): registry queries and context-aware lookup.
- [DescriptorContext](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/signalization/tsDescriptorContext.cpp): table, standard, PDS and ordered registration context.
- [DescriptorList](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/signalization/tsDescriptorList.cpp): list-local PDS and program-level registration inheritance.
- [DSM-CC table](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/tables/mpeg/tsDSMCCUserToNetworkMessage.cpp), [name descriptor](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/dvb/tsDSMCCNameDescriptor.cpp), [CRC descriptor](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/dvb/tsDSMCCCRC32Descriptor.cpp): why the namespace guard is necessary.
- [AVS3 video](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/avs/tsAVS3VideoDescriptor.cpp) and [SMPTE ancillary data](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/smpte/tsSMPTEAncDataDescriptor.cpp): private identifier registrations.

Public specification links live separately in `references/standards.json`.
A standard-level link is not a clause-compliance certificate or a claim that the
latest document edition is fully implemented. No PDFs are bundled and optional
reference browsing is outside parsing/packet analysis.

## Legacy 3.39 compiler source XML

These inputs generated the unchanged legacy binary vectors. They are retained as
provenance for the original compiler, while their API assertions now run on 3.45.

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

## Service overview metadata refinement (2026-10-17, development)

The service overview exposes the SDT service descriptor's numeric service type
and SDK DVB service-type name,
PAT-selected PMT PID, and audio/video PID lists classified by the linked SDK
using PMT stream types and descriptors. A missing service descriptor or PMT is
explicitly unknown, not a fabricated TV/audio classification. For example, private
PES stream type 0x06 is not automatically audio; descriptor evidence matters.

LCN projection currently supports SDK-resolved ordinary logical-channel-number
descriptors with an explicit private-data specifier and exact ONID/TSID/SID
association, plus the existing explicitly configured private extension. Candidate
records retain source evidence, namespace and visibility. Different channel numbers
or incompatible visibility produce a conflict, not an arbitrary winner. A missing
LCN is not replaced with the service ID. Regional/list/HD-simulcast policies remain
native inspection evidence and are not automatically selected by this projection.
This is not a claim of universal operator LCN support.

Arrival labels use packet positions unless the user supplies a transport bitrate;
in that case elapsed seconds are explicitly an estimate from that bitrate. No PCR
or wall-clock reconstruction is claimed. Logical table groups retain version,
current/next, extension and section evidence rather than grouping by PID alone.

## Current protocol extension support

This is bounded inspection support. SDK registration, complete section assembly,
semantic decoding, module reconstruction and receiver conformance are distinct.
The following table describes the current source, not a claim that every platform
has passed acceptance. Tests and commands are in [the test contract](PROTOCOL_TEST_PLAN.md)
and [tests/README.md](../tests/README.md).

| Feature | Implemented subset | Important limits |
| --- | --- | --- |
| NorDig within DVB | Namespace-backed LCD v1/v2 decoding, list/country alternatives, cross-transport list objects, exact source anchors and SDT simulcast declarations | No separate activation switch. Receiver list/country selection, ordering, replacement policy and media equivalence remain unsupported. Auto topology remains unresolved; graph adapters require explicit DVB. |
| SCTE18 / SCTE35 | EAS discovery and fields; PMT-discovered splice commands, supported descriptors, CRC/malformed/encrypted boundaries and export/reopen fixtures | No emergency receiver, splicer, encrypted cue decoding, SCTE35-2 or blanket SCTE65 support. Complete normative text was not independently field-reviewed. |
| AIT / UNT | Read-only application and update-notification cards, scoped alternatives, exact sources and bounded nonexclusive PAT/PMT-to-AIT carriage | No HbbTV runtime, URI fetching, application execution, device eligibility, firmware installation or cross-PID carousel resolution. |
| DSM-CC | Exact-section DII/DDB cards and bounded same-PID captured-module reconstruction; complete conflict-free supported modules receive hashes | No BIOP objects, filesystem export, decompression, cross-PID associations, image authenticity or receiver conformance. Incomplete/conflicting/resource-limited modules retain evidence without a hash. |
| ITU-T J.94 (2016) System B | Explicit context, NIT CDS/MMS, short-VCT VCM/DCM/ICM, NTT text, STT and descriptor-revised subtable queries | No synchronized network lineup, cross-subtable joins, clock-based activation, receiver/RF/POD actions or current SCTE65 equivalence. J.94 snapshot export remains unsupported. |
| Local DVB-I | Bounded TS 103 770 V1.2.1 XML import/query/inspect, independent Qt/Web sessions, semantic/source navigation, paging and original-byte/hash identity | No network retrieval, playback, TS association, full XSD validation or complete receiver behavior. Unsupported namespaces are raw-only; import has no asynchronous cancel API. |

### Evidence and source contracts

- NorDig interpretation requires the original private namespace. A private tag
  or merged SDK name alone cannot establish it. Lists retain conflicts and
  `selection_required`; a single captured list is not silently selected.
  [NorDig contract](NORDIG_TOPOLOGY.md).
- AIT/UNT and DSM-CC cards distinguish declared relationships, captured bytes and
  complete supported modules. Missing generations cannot borrow older evidence.
  [Application summaries](APPLICATION_SUMMARY_API.md),
  [carriage](APPLICATION_CARRIAGE.md), [DSM-CC](DSMCC_RECONSTRUCTION.md).
- J.94 uses the original short-section envelope with CRC. Absent MPEG long-header
  fields remain null/“not carried”; descriptor 0x93 revision evidence does not
  invent those fields. Query completeness covers declared subtable sections and
  record ranges, not the whole operational lineup.
  [Cable input](CABLE_OOB_INPUT_DESIGN.md), [cable API](CABLE_OOB_API.md).
- DVB-I has its own document revision, hash and XML locators, without invented
  PID/CRC/packet fields. DTD/external entities and XML-triggered fetching are
  rejected. [DVB-I API](DVB_I_API.md), [DVB-I workspaces](DVB_I_UI.md).
- Shared Qt/Web source navigation preserves revision, cutoff, byte range and
  origin on Back. Source-only changes do not redefine semantic snapshot diffs.
  [Protocol presentation](PROTOCOL_UI.md), [topology API](TOPOLOGY_API.md).

### Specification and fixture boundaries

NorDig uses Unified Requirements and Rules of Operation **3.2.2**. AIT and SSU
use **ETSI TS 102 809 V1.3.1** and **TS 102 006 V1.4.1**. Cable inspection uses
**ITU-T J.94 (10/2016) Annex B/F**, not an assumed SCTE65 cross-edition mapping.
DVB-I uses published **TS 103 770 V1.2.1**, separately from newer drafts.
The linked contracts retain official edition-specific references.

SCTE fixtures and application-signalling fixtures record their pinned TSDuck
compiler and input/output hashes. NorDig, carriage, J.94 and DVB-I tests also use
independently authored inputs. Compiler-derived vectors are not independent
conformance streams. No standards PDFs or private recordings are bundled.

Run strict engine/helper, Qt and browser tests from the same source revision.
Offscreen Qt and Chromium checks do not establish Windows/macOS desktop dialogs,
WebView2/GPU behavior, clean-machine installation or standard-wide conformance.
Exact-revision Windows packaging/runtime checks and clean-host acceptance remain
separate release gates; an earlier build's pass cannot certify a later candidate.


## Original packet and timing inspection (local 2026-10-26 increment)

Application-tested query_packet reads unchanged accepted source files and returns
188-byte TS plus actual 192-byte prefix / 204-byte parity framing bytes. PID
search is bounded and continuation-based. inspect.source_fragments verifies
first-occurrence packet/section coordinate mapping, including continuation
packets; unavailable mappings remain explicit. No media decoding is implied.
query_timing exposes bounded PCR observations, wrap-aware captured-TS bitrate
and trusted-interval duration; gaps, discontinuities, malformed/errored packets,
non-increasing clocks and intervals over ten seconds break measurement chains.
Continuity counters are an observed-window diagnostic, not full TR 101 290
conformance. Raw PCR samples cap at 4096; total counters remain scan-global.
Tests: test_packet_inspection.py, test_transport_timing.py and the original
section/source mapping regressions in test_unified_inspector.py. Native Windows
mouse/DPI acceptance remains distinct from real-engine component/browser and
Qt offscreen integration checks.
