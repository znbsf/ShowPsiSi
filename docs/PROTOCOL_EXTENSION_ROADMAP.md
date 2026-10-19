# Protocol and operator-extension roadmap

Research checkpoint: 2026-10-19. This is a plan, not newly implemented coverage.
Current application and pinned TSDuck 3.45-4798 capabilities were inspected.
The current Windows release and the separate semantic-topology work remain distinct.

## Classification

A public specification, a private descriptor tag, an open-source implementation,
a redistribution license, and operator receiver certification are different facts.
Do not label an operator system an open standard merely because a parser exists.
Do not count an SDK registration as a tested application feature.

## Suggested order

| Priority | Candidate | Existing state | Actual proposed work |
|---|---|---|---|
| 1 | NorDig v2 / regional lists / HD simulcast | Ordinary EACEM/NorDig v1/DTG/Australian LCN candidates already exist; SDK has additional decoders | Preserve country/list/region and alternative-HD relationships; explicit selection and conflicts, no automatic flattening |
| 2 | SCTE-18 and additional SCTE-35 cases | EAS decoders registered; time_signal/segmentation and some35 discovery already tested | Alert objects/region/validity/priority; splice_insert/cancel/component/timing cases and source-linked views |
| 3 | AIT/HbbTV, DSM-CC, SSU/UNT | PMT→AIT and DII/DDB have partial application tests; no complete carousel object pipeline | Application summaries, bounded module/object reconstruction, update-notification relations; never execute applications or firmware automatically |
| 4 | SCTE-65 out-of-band SI | No dedicated current adapter established | Confirm actual input framing, add dedicated decode/identity namespace and service mapping with normative and real samples |
| Experimental | M7 Fastscan | No FNT/FST/ONT in current registry; public reference implementation exists | Separate operator profile with discovery/namespace rules and FNT/FST/ONT relationships, only after acceptable protocol basis and samples |
| Await evidence | Türksat TKGS | Official system and receiver certification known; complete public wire specification/license not established | Preserve unknown raw evidence; do not promise decoding until usable specification/sample basis exists |
| Separate input adapter | DVB-I | HTTP/XML service discovery is outside the TS section input | Import into shared semantic objects without pretending it is MPEG-TS SI |

Further candidates include TV-Anytime content-reference relationships, additional
ATSC RRT/DCCT/DCCSCT coverage and ISDB auxiliary signalling integration. Many
AEIT/AETT/DET/DST/NRT/ATSC SVCT and ISDB AMT/BIT/CDT/SDTT/LDT/NBIT/ITT paths already
have varying fixture coverage; inspect the existing matrix before creating work.
ATSC A/81 Satellite VCT is not SCTE-65 Short-form VCT despite the acronym SVCT.
DTMB physical-layer support and a decoder profile do not establish complete
Chinese SI/EPG conformance. ATSC3/MMT/ROUTE/DAB/DRM need separate input architectures.

## Tests and safety

- Preserve standard/profile/PDS/registration context, raw bytes and exact provenance.
- Test IDs reused across ONID/TSID, multiple lists, incomplete sections, version
  changes, malformed input and conflicting claims; no guessed channel identity.
- Bound carousel sizes, decompression, filenames and traversal; extracted content
  is data, not permission to execute or install anything.
- M7 reference code is GPL-3.0-or-later. Do not copy it into this MIT repository
  as if unrestricted. Any implementation/reuse must undergo a specific license
  and provenance review; an independently authored parser still needs reliable
  format evidence and samples.
- TKGS availability was not proven; absence of a public spec does not prove the
  signalling is encrypted or impossible to parse.

## Primary and implementation sources

- NorDig: https://nordig.org/wp-content/uploads/2016/04/NorDig-Unified_ver_2.5.1.pdf
  (public researched edition; current SDK cites3.1.1 §12.2.9.3, so verify target edition).
- SCTE public standards policy: https://www.scte.org/standards/
- SCTE18: https://account.scte.org/standards/library/catalog/scte-18-emergency-alert-messaging-for-cable/
- SCTE35-1: https://account.scte.org/standards/library/catalog/scte-35-1-digital-program-insertion-cueing-message-part-1-legacy-splice-based-and-time-based-signaling/
  Current SDK's older35 implementation does not establish newer35-2 coverage.
- SCTE65: https://account.scte.org/standards/library/catalog/scte-65-service-information-delivered-out-of-band-for-digital-cable-television/
  Catalog description verified; full detail retrieval encountered403 in this pass.
- AIT/application signalling: https://www.etsi.org/deliver/etsi_ts/102800_102899/102809/01.03.01_60/ts_102809v010301p.pdf
- SSU: https://www.etsi.org/deliver/etsi_ts/102000_102099/102006/01.04.01_60/ts_102006v010401p.pdf
- HbbTV: https://www.hbbtv.org/resource-library/specifications/
- M7/Skylink official certification reference: https://www.skylink.sk/doc/um_prijimac_file/tesla_te-3000_pdf-139.PDF
- M7 reference implementation: https://github.com/EricBerendsen/dvbinspector/tree/master/src/main/java/nl/digitalekabeltelevisie/data/mpeg/psi/m7fastscan
- TKGS: https://www.turksat.com.tr/en/satellite/video-services/tkgs
- Türksat certification/brand statement: https://turksat.com.tr/haberler/turksat-asden-kamuoyuna-aciklama-2
- DVB-I: https://dvb.org/?standard=service-discovery-and-programme-metadata-for-dvb-i
- DTG D-Book: https://dtg.org.uk/d-book/ (download routes through Member Hub;
  availability/updates subject to access terms, not assumed anonymous/open).

This research did not rerun the entire application test suite or establish
royalty-free commercial use of every referenced standard.
