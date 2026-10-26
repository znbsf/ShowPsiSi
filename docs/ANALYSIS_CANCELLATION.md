# Cooperative analysis cancellation

For compact progress, revision-bound result pages, in-session pause/resume and
bounded preview scans, see [responsive analysis](RESPONSIVE_ANALYSIS.md).
Pause preserves the session; it does not change Cancel into a resumable action.

Status: implemented and locally tested after merged PR #4 (`dcadd66`);
new hosted CI and final native-runtime checks remain separately tracked.

## Scope

Cancel one queued or running local-file analysis without restarting the backend.
Keep ordinary JSONL operations FIFO and all Engine/TSDuck state on one owner
thread. A separate input/control path can set the target analysis's cancellation
flag; it cannot inspect or mutate engine evidence. Cancellation bypasses the
bounded ordinary request queue. Whole stdout JSON lines remain serialized.

`cancel_analysis.request_id` identifies the original native analyze request.
Integer and string IDs remain distinct. A successful cancellation request is an
acknowledgement, not the original operation's terminal result. Unknown/completed
requests report that no cancellation was requested. An accepted cancellation must
not race into a successful final analysis result.

## State and evidence

The original analysis returns one `analysis_cancelled` error with its final state.
State distinguishes idle, analyzing, cancelled, failed and complete. Existing
`complete` remains true only for successful completion. Cancelled work discards
partial evidence and edit previews, retains source/progress only as cancelled
status, and never restores an unrelated previous source. Elapsed time freezes.
Loaded extension configuration and monotonically increasing revision identity
survive cancellation. Query may report the empty cancelled state; editing,
comparison and export still require a complete successful analysis.

EOF drains accepted requests rather than silently cancelling an active scan.
Cancellation is cooperative: synchronous file reads, SDK calls and output may
limit responsiveness. This feature makes no hard real-time latency guarantee and
does not add live network inputs or large-file indexing.

## User interfaces and MCP

Qt and Web expose Cancel while scanning, then Cancelling until the original
request settles. Progress and final responses must match the active request and
scan generation. Cancelling clears selection, comparison, detail and edit state.
It is distinct from an unexpected backend exit. A new scan is available after
terminal cancellation; no automatic restart or write replay is permitted.

The MCP adapter maps outer request IDs to native IDs and keeps its input loop
responsive. It accepts `notifications/cancelled` for active analyses, consumes
the native terminal response, and suppresses the cancelled MCP result. Unknown,
late and unrelated notifications do not abort exports. Progress is emitted only
for a supplied progress token and stops after cancellation/termination.

## Required evidence

- Queued, running, repeated, wrong-target and late cancellation; exact ID types.
- Completion/cancellation race, queue bounds and input EOF behavior.
- Successful A + preview, cancelled B, successful C: no stale evidence or tokens.
- Real Qt and Chromium/native-engine Cancel → cancelled → rescan workflows.
- Stale progress/result isolation and disconnected-backend controls.
- Real MCP subprocess cancellation, progress token and request-ID routing.
- Existing engine, protocol, bridge, Qt, browser and Rust regressions, plus Windows CI.
- Deterministic scheduling checks through a test-only compiled seam where needed;
  no production runtime testing switch or reliance on a file merely being slow.

## Implementation details

The input reader validates against an immutable startup schema before queueing or
registering an analysis. The waiting ordinary queue has capacity 64; overflow is
`queue_full`. Duplicate queued/running analysis IDs are `duplicate_request_id`.
The matching registry entry is retired before the terminal response is emitted,
so a completed ID can be reused. Legacy analyses without integer/string IDs still
run, but cannot be targeted by cancellation. Edit the schema only with an intended
backend restart; it is not a live-reload protocol.

The opt-in CMake target `showpsisi-core-test` provides deterministic one-shot file
gates. Its hooks are compiled out of `showpsisi-core`; CI explicitly enables
`SHOWPSISI_BUILD_CANCELLATION_TESTS` and supplies `SHOWPSISI_TEST_CORE`. Missing
helpers do not count as passing required cancellation coverage.

Qt supports the trusted-local development variable `SHOWPSISI_CORE_ARGS_JSON`:
a JSON array of up to128 strings without NUL, passed directly to QProcess without
a shell. It replaces the default `["--root", root]` argument list, so callers must
include needed root/script arguments themselves. This allows portable interpreter
fixtures; stream data cannot configure the launcher or inject protocol frames.


## Python and MCP completion semantics

`Core.submit(method, params=None, progress=None)` returns a handle with
`request_id`, `done()` and `result(timeout=None)`. A result timeout does not cancel
the request. `Core.call` remains synchronous. `CoreError(RuntimeError)` retains
`code`, `message`, `data`, `error` and `request_id`. Progress callbacks run in the
result-waiting thread, never in the stdout reader, so a callback may submit a
cancellation without deadlocking the response router.

Explicit `Core.close` cooperatively cancels pending analyses and reaps its reader
threads and owned process. Active exports may delay shutdown and are not killed.
Passive MCP stdin EOF has different semantics: drain accepted work first, then
close. This preserves one-shot clients that send requests and close their input.

The MCP `cancel_analysis` tool targets an outer MCP request ID. It returns its
acknowledgement and preserves the original analysis's terminal tool error. By
contrast, `notifications/cancelled` suppresses the original outer response after
cancellation while the adapter still consumes the native terminal result. Repeated
explicit cancellations stay accepted until that target finishes.

Independent review found and verified repairs for passive-EOF cancellation and
repeated queued cancellation. Six independent probes and 50 deterministic
completion/cancellation interleavings passed; completed-ID reuse, overflow, typed
IDs and callback-triggered close were included. Stress repetitions are not added
to the count of distinct automated tests.

The advertised MCP2025-06-18 JSON Schema defines RequestId and ProgressToken as
string/integer. Integer-valued numeric representations such as `1.0` are valid
JSON Schema integers; the adapter preserves them at the outer MCP boundary while
mapping to its generated native integer IDs. Numeric `1` and `1.0` share identity;
string `"1"` is distinct. Boolean, null, fractional and non-finite values are not
accepted. The native JSONL cancellation contract retains integer-token/string
IDs. See the [pinned MCP schema](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/2025-06-18/schema/2025-06-18/schema.json)
and [JSON Schema numeric semantics](https://json-schema.org/understanding-json-schema/reference/numeric).


## Candidate input admission (2026-10-26)

A bounded readability/framing/charset/range check now runs before an analysis
replaces the previous source. Rejection returns `input_rejected` with
`data.state_preserved=true`; the old input, revision and preview still belong to
the old source. A fresh session remains idle after rejection. Both UIs retain
their existing views until the owner admits the candidate. Accepted scans still
own a new revision, and later read failures/cancellation discard that scan's
partial evidence as above. Admission rejection and accepted cancellation use
the same owner-side `finish` decision so an accepted cancellation cannot be
published as a successful scan or admission rejection. No control-thread engine
state access is added.
