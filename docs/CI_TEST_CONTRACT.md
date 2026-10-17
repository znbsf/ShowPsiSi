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
