# Responsive analysis, pause and bounded previews

This work targets local-file analysis, especially Qt on files of tens to hundreds
of MiB on a mechanical disk. It preserves sequential block reads and the shared
single-owner C++/TSDuck engine. It is not a new network-input implementation,
durable checkpoint format, disk-backed evidence database or complete remuxer.

## Separate progress from evidence

The frontends request `response_mode: "compact"` for analysis and snapshots.
Progress reports contain source identity, revision, counters, phase and coverage,
not complete tables, EPG, distributions and history. The previous legacy response
mode remains available to API callers.

A compact terminal response is not proof that every frontend model is loaded.
The frontend subsequently hydrates the eight result collections through
`query_result`, with a revision and optional inclusive snapshot cutoff. Pages
have an item limit and a bounded serialized item payload. Collection totals may
be unknown until that collection is materialized; page `total` and `next_offset`
are authoritative. A client must not stop at its first page and advertise a
whole-file search or a zero-result conclusion.

Tables and logical groups omit expensive occurrence-distribution bins from the
bulk projection. Individual section inspection retains detailed evidence. Large
group membership lists use bounded inline IDs plus the compact table rows'
`table_group_id` and `selected_in_snapshot` fields, allowing the UI to reconstruct
complete membership after hydration without silently hiding later members.

Qt owns the process and wire JSON decoding on a worker thread; the GUI receives
coalesced progress and bounded page payloads. QML still decodes each bounded
page into native JavaScript arrays on the GUI thread, avoiding costly traversal
of large QVariant-backed collections. This is not a claim that all JSON work
is off the GUI thread. Web updates progress separately from
the workbench DOM. Stale replaceable progress can be coalesced, but terminal
responses, errors and control acknowledgements must not be dropped. Every page
and update remains bound to the active request/revision/cutoff. Stopping frontend
result loading invalidates its page generation so a late page cannot revive it.

This is paged transport with incrementally hydrated in-memory UI models, not an
unbounded-file memory guarantee. All-record search and existing views remain
available after hydration. Very long captures still retain occurrence indexes;
disk-backed indexing is a separate future step.

## Pause is not cancel

`pause_analysis` and `resume_analysis` target the original analyze request ID.
An accepted control request is an acknowledgement of intent; the owner-thread
progress state establishes when analysis is actually paused or resumed.

Pause preserves the open source, cursor/buffer position, packet framing, demux
assembly, discovered PID filters, continuity state and collected evidence.
Resume continues that session. Cancel wakes a paused worker and follows the
existing cancellation terminal contract, discarding incomplete evidence.
Completion, pause and cancellation races must have one terminal outcome.
Passive input EOF resumes accepted paused work so the existing drain contract
does not hang forever with no remaining sender. This is distinct from an explicit
application cancellation or shutdown request.

The initial implementation supports pause within the running application only.
It does not promise resume after application exit. Engine query/inspection while
paused is explicitly unavailable rather than dispatched unsafely into mutable
parser state. Local UI interactions remain responsive; complete detailed
inspection is available after a full scan or bounded preview finishes.

Source metadata is checked for ordinary changes while the task is active.
Size/mtime checks are not a cryptographic immutability guarantee. Users must not
modify the input while scanning or paused. Hashing the entire source merely to
start a preview would defeat its mechanical-disk benefit.

## Scan modes and evidence limits

- `full`: all packets; a preview budget must not silently limit a full scan.
- `prefix`: the first `max_packets` packets.
- `range`: `start_packet` inclusive to `end_packet` exclusive.
- `distributed`: a bounded number of contiguous windows spread across the file,
  with a total `max_packets` budget.

Prefix and distributed scans can instead use `sample_percent` (integer 1–100).
The engine converts that percentage to a packet budget after detecting framing,
rounding down with a one-packet minimum for a nonempty source. Percent and
`max_packets` are mutually exclusive; percent is rejected for full/range mode.
The recorded requested percentage is distinct from the exact resulting coverage.

The contract is packet based. Current time labels use a user-supplied bitrate,
not a newly measured PCR index. Do not label approximate byte/packet fractions
as exact recording time. Few larger windows are preferable to frequent seeks
on a mechanical disk.

Coverage records source packet count, scanned packet count, actual half-open
intervals and whether coverage is partial. Adjacent intervals are merged; only
real gaps reset assembly and continuity. 188/192/204-byte framing is preserved,
and evidence positions remain absolute in the original source.

Each disconnected window discovers its own available signalling dependencies.
A missed PAT/PMT/MGT, a long-cycle table, or an incomplete section is unknown
evidence, not proof of absence. Skipped regions must not be reported as transport
loss. Same-version sections on opposite sides of a gap must not fabricate one
complete table; derived generations and reconstruction respect window boundaries.
Consumers must retain the reported semantic scope for previews.

Partial coverage is not a complete-file result. Editing/export and unsupported
cross-gap comparisons are guarded, rather than silently treating a successful
preview as a successful full scan. A 10% sampling budget is neither a 90%
completeness guarantee nor a guaranteed tenfold speedup.

## Regression and performance evidence

See [the dated validation report](RESPONSIVE_ANALYSIS_VALIDATION.md) for the
measured synthetic comparison, exact binary identities and verification limits.

The strict native runner includes `test_responsive_analysis.py` and the independent
`test_analysis_preview_review.py`; Qt includes `test_qt_analysis_modes.py`.
Browser integration exercises the real core through its supported loopback
bridge. Existing parser, export, cancellation, resource, topology and UI tests
remain required.

Acceptance includes uninterrupted versus pause/resume equivalence; queued,
repeated, wrong-ID, EOF and completion races; paused cancellation; source changes;
late-page isolation; all-record hydration; absolute offsets in all three framings;
adjacent-window continuity; and no cross-gap section/generation reconstruction.

`scripts/benchmark_analysis.py` compares a baseline legacy core and a compact
candidate using the same deterministic synthetic fixture. It records binary and
input hashes, individual wall-time rounds, terminal and fully hydrated latency,
message counts and sizes, and resulting collection counts. The dense empty-EIT
fixture stresses table cardinality, not realistic EPG decoding.

```sh
python scripts/benchmark_analysis.py --core /path/to/baseline-core \
  --root /path/to/baseline-checkout --response-mode legacy \
  --output artifacts/analysis-baseline.json
python scripts/benchmark_analysis.py --core /path/to/candidate-core \
  --response-mode compact --output artifacts/analysis-candidate.json
```

CLI wall time includes startup and client JSON decoding. Cloud offscreen tests
and sandboxed Chromium do not establish mechanical-disk throughput, native
Windows/WebView2 interaction or the user's specific stream behavior. Publication
must report final source/CI identity and these remaining boundaries, not convert
synthetic measurements into a general speed claim.

The legacy-compatible `metrics.scan_ms` is wall elapsed through the engine's
terminal commit, including pause and owner finalization, not active CPU time.
It excludes subsequent client hydration/rendering. `scan_ms_basis` describes this
explicitly; performance comparisons must use the fully consumed wall-time metric
as well, and must not turn paused wall time into an active scanning rate.
