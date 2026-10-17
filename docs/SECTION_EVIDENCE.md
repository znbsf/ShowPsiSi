# Section evidence contract

Additive JSON fields preserve legacy query/inspect behavior. Invalid records remain
in the engine and API; UI default hiding is a presentation filter, never deletion.
`valid` includes syntax/application validation, while `crc.status` independently
reports valid/invalid/not_present/unavailable. Correct CRC does not imply a valid
schema. CRC values are uppercase eight-digit wire/computed values without `0x`.
Long syntax, TOT and SCTE-35 carry CRC; declared-length mismatch is unavailable.
Known short TDT/RST/stuffing/DIT report no CRC; unfamiliar short syntax reports
unavailable rather than assuming the absence of an integrity field.

## Identity and coverage

Every table row is an exact raw-byte variant with repeat observations. `identity`
contains PID, TID, extension, version, current_next, section number and last section
number. `table_key` additionally retains SDT ONID and EIT TSID/ONID. Existing IDs
remain stable. A repeat increments observations, never section coverage.

`table_groups` separates table_key/version/current/last-section combinations.
`section_ids` references all observed raw variants in that group, including invalid
ones. `validity` is valid, mixed or all_invalid (all validation, not only CRC).
`observed_section_numbers`, `valid_section_numbers`, `invalid_section_numbers`,
`missing_section_numbers`, and `missing_valid_section_numbers` describe observations
through the query cutoff, potentially across a reused five-bit version.

Only `selected_section_ids`, `selected_missing_section_numbers`, and
`selected_complete` use generation-safe snapshot selection, excluding siblings
before a version/last-section transition. Capture-wide version coverage is not a
claim of coherent simultaneous assembly. Malformed header numbers are untrusted
observed evidence, not instructions to select a generation.

EIT schedule has legal holes between eight-section segments. Its
`expected_section_numbers` and missing lists use only valid observed sections'
`segment_last_section_number`, constrained to that section's segment and last
section. Unobserved segments remain unknown, indicated by
`schedule_unobserved_segments_unknown`. This is not full EPG completeness or proof
that every advertised table was broadcast. Existing `selected_complete` describes
strict native BinaryTable assembly, not EIT schedule completeness. Each EIT row
also includes `segment_last_section_number` and `last_table_id`.

DSM-CC transaction/module/block reassembly is outside this contract. Inspection
reports this limitation; generic long-section numbering does not establish an
assembled downloadable object.

## Arrival distribution

Row and group `distribution` have up to 32 bins with explicit inclusive packet
ranges, observation and invalid counts, first/last start-packet, and min/max/mean
start-packet gaps. Only occurrences completed by the cutoff count, including
multiple arrivals in one packet. `last_packet` in the legacy summary remains the
last completion-packet; distribution uses start-packets consistently.

These are capture packet positions, not RF reception wall-clock or PCR-derived
time. `pcr_derived` is false. Seconds are null unless a bitrate is supplied; the
conversion uses 188-byte transport packets, excluding 192-byte framing prefixes
or 204-byte parity. Arrival aggregation streams per-variant sorted observations with a k-way merge,
using O(raw-variant count) temporary memory, with cooperative cancellation checks
every 256 observations. It does not copy/sort all repeat occurrences.

No PCR interpolation, clock selection or wrap/discontinuity
handling is implemented. A histogram allows sparse/dense inspection without
inventing a normative repetition-rate threshold. Query-global legacy density and
counters retain their original whole-scan scope.

## Inspection and decoder status

`raw_hex`, `fields`, `descriptors`, `services`, `events` refer to the selected exact
section. `section_native_text` uses TSDuck `TablesDisplay::displaySection` on that
original Section without renumbering, CRC changes or invented siblings. Guarded
namespace text is suppressed; invalid records remain raw-only. This SDK display
is not a second wire representation.

`native_table_sources` lists the selected generation's exact section summaries.
`merged` wraps legacy native_table/XML with complete/source_ids/scope. An incomplete
or superseded inspection never claims a complete merge. Source IDs support sibling
navigation; individual bytes always remain available through inspect.

