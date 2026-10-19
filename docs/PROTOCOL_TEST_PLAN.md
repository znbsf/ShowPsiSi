# Protocol implementation and test iteration plan

Checkpoint: 2026-10-19. This plan concerns inspection and evidence, not RF reception,
media playback, HbbTV execution, firmware installation or standards certification.
The measured starting matrix is in [PROTOCOL_COVERAGE.md](PROTOCOL_COVERAGE.md).
Keep this feature branch separate from the current release candidate until its
own combined gates pass. No phase completion follows merely from an SDK decoder.

## Repeatable increment loop

1. **Select one bounded claim.** Record standard edition and relevant clauses,
   input framing, discovery rules, identifiers, interpretation context and what
   remains unknown. Verify official publication status; separate drafts. If only
   a catalogue/preview is available, scope the claim to pinned SDK behaviour or
   defer new syntax. Do not substitute unofficial reconstructed wire syntax.
2. **Establish evidence before implementation.** Add a small independently authored
   wire fixture or a pinned source/XML + compiler + byte/hash manifest. Record
   provenance, redistribution terms and expected fields manually. Keep a failing
   real-core regression for an actual gap. Compiler output agreeing with itself
   does not establish normative conformance.
3. **Implement in the shared engine.** Keep parsing, validity, source identity and
   projection separate. UI code must not decode binary formats. Reuse tested SDK
   types, but keep unsupported/ambiguous and malformed results explicit. Never
   replace original bytes with a pretty-printed reconstruction.
4. **Exercise positive and negative paths.** Assert fields and exact sources,
   context collisions, reassembly/generation boundaries, resource limits and
   error recovery in the same process. Verify additive API shapes and that stale
   requests cannot attach new-session source labels to old evidence.
5. **Check semantic consumers.** Add source-linked projections only after parser
   facts are stable. Test query/cutoff/diff/topology, MCP and Qt/Web workflows.
   Distinguish source-only changes from semantic changes. Test all selected
   filters/pages and state replacement rather than only a screenshot.
6. **Review and combine.** Another reviewer checks source/spec mapping, independent
   expected values and failure contracts. Rebuild production and gated-test core
   from the combined exact revision. Run strict regressions and native UI gates;
   unexpected skips fail. Retain source SHA, SDK versions, log and summary JSON.
7. **Promote one claim.** Update the matrix with tested files, platform and evidence;
   retain remaining exclusions. If any gate fails, preserve its artifact, fix
   the cause, rerun affected and combined gates. Do not hide failure by relaxing
   expected semantics or reusing an older green artifact.

Each pass ends with implemented claim + tests + evidence + remaining boundary.
Proceed to the next dependency-ready slice; do not declare an entire standard
complete because one representative table decodes.

## Input and identity contracts

| Input | Current accepted boundary | Required distinction / test |
| --- | --- | --- |
| TS packets | Existing 188/192/204 framing; actual PSI/SI PID/section evidence | PMT/MGT/fixed-PID discovery and explicit extra PIDs are different sources. Lost packet/sync and wrong stride cannot invent a complete table. |
| NorDig | NIT transport-loop extension inside DVB; earlier wire PDS 0x29 | Automatically decode with DVB; no NorDig enabling checkbox. Use ONID + TSID + SID + list ID, retain country/name and ambiguity. No inference from frequency, display name or descriptor tag alone. |
| SCTE18/35 | Sections already carried in TS; established PID or PMT discovery | An EAS section on extra PID 0x1FFC is not a CableCARD/OOB adapter. Preserve 33-bit PTS and adjustment separately from UTC or a computed timeline. |
| DSM-CC | DII/DDB sections already demultiplexed from TS | Section completeness, module completeness and object completeness are separate states. Download/transaction/module/version/block identity cannot collapse into PID alone. |
| AIT / UNT | Discovered or explicitly selected TS sections | Signalled HTTP/carousel/firmware paths are data. Do not fetch, execute or install them as a side effect of analysis or source navigation. |
| SCTE65 | No dedicated accepted OOB input contract yet | Establish framing, routing/namespace, reference clock and table syntax before decoder claims. ATSC A/81 Satellite VCT is unrelated despite the shared SVCT acronym. |
| DVB-I | Planned local XML first, optional HTTP later | Use document hash/revision + namespace-expanded XML locator. Never fabricate TS PID, CRC, packet offset or PAT/PMT for an XML element. |

