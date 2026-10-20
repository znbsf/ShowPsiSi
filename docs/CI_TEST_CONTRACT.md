# CI completion and isolation contracts

This is a prevention runbook for the recurring failure classes investigated in
October 2026. It describes required behavior, not a promise that CI cannot fail.
Use it with [delivery and recovery](DELIVERY_RUNBOOK.md),
[cloud environment notes](CLOUD_DEVELOPMENT.md), and [test commands](../tests/README.md).

## Do not equate intermediate states

Keep these states distinct: requested UI value, rendered geometry, persisted
settings, completed screenshot, complete JSON report, validated package, and
uploaded artifact. A passing earlier state does not prove a later one.

- Wait for a bounded observable predicate or acknowledgement. A fixed sleep or
  timer interval alone is not an acceptance condition.
- Preserve a deadline and fail with useful diagnostics when it expires. Never
  replace a failure with an unconditional retry, a weaker assertion, or a skip.
- Completion reports must be the last required output. Consumers must not kill
  their writer because a file merely exists.
- Atomically publish test checkpoint JSON after a complete write and checked
  close. Keep temporary and final names in the same directory. Test-only hooks
  must remain absent from production executables.

## Observed failure classes and required checks

| Class | Observed evidence | Required regression |
| --- | --- | --- |
| Parallel shared writes | Two engine POST_BUILD commands copied SDK files into one Windows output directory | One shared runtime staging target; repeated parallel single-/multi-config builds preserve identities |
| Windows path/environment assumptions | Copied environment dictionaries lost case-insensitive lookups; path separators differed | Normalize the explicit contract; test mixed casing and path forms without weakening identity checks |
| Partial result publication | QFile created a result before buffered JSON was complete; the consumer terminated Qt | Complete-object polling with a deadline, partial/empty/error/exit probes, original failure preserved |
| Premature evidence publication | Layout result JSON could precede its screenshot | Required capture finishes before completion; missing evidence remains visible |
| Layout persistence ordering | A requested keyboard resize preceded geometry polish and durable settings; immediate close could save the previous size | Test requested/rendered/persisted values separately, graceful close, delayed save, repeated keys, drag, Reset and constrained windows |
| Evidence lost during cleanup | Wait/early-exit or cross-run assertions could bypass retention before temporary directories disappeared | Bounded report/log/screenshot retention for every failure path, without masking the original exception |
| Settings contamination | Retained smoke used default user settings rather than an isolated test path | Explicit per-run settings; share a path only for deliberate persistence/reopen tests |
| Dialog choice is not yet an export | Duplicate-output test saw `exporting=false` before the delayed Save dialog accepted; it judged empty feedback and replaced the pending choice | Await that choice's accepted/rejected signal, then its export terminal; delayed duplicate acceptance, repeated refusal/cancel, and unchanged output/manifest bytes and mtimes |
| Query has not settled | Use-snapshot query clears detail without setting busy/inspecting; next timer phase could rescan before its response | Hold the real query terminal until the UI acknowledges waiting; prohibit premature analyze, then verify matching inspection |
| Cancellation sampling window | Fixed fixture sleeps could deliver ACK and terminal between UI timer samples | Hold terminal until UI observes ACK while still busy/cancelling; acknowledge deliberately late frames through the protocol before asserting |
| Platform geometry differences | Windows compact inspector measured 89px against the unchanged 90px minimum | Keep the threshold; measure geometry/fonts and correct layout, then retain successful platform evidence |

Predicate-based polling of busy/inspection/comparison state is legitimate. Do
not classify every timer or sleep as a defect; demonstrate the missing completion
condition before changing code.

## Ownership and evidence

- One build process owns a build directory. Separate worktrees need separate
  build directories; independently scheduled builds must not race shared output.
- One controller owns an interactive device or desktop at a time. Unit tests can
  run in parallel only with isolated inputs, profiles, ports and output paths.
- Retain bounded failure evidence even when JSON is incomplete, the process
  exits, diagnostics fail, or a later assertion compares two individually valid
  reports. A normal smoke screenshot is not evidence for a different failed flow.
- Record the exact source head and the actual PR merge/test checkout SHA. Inspect
  the relevant platform artifact; compilation is not native interaction proof.
- Test the final combined source after integrating independent branches. Earlier
  green checks do not validate the newly combined revision.

## Portable delivery remains a separate gate

A green build or a staged directory is not a delivered package. Require runtime
and relocation validation, the exact reviewed dependency/source/notice inventory,
archive integrity, full manifest hashes, and a verified uploaded artifact. Bind
our compiled executables to their tested source/build manifest; do not create a
circular requirement to preapprove unpredictable future executable hashes.
Unknown third-party payloads must still fail review. Preserve platform limits:
offscreen Qt checks do not prove native Windows dialogs, a clean machine, GPU
behavior, or WebView2 interaction.

## Qt async regression reproduction

The postmerge export failure was reproduced locally by delaying only the third
(duplicate-output) dialog acceptance to 700ms: the old harness failed only
`existing_output_refused`, matching the hosted result. The fix waits on the actual
choice-resolution event; it does not lengthen a production timeout. Existing output
and manifest hashes plus modification times are checked after repeated refusals.

`test_snapshot_query_waits_for_terminal_before_rescan` uses a real-engine proxy,
not fabricated decoded evidence. The proxy holds the Use-snapshot query terminal
until the UI has acknowledged waiting, and records any premature analyze request.
Cancellation's adversarial fixture releases its terminal only after the driver
observes the UI's ACK check; a subsequent fixture response orders late frames.