`table_decoder_registered` uses the contextual SDK registry.
`table_decode_category` distinguishes decoded, registered_decoder_fallback,
unknown_or_unsupported, incomplete_or_superseded and invalid_evidence.
Descriptor `decode_status` distinguishes decoded, context_guarded, parse_failure,
and unknown_or_unsupported. A registered descriptor factory plus failed native
conversion is parse_failure. Generic data alone cannot distinguish unpublished
private syntax from a known specification unsupported by this SDK. `raw` is
preserved in every case. Flat application descriptor projections cover selected
loops, not every table descriptor loop; SDK native trees/text may contain more.

## Tests and scope

`tests/test_section_evidence.py` verifies repeats versus missing sections, mixed
and all-invalid groups, exact CRC values/raw retention, edit rejection, snapshot
cutoffs, merged sibling IDs, reused versions, current/next/PID separation,
explicit supplied-bitrate timing, TDT without CRC, and EIT schedule segment holes.
Additional cases cover superseded merged-output provenance, same-packet zero
gaps, a 20,000-repeat burst, and valid/corrupt short TOT CRCs (the section demux
alone does not check those short-section CRCs).
It is included in the strict native engine runner. These are synthetic fixtures;
real French UHF22 has no CRC errors and cannot validate a bad-CRC path.

## Workbench presentation and regression evidence (2026-10-17)

Both frontends retain the raw-record model and use distinct fixed colors and
symbols for PAT, PMT, CAT, NIT, SDT, BAT, EIT, TDT, TOT, AIT and DSM-CC. Each of
these eleven identities has its own foreground token and glyph in both UIs.
Unknown/other signalling uses one neutral token, never a randomized name hash.
Visible type names and semantic tooltips remain; colors do not replace labels. CRC-invalid
records are hidden by default in Tables, with an explicit count/reveal control;
structural failures with a good CRC are not silently removed. An all-bad source
must not auto-select a hidden bad record. Issues can still open exact bad evidence.

The inspector exposes PID, TID, version, section/last-section and transmitted CRC
without opening XML, plus first/last packet and arrival density. A packet position
is not a wall-clock timestamp. Compact Qt retains first/last and the complete
expandable arrival data, while omitting the mini histogram to preserve field space.
The per-section selector keeps original bytes distinct from the native merged
projection. A superseded/incomplete selection cannot show legacy fallback XML as
a completed merged table. Candidate sources are explicitly labelled when no
complete merged projection exists.

Qt's pointer-disclosure bug was an unqualified `toggle(path)` inside an
`ItemDelegate`: its inherited button `toggle()` shadowed the window's tree
function. Calls are now explicitly `win.toggle(path)`. The new regression
actually scrolls virtualized rows into view before clicking, verifies mouse
fold/unfold and Left/Right child navigation, and tests Expand/Collapse all. A
successful input-injection return is not treated as proof of a changed tree.

Descriptor rows identify native decode, configured extension, or unresolved raw
semantics and expose native warnings and registration context. Empty application
field maps are not labelled as successful decoded fields. Native descriptor
children are expanded where useful. The audit count is explicitly scoped to
application-indexed loops; native-only loops may contain further descriptors.
Qt also exposes the SDK's exact original-section text in **Decoded**, subject to
the same namespace safety guard. This is not an inferred semantic decoder.

Qt XML remains a selectable `PlainText` document with `QSyntaxHighlighter`
formatting. It never becomes interpreted HTML. The regression checks actual text
layout format ranges and preserves the existing literal-untrusted-text tests.
Completion JSON is now committed through `QSaveFile`, after required captures.

Local frozen-source verification:

- **35 Qt UI/result tests passed**, including three new section-workbench cases:
  mixed CRC + multi-section evidence, superseded selection at an explicit later
  cutoff and historical recovery, and an all-CRC-bad source with a missing sibling.
- The compact comparison retains the unchanged **90px** minimum field-tree
  assertion; its final Linux rendered height is **102px** at 1000×680. Earlier
  0px/88px failures prompted layout changes, not a reduced acceptance threshold.
- The three authored-token contrast tests pass, including a new cross-frontend
  fixed-type identity/color/glyph regression. The eleven fixed colors measure
  at least **5.56:1** across the six checked native/Web text backgrounds. This is
  bounded contrast sampling, not full accessibility certification.