A raw BIN section export contains no universal PID context. Its existence does
not establish an automatic general BIN input adapter. New input types require
an explicit API/UX choice, revision/source model and failure-isolation tests.

## Phase A: bounded decoder evidence and NorDig lists

**Current increment:** `test_nordig.py` (20), `test_scte_extensions.py` (18),
`test_application_signalling.py` (7), plus existing protocol/service suites.

- NorDig v1/v2 activate through the existing DVB/default-auto path. Check real,
  absent, wrong, late and previous-loop PDS; contradictory family context must
  not invent private namespace evidence. Keep the current auto-inference contract.
- Retain list ID/name/country, SID/LCN/visibility, exact source and wire offsets.
  Assert UTF-8 selector, 23-byte names, country group, 10-bit vs v1 14-bit values,
  hidden/reserved allocations and maximum 255-byte descriptor failure. Malformed
  nested lengths must never produce a partial successful projection.
- Check matching ONID/TSID/SID, NIT-other, current/next, multiple lists, duplicates,
  conflicting same-ID definitions, incomplete/new/reused versions and CRC loss.
  Redundant sources or list order do not become semantic diffs.
- Preserve v1 candidate evidence when v2 is present, but do not silently choose
  v1 or flatten v2 into a single displayed LCN. Receiver country/list selection
  is a later UX policy even if only one list was observed.
- SCTE18/35 assertions follow the pinned SDK representation with exact bytes;
  malformed/CRC/encrypted cases remain distinct. Reproduce all 11 vectors with
  the pinned official compiler; assert valid unchanged BIN and TS export/reopen.
- AIT HTTP and UNT add discovery/fields/raw/reference evidence plus every payload
  truncation boundary with repaired outer length/CRC. Native table assembly
  completeness is not semantic decoder success.

**Next NorDig slice:** network/list semantic objects and explicit optional list
choice shared by both UIs, followed by HD-simulcast relationships. Verify same
list ID across multiple TS and ONIDs, duplicate SID across descriptors, global
list-name/country inconsistencies, v1/v2 list membership differences, source
replacement and selection invalidation. Apply receiver-priority rules only as
an explicitly named policy with tests; inspection remains available by default.
Use NorDig Test Plan 14:12/13/14/23 as a requirements checklist, not a claim that
its externally supplied receiver conformance vectors were run.

## Phase B: source-linked application, alert and update relations

**Dependencies:** Phase A parser evidence and shared revision-bound source locators.

- AIT: application organisation/ID/type, profile/control code, names/languages,
  common vs local descriptors, transport labels and location relationships.
  Missing/reused/ambiguous labels remain unresolved; test more than one app and
  protocol per table, ordering, incomplete generations and app disappearance.
- SSU: UNT target/compatibility selectors, OUI/version, association/module and
  notification/transport relationships. Unknown private selectors remain opaque.
  Test multiple OUIs, nonmatching devices, impossible ranges, conflicting updates,
  timestamps and stale versions without claiming firmware suitability.
- SCTE18: explicit alert/event objects with source-linked geography/priority/
  exceptions and declared validity. Unknown clocks stay unknown. Do not promote
  signalled emergency text into an application-generated real-world warning.
- SCTE35: source-linked command/segmentation objects; immediate/cancel/unspecified
  time and 33-bit wrap cannot be silently normalized to one timestamp. Unknown
  commands/descriptors, inconsistent declared lengths, reserved fields and
  overlapping/cancelled events need explicit tests before summary claims.

**UI gate:** select each summary object, reach its native node and exact bytes,
then change cutoff/filter/file and verify the old locator is rejected. Both Qt
and Web must show ambiguous/incomplete/unknown states, keyboard access and
plain-text hostile metadata. Use real C++ data, not UI-only fixture models.

## Phase C: bounded DSM-CC module reconstruction

**Dependencies:** verify edition/profile mapping against accessible normative
DSM-CC/DVB text, then DII/DDB identity fixtures. No BIOP export in this slice.

