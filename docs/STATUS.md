# ShowPsiSi status

Updated: 2026-10-16 UTC.

- PR #1 merged as `ac039f6`: modern workbenches and initial integrity loop.
- PR #2 merged as `beb2e57`: Windows MSVC engine/Qt validation.
- PR #3 merged as `f63bc60`: snapshot comparison, layout persistence and protocol
  generation integrity. All four jobs passed at feature head `98482d1` in
  [run 38976239202](https://github.com/znbsf/ShowPsiSi/actions/runs/38976239202).
- No release or installer published. Windows Tauri compile/test validation is the
  next CI-only step, separately tracked from Windows Qt/runtime claims.

## Current result

Qt Quick and Tauri/Web share one native C++/TSDuck engine and JSONL API. Both have
an editor-style dark workbench, semantic PSI/SI trees, evidence views, keyboard
navigation and search. The parser exposes its linked native table/descriptor
registry, explicit standards/regional context, section-PID discovery and optional
extra PIDs. An offline metadata index provides verified standard-level links.

Interactive development used the assistant's **own Linux cloud computer**;
Windows validation uses GitHub-hosted runners. No owner Windows PC, television
or phone was accessed. The actual native Linux Qt and
Tauri/WebKitGTK applications have been built and exercised, including native
edit/export. Browser validation is separately labeled and never substituted for
a native-runtime claim.

## Verified current behavior

- Read-only A/B snapshot comparison with deterministic pagination, explicit cutoffs,
  per-side evidence and stable identities. Native Qt and browser workflows preserve
  the main selected snapshot until an explicit navigation action.
- Qt and Web pane sizes persist with bounded restoration and Reset layout.
- Reused-version generations and same-packet reception order preserve evidence
  boundaries. Extra-PID SDT stays inspectable without replacing canonical services.

- 30 engine tests: source preservation, analysis failure reset, exact PAT→PMT
  binding, snapshot inspection cutoff, regional text, extension validation,
  export exclusivity/cleanup, framing and regular-file input guards.
- 26 protocol/reference tests: ATSC and ISDB fixtures; DVB-S/S2/T/T2/C delivery
  parameters; private PDS isolation, nondefault PID discovery and unknown bytes.
- 5 HTTP bridge tests and 16 live Chromium/native-engine tests, including backend
  termination, keyboard/tree interaction, historical snapshots and responsive layout.
- 8 compiled native Qt tests: real workflows, search, literal untrusted text and
  tooltips, no remote image fetches, and failure-state cleanup.
- 7 Rust native-shell tests: exact URL allowlist plus launcher success/failure,
  spawn errors, bounded diagnostics and unconfirmed timeout. Native GTK source selection, save/export,
  independent readback, overwrite-warning cancellation and backend-death flows
  were also checked in the actual application.
- Both workbenches carry the selected packet cutoff into inspection. A historical
  view cannot silently assemble a later sibling section.

Total automated test cases above: **92**. See [cloud validation](VALIDATION_CLOUD.md),
[native Tauri evidence](NATIVE_TAURI_VALIDATION.md) and [test commands](../tests/README.md).
These are local cloud results; check each PR's latest CI commit separately.
Native Linux Tauri comparison and persisted layout have been exercised on the
new assets. Its actual unsupported desktop-browser helper now reports failure;
Copy URL succeeds and clears the error. Browser navigation itself is not verified.
The CI-only Windows PR #2 is merged as `beb2e57`. All four jobs passed in
run 38974640106, including Windows baseline engine/protocol/HTTP/Qt regressions.
The retained Windows Qt screenshot was inspected after fixing offscreen font
discovery. The expanded PR #3 suite also passed all four jobs: Windows engine29 + one
explicitly allowed absent-recording test, protocol26, HTTP5 and Qt8. Its retained
Windows Qt smoke screenshot was downloaded and visually inspected.

The SDK currently registers **43 table decoders / 306 descriptor decoders**.
The 12,490-byte standards index associates 191 descriptor names and 26 table names,
without bundling PDFs. These counts are not conformance percentages. See
[protocol coverage](PROTOCOL_COVERAGE.md) for measured, SDK-only and unknown cases.

## Remaining boundaries

- New Windows WebView2 and macOS builds, installers and actual external-browser
  launching have not been validated in this iteration. Original Windows evidence
  below does not validate later changes.
- No RF demodulation, tuner control, complete DTMB-specific signaling guarantee or
  ATSC 3.0 IP/ROUTE/MMT support.
- No exhaustive standards conformance, arbitrary descriptor/table edit/remux,
  live UDP/SRT input, persistent large-file index or production EPG time grid.
- Exact field-to-byte selection highlighting remains future work. Unknown private syntax is retained, never invented.
- Export output+manifest use exclusive creation and failure cleanup, but are not
  a crash-atomic transaction spanning two files.

## Original Windows prototype evidence

The initial `a79ce16` prototype compared Qt Quick 6.7.3 and Tauri/WebView2 using
TSDuck 3.39-3956. It exercised a generated DVB stream and official French UHF22/UHF33
recordings, MCP edit/export/readback and three alternating benchmark trials.
See [BENCHMARK.md](BENCHMARK.md) for those exact binary identities and limits.
Those historical resource measurements must not be presented as measurements of
the new workbench. Historical SDK locations and experiment retry budgets do not
constrain this cloud iteration.

SDKs, binaries, downloaded streams, local profiles and transient evidence remain
ignored. Source screenshots and reproducible tests are committed. Read
[CLOUD_DEVELOPMENT.md](CLOUD_DEVELOPMENT.md) before repeating environment diagnosis.
