# Satellite parameter association

The C++ engine exposes read-only `lookup_satellite` and
`inspect.satellite_associations`. Qt and Tauri show the same candidate names,
raw parameters, source URLs, review dates, unknowns and expandable JSON evidence
in **Metadata**. The manual lookup accepts a nominal orbital position (0–180
degrees) and E/W. Select a section to open Metadata; the JSONL tool itself needs
no analysis.

## What a match means

Only nominal GEO orbital longitude is compared. Default tolerance is **zero**
(same nominal slot); the API can explicitly request up to one degree. E/W is
required, with 180 E and 180 W treated as the same longitude. No direction or
orbital slot is inferred from a frequency, network ID, service name or operator.
Every matching entry remains a **candidate**, including a sole match.
`confirmed_satellite` and `assignment_valid_at_capture` remain null.

The automatic path accepts only SDK-context-resolved ordinary
`satellite_delivery_system_descriptor` records. It checks descriptor size, BCD
digits, physical longitude bounds and nonzero frequency/symbol rate before
matching. A private extension's display name cannot enable this path. It preserves
the descriptor hex, native SDK attributes, decoded wire parameters (including
modulation, roll-off and FEC codes), section/PID/offset and the containing
TSID/ONID loop. Two transport loops or historical sections are never combined.
Invalid/unresolved descriptors stay in ordinary descriptor/raw evidence, with
no candidate inference; a resolved descriptor with invalid numeric parameters
has `invalid_parameters`.
ISDB uses the same descriptor tag with different modulation/FEC semantics; its
SDK fields and bytes are retained with `unsupported_delivery_system`, without
applying the DVB layout or returning candidates.

Delivery parameters are **advertised signalling**, not a measurement of the
received satellite. NIT-other and BAT can describe other transports. S2/S2X-only
descriptors do not supply a supported identity lookup. No RF demodulation,
ephemeris, footprint, historical assignment or reception verification is added.

Frequency (Hz), symbol rate (sym/s), polarization, modulation, roll-off and FEC
are retained. They are explicitly **not checked** against this directory:
it contains no transponder assignments. Consequently, an implausible but
well-formed frequency does not prove or exclude a spacecraft. Co-located names
are all returned; no probability or invented confidence ranking is assigned.

## Reference snapshot and maintenance

`references/satellites.json` is a small, deliberately incomplete offline
directory (22 records in revision 2026-10-18.1). It contains independently
transcribed factual names and nominal positions, not scraped page prose,
coverage images or third-party transponder listings:

- [AsiaSat fleet](https://www.asiasat.com/): AsiaSat 5/6/7/8/9.
- [SES neighborhoods](https://www.ses.com/solutions/media-broadcasters/reach-neighborhoods):
  ASTRA 1N/1P/3C/2E/2F/2G.
- [Eutelsat 13 East](https://www.eutelsat.com/satellite-network/GEO-fleet/eutelsat-13-east):
  HOTBIRD 13F/13G.
- [Eutelsat 5 West](https://www.eutelsat.com/satellite-network/GEO-fleet/eutelsat-5-west)
  and [7/8 West](https://www.eutelsat.com/satellite-network/GEO-fleet/eutelsat-7/8-west):
  EUTELSAT 5 WEST B/7 WEST A/8 WEST B.
- [APSTAR fleet](https://www.apstar.com/resource): APSTAR 5C/6C/6D/6E (MPSat-3)/7/9.

Source publisher identifies the source organization, not verified ownership.
Review dates are when the reference was checked, not publication dates or
guarantees of current operation. Capture-time validity is unknown. Names may
move, retire or describe leased payloads; an unlisted slot is not evidence that
no satellite exists. There is no background network request or automatic update.

To maintain the directory, review the primary references, amend factual records
and their provenance, and increment `revision`. Schema version 1 requires unique
IDs, names, signed longitude (-180–180), and a source with publisher, HTTPS URL
and review date. Keep assignment dates null unless explicitly supported.
The engine reads at most 1 MiB / 1,000 entries, validates the whole catalog before
using it, and returns its exact byte fingerprint (FNV-1a64, **not a security
hash**), revision, entry count and coverage limitation. Modified catalogs are
local reference data, not authenticated operator statements.

Missing/malformed catalogs produce `catalog_unavailable`, diagnostic evidence
and no candidates without breaking section inspection. Missing position/direction
produces `insufficient_parameters`; a valid but unlisted position produces
`no_catalog_match`. Invalid API types/ranges are rejected.

## Validation

`test_satellite_metadata.py` exercises real engine matching, wire parameters,
source offsets, co-location, sole candidates, E/W and 180-degree equivalence,
tolerance boundaries, private-name spoofing, invalid BCD, independent transport
loops, historical sections, source immutability, catalog failures and changed
fingerprints. It is part of the strict engine gates on Linux and Windows.
Qt's satellite-metadata interaction test and the browser suite operate the real
lookup controls against the native engine; native Windows WebView2 interaction
evidence is retained separately from browser/offscreen evidence.