- Model announced size/block size/version, expected block count, received unique
  blocks, missing ranges and completeness separately. Keep all conflicts with
  originating section/packet evidence. A DDB alone cannot certify a module.
- Reordered blocks, identical duplicates, conflicting duplicates, missing first/
  middle/final blocks, truncated/overlong final block, zero block size, out-of-range
  block index, contradictory DII, transaction/download-ID and module/version reuse,
  wrap, simultaneous carousels/PIDs and analysis replacement.
- Reject overflow before allocation; sparse huge IDs must not allocate dense
  arrays. Do not preallocate declared module size. Cap outstanding sessions,
  total unique blocks, bytes, diagnostics and retained history; exercise cap−1,
  cap and cap+1. Cancellation must leave an inspectable incomplete result.
- Proposed first limits, to ratify before coding: 16 MiB/module, 64 MiB assembled
  bytes/session, 256 active modules, 65,536 stored blocks and 1,000 diagnostics.
  These are engineering defaults, not normative protocol maxima. Hitting a limit
  yields `resource_limited`, never silent truncation or a complete object.
- Record measured wall time/peak memory for fixed adversarial fixtures and prove
  bounds on Linux/Windows. A timeout killing the process is not graceful handling.

**Exit gate:** module bytes/hash match independent expected data; no cross-version
or cross-source borrowing; malformed input and repeated failure do not poison the
next valid scan. No decompress, extract or execute action is implied.

## Phase D: DSM-CC objects and safe export

**Dependencies:** reliable modules plus normative BIOP/object/profile coverage.

- Parse directories, object keys, bindings and references with explicit unresolved
  cycles/missing objects; distinguish a name collision from identity equality.
  Unknown BIOP kinds remain raw evidence. Never interpret module bytes as code.
- Decompression needs an allowlisted algorithm, streamed input/output accounting,
  maximum output and expansion ratio; test bombs, nested wrappers, corruption,
  wrong checksums, truncated streams and cancellation. Proposed first budget:
  64 MiB total output and 100:1 ratio, ratified and documented before enabling.
- Export only after explicit user request to a chosen new directory. Reject
  traversal, absolute/UNC/device paths, alternate data streams, Windows reserved
  names, symlink/reparse escapes, case/Unicode collisions and overwrite ambiguity.
  Test destination mutation/races and partial-write cleanup. Do not execute
  applications, play alert assets or install firmware after extraction.
- Save a manifest linking each exported file/hash to modules/sections and capture
  revision. Test failure and cancellation without reporting success or erasing
  unrelated destination files. Closing the app must respect active export work.

## Phase E: SCTE65 evidence acquisition and adapter

The official full ITU J.94 (10/2016) Annex B was obtained during this iteration;
see [CABLE_OOB_INPUT_DESIGN.md](CABLE_OOB_INPUT_DESIGN.md) for its source/hash and
edition boundary. Begin a separately named System B section adapter using that
syntax. It does not establish current SCTE65 equivalence. For the latter obtain
its complete normative text and a provenance-tracked realistic input. Official
SCTE catalogue/preview scope alone is insufficient. Identify CDS/MMS NIT, NTT,
short-VCT subtypes and time/linkage identities separately from DVB/ATSC tables.

The first J.94 increment now implements section-level CDS/MMS and VCM/DCM/ICM
with 20 real-core tests; it retains each exact variant, exposes absent long-header
fields as null, leaves map completeness false and refuses snapshot export. The
subsequent NTT/STT section-only slice is recorded below; cross-section maps remain
a separate future slice. Continue adding
independently expected field vectors, collisions, invalid length/CRC,
version and source-ID reuse, incomplete map updates and OOB-to-TS encapsulation
cases. UI must label the original source and mapping uncertainty. Stop at a
clear evidence blocker rather than fill gaps with invented syntax. This phase
can proceed independently once the missing source/input basis is available.

## Phase F: DVB-I local input, then explicit network retrieval