All Qt integration paths use `qt_evidence.retain_qt_evidence`. Its bounded context
retains explicit files before temporary cleanup and preserves the original error
if retention itself fails. The strict Qt runner executes its dedicated unit suite
on both Linux and Windows, alongside native UI and resource-path tests.

## Qt tooltip delegate lifetime

Windows run `39212811287` reached the operation-parity dark-theme flow but
failed the unchanged diagnostics gate on `Cannot read property 'hovered' of
null` in the structure-tree tooltip. The tooltip's `anchorControl` tracks
`Popup.parent`; that parent can become null while bindings still exist during
delegate detach/retirement. This is a lifecycle defect exposed by platform
ordering, not grounds to retry away or suppress QML diagnostics. The original
log identifies the null anchor, but does not identify the exact retirement phase.

The parity regression now opens a real inspector-tree tooltip, explicitly
detaches its parent, checks hidden/false hover and empty parent-derived text,
then rebinds it before continuing the real-engine evidence and edit flows.
Both themes exercise this interval deterministically. Shared `SafeTip` hover
and text bindings guard the absent parent; normal tooltip content and errors
remain observable. Retain the existing rejection of any QML `TypeError` and
`ReferenceError`, including errors emitted during teardown.

## Windows result-file sharing during publication

Main run `39223520677` (source `827535b999d8081b197f1d2e04d0750ea597ee2f`)
failed the resource-path smoke while opening its result file with Windows
`PermissionError: [Errno 13]`. The log does not establish whether the short-lived
lock belonged to Qt or another process. A denied read is not a published result.
The consumer now polls that specific result path within its original deadline,
just as for a missing or incomplete result. Permanent denial and a writer that
exits without a readable complete object still fail with the original cause;
other I/O errors are not retried, and a complete failing report remains a failure.
Regressions cover each of those cases. Resource-path runs also retain their
explicit result/log/screenshot/trace evidence before temporary cleanup, including
incomplete-result and completed-acceptance failures. No timeout, acceptance
threshold, diagnostic gate, or production code changed.

## Responsive title-bar controls

PR #25 run `39255322746` failed six browser flows with a 527px document at
520px viewport width. The shared title bar remained one flex row after adding
the input-kind selector. Its buttons exhausted the row, shrinking that selector
to its arrow before wider system fonts forced page overflow. DejaVu Sans
reproduces all six failures at exactly 527px; a narrower default font can hide
the selector label without overflowing, and the adjacent 521px breakpoint also
overflows. Do not hide overflow or relax the existing viewport assertions.

The title bar now wraps and preserves its controls' intrinsic widths. The
dedicated browser regression checks full selector width, visible/hit-testable
controls, and no page overflow at 520/521/760/761/900/1100/1440px, in both themes
and both TS/DVB-I workspaces with default and DejaVu Sans fonts. The original
cancellation, comparison, theme, layout-reset, tree and evidence tests retain
their assertions. Browser evidence does not establish native WebView2 behavior.

## Windows test-owned descendant log handles

PR #28 run `39418321685` completed the responsive hydration assertions but
failed temporary-directory cleanup with WinError 32 on `analysis-responsive.log`.
The shared helper already closed its Python log handle and reaped the direct Qt
process; the exact remaining holder was not identified. Forced termination of
only Qt can leave a descendant holding inherited handles, so Windows test teardown
now targets the still-live, test-owned process tree by PID and checks the outcome
before reaping the direct child. Already-exited graceful-close flows remain
unchanged. This is test cleanup, not proof of graceful application shutdown.

The regression starts a real Windows parent/descendant sharing a log, then requires
immediate file deletion after teardown. Mocked contracts also check ownership,
ordering and visible failure. Do not suppress PermissionError, retry deletion with
a fixed sleep, kill by image name or terminate unrelated processes to pass it.

The next Windows run (`39420939788`) passed that inherited-log regression but
exposed harness integration failures: evidence tests' mocked `Popen` intercepted
nested `taskkill`, and one normal-close flow returned taskkill code 128 without
retained stderr. Evidence tests now isolate their fake launch cleanup. Teardown
records the command diagnostics and accepts code 128 only with an immediately
verified successful exit of the same owned Qt process; still-live, nonzero-exit
and other command failures remain failures. The earlier event's cause remains
unproven. Dedicated contracts cover each branch without changing UI deadlines.

## Browser progress and dialog completion boundaries

PR #28 run `39423049118` passed Windows native and packaging gates but failed
two browser assertions. The cancellation screenshot contained genuine native
one-packet progress: the harness had recorded an empty baseline after transport
receipt but before the animation-frame publication. The test now awaits that
applied checkpoint while the engine's after-progress gate prevents further real
updates, then retains ignored-envelope equality across a rendered frame.

The shortcut screenshot showed a question mark appended to the source field.
Chromium restores the original focus synchronously when a dialog closes, before
its queued close event invokes application focus restoration. A focused browser
reproduction confirmed this ordering. Repeated shortcut checks now await the
actual close-event handler before moving focus for the next opening; a separate
regression verifies that boundary. Original ignored-frame, focus, content and
modal-keyboard assertions and deadlines remain unchanged. No production handler
was changed to manufacture these test results.