- Source and binary SHA-256 values are checked again after the suite in ignored
  `artifacts/section-workbench/qt-source-{freeze.sha256,verified.txt}`.
- Real restored UHF22 and a synthetic two-section SDT were captured before changes.
  Final captures below are from the compiled application and real engine, not
  a drawing or fabricated UI state.

Retained screenshots:

- [Real UHF22 workbench, 1440×900](images/qt-section-workbench.png)
- [Real UHF22 compact workbench, 1000×680](images/qt-section-compact.png)
- [Synthetic section provenance and CRC evidence](images/qt-section-provenance.png)
- [Selectable syntax-colored XML](images/qt-section-xml.png)

These Qt captures use Linux's offscreen/software backend. They do not establish
native Windows dialogs, GPU behavior, screen-reader support or a Windows package.
Browser validation remains separate from native Tauri/WebView2 acceptance.

## Web workbench verification

Final sandbox-enabled Chromium/native-engine validation passed **28/28 tests**,
with no skips (37.534 seconds). This includes the real synthetic mixed/complete,
missing-sibling and all-invalid groups; CRC visibility counts and all-invalid
initial selection; arrival bins; explicit section/merged scopes; XML text
preservation and syntax spans; repeated pointer/keyboard folding; each table
group's keyboard entry; and superseded-section inspection at an explicit later
cutoff. The superseded case must return authoritative `merged` null data; Web
never substitutes the older compatibility XML/tree fields for that result.

Closed structure branches are lazily materialized so their hidden descendants
cannot exhaust the displayed-node budget. PAT, PMT, CAT, NIT, SDT, BAT, EIT, TDT, TOT, AIT and DSM-CC each have a fixed
distinct type color and glyph, shared with Qt; semantic-family explanations remain
in tooltips. Unknown types use neutral gray and a circle. The additional browser
regression checks all 11 computed colors and glyphs are distinct and retain text
labels, including the inspector heading where an older span rule previously
overrode the badge color. Table-tree group summaries distinguish observed
coverage from generation-safe selected completeness. Bad-CRC visibility does not
hide unrelated structural faults or imply an absent section was received.

A visual check found that expanded sibling provenance squeezed the compact tree
to zero height despite passing functional tests. The inspector now scrolls when
necessary and retains a **140px minimum working tree**. Final actual rendered
heights were **305px at 1440×900** and **140px at 1000×680 and 520×1000** for both
UHF22 and the synthetic source. New assertions cover the compact height, scrolling
reachability and lack of document-wide horizontal overflow. Single-section,
single-variant records omit the redundant sibling chooser.

Real UHF22, synthetic mixed-section evidence, table groups and XML captures were
visually inspected. Baseline frontend captures were reconstructed separately from
HEAD web assets, with the real current engine; they are not claimed as captures
taken chronologically before editing. The optional
`tests/capture_section_workbench.py` reproduces the final captures, or accepts
`SHOWPSISI_BASELINE_WEB` pointing to separately exported baseline assets.

- [Real UHF22 web workbench, 1440×900](images/web-section-workbench.png)
- [Real UHF22 compact web workbench, 1000×680](images/web-section-compact.png)
- [Synthetic mixed CRC and sibling provenance](images/web-section-provenance.png)
- [Escaped, selectable syntax-colored merged XML](images/web-section-xml.png)

Ignored evidence is under `artifacts/section-workbench/web/`: final suite/capture
logs and terminal exit files, baseline/final viewport metrics and screenshots,
and the run-start `final-inputs.sha256` manifest. All web assets and both native
core binaries matched that manifest after the final suite and captures. The
initial superseded test accidentally used implicit last-observation semantics;
it was corrected to an explicit later cutoff rather than weakening the engine
contract. Earlier logs are retained separately. No validation-owned browser,
bridge, or core process remained after completion.

These are Chromium web-frontend checks on Linux, **not native Tauri/WebView2
interaction**. Native Tauri embedding, Windows/macOS interaction, actual screen
readers, and all-state accessibility remain separate acceptance boundaries.