Follow [DVB_I_INPUT_DESIGN.md](DVB_I_INPUT_DESIGN.md): published TS 103 770 V1.2.1
first; newer draft support has its own named profile. Proposed first local limits:
8 MiB/document, depth 64, 100,000 nodes, 1 MiB per text value and 1,000 diagnostics.
Ratify limits before implementation and report bounded failures explicitly.

- Namespace-equivalent prefixes/default namespace, wrong edition, unknown
  extensions, missing/duplicate IDs, multilingual names, alternative delivery
  instances and regional LCN conflicts. Same name/number is never service identity.
- Reject DTD/external entities and unintended XInclude/schema/network resolution;
  test entity expansion, deep trees, huge attributes/text and truncated UTF-8.
  No URI in metadata is fetched by parsing or inspecting it.
- Failed replacement/cancel must preserve the prior usable session; source jumps
  are document-revision-bound. Verify original bytes vs formatted XML distinction.
- Optional later HTTP phase: scheme/host/redirect policy, private-network access
  and credential boundaries, explicit consent UX, TLS failure, request timeout,
  compressed-body/decompression limits, cache/ETag/304 and source replacement.
  Retain retrieval errors without logging authorization headers or URL secrets.

## Combined acceptance and release gates

Run the ordinary tests against the production binary; cancellation seams belong
only in the separately gated helper. The strict runner rejects missing binaries,
zero tests and unexpected skips. The optional separately sourced real recording
may remain the one documented skip; that means no real-recording claim.

```sh
export SHOWPSISI_CORE="$PWD/build/protocols/bin/showpsisi-core"
export SHOWPSISI_TEST_CORE="$PWD/build/protocols/bin/showpsisi-core-test"
python scripts/ci/windows_native_checks.py --engine --artifacts artifacts/protocol-extension/engine
```

Despite its historical filename, the strict engine runner works on Linux too;
a Linux invocation is not Windows validation. Source the appropriate official
SDK environment first. The runner includes service/protocol metadata, new suites,
MCP/cancellation, packaging and icon regressions. `scripts/check.sh` also includes
the new suites; UI jobs remain separately required.

Before release promotion: exact-revision Windows/Linux core gates; Qt native
interaction and Web integration suites using real engine; byte/source/export
regressions; hostile-input and resource tests for enabled features; package
runtime/resources/source-manifest checks; independent review; synchronized
matrix/API docs. Capture new UI interactions and screenshots only after tests
actually run. Build success or an old screenshot is not an interaction result.

Retain failing as well as passing artifacts under ignored `artifacts/`: commands,
source/build identity, compiler/SDK versions, fixture manifests, test summary JSON,
logs and native UI traces. Commit only small licensed/synthetic inputs and tests.
A green synthetic suite promotes exactly its bounded claims; complete receiver,
real broadcaster or edition-wide conformance remains explicitly unverified.


### NTT/STT continuation

The next section-only slice adds SNS names (including language wildcard,
application/source ID distinctions, duplicate observations and opaque descriptors),
MTS code-page/BMP text with explicit unknown/invalid status, and STT signed offset
arithmetic. Tests cover every structural payload truncation, nested lengths,
reserved pages/characters, odd BMP length and surrogates, format-effector framing,
255-byte names, bounded many-segment/many-record inputs, offset zero and underflow
boundaries. CRC admission, explicit context and no-map/export rules remain the
same. Source-name selection, time-based activation and channel-map joins remain
separate future work requiring conflict/generation policy and UI evidence.

A supplementary seeded parser-only ASan/UBSan probe uses 12,000 mutated/random
NTT/STT sections. Its raw corpus/result are retained under ignored
`artifacts/protocol-extension/ntt-stt-draft`. LeakSanitizer cannot run under the
executor's ptrace environment, so the successful rerun disables leak detection;
this does not establish leak freedom or replace real-core fixture tests.

The NTT/STT checkpoint passed 30 focused real-core cases, independent normative
review and a second real-core rerun. The subsequent source-hash-verified combined
Linux gate passed 371 tests with zero skips. Checkpoint and suite evidence:
`artifacts/protocol-extension/ntt-stt-checkpoint.json` and `ntt-stt-engine/`.
Hold the source at this checkpoint for the separately tested topology integration;
rebuild and rerun after integration rather than carrying these counts forward.
