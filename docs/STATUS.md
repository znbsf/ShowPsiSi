# ShowPsiSi status

Updated: 2026-10-16 UTC.

- PR #1 merged as `ac039f6`: modern workbenches and initial integrity loop.
- PR #2 merged as `beb2e57`: Windows MSVC engine/Qt validation.
- PR #3 merged as `f63bc60`: snapshot comparison, layout persistence and protocol
  generation integrity. All four jobs passed at feature head `98482d1` in
  [run 38976239202](https://github.com/znbsf/ShowPsiSi/actions/runs/38976239202).
- PR #4 merged as `dcadd66`: Windows Tauri release executable compiled and six
  Rust unit tests passed. All five jobs passed in run 38976742240. This is compile
  evidence, not Windows WebView2 interaction or an installer.
- PR #5 merged as `7df3706`: cooperative scan cancellation, MCP routing and
  stale-progress isolation. All five jobs passed at head `935ee17` in
  [run 38980765498](https://github.com/znbsf/ShowPsiSi/actions/runs/38980765498).
  The exact merged main also passed all five jobs in
  [run 38981738934](https://github.com/znbsf/ShowPsiSi/actions/runs/38981738934).
  Windows engine/Qt regressions and Tauri release compilation passed; this does
  not establish Windows WebView2 interaction.
- PR #6 merged as `3e51f4c`: native Qt Save destination and TS/BIN choice.
  All five CI jobs passed at `37e92c0` in run 38982972251; Windows Qt15 passed.
- No release or installer published. SDK 3.45 cross-platform validation is pending.

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

- Cooperative targeted scan cancellation with explicit lifecycle states, cleared
  incomplete evidence and safe rescan. Qt/Web reject stale/foreign progress;
  backend death disables stale actions. MCP input stays responsive and passive
  EOF drains accepted calls. See [cancellation contract](ANALYSIS_CANCELLATION.md).

- Read-only A/B snapshot comparison with deterministic pagination, explicit cutoffs,
  per-side evidence and stable identities. Native Qt and browser workflows preserve
  the main selected snapshot until an explicit navigation action.
- Qt and Web pane sizes persist with bounded restoration and Reset layout.
- Reused-version generations and same-packet reception order preserve evidence
  boundaries. Extra-PID SDT stays inspectable without replacing canonical services.

- 30 engine tests: source preservation, analysis failure reset, exact PAT→PMT
  binding, snapshot inspection cutoff, regional text, extension validation,
  export exclusivity/cleanup, framing and regular-file input guards.
- 43 protocol/reference tests: ATSC and ISDB fixtures; DVB-S/S2/T/T2/C delivery
  parameters; private PDS isolation, nondefault PID discovery and unknown bytes.
  New fixtures cover all 15 newly registered table types, DTMB DRM, explicitly
  signalled text, registration inheritance and safe namespace fallback. All 21
  fixture XML inputs reproduce byte-for-byte with the pinned compiler.
- 6 SDK migration tests: runtime/header identity, UTF-8 filesystem paths,
  root arguments, manifests and no invented DTMB charset/timezone.
- 14 deterministic native cancellation tests and 17 MCP/transport tests: queued,
  progress and completion boundaries, EOF drain, typed IDs, progress tokens,
  response routing and safe close. Test gates are excluded from production.
- 6 HTTP bridge tests and 25 live Chromium/native-engine tests, including backend
  termination, keyboard/tree interaction, historical snapshots and responsive layout.
- 16 compiled native Qt tests: real workflows, search, literal untrusted text and
  tooltips, no remote image fetches, failure-state cleanup, external TS/BIN save
  destinations, cancelled save, stale preview rejection and no-overwrite errors.
  Linux tests also enforce a read-only application resource directory; the
  Windows case uses a separate resource directory without claiming ACL coverage.
  Actual DTMB/DSM-CC fixtures also verify standard selection, empty projections,
  guarded warning/XML display, raw-byte preservation and indexed list labels.
- 7 Rust native-shell tests passed on the merged pre-upgrade baseline: exact URL allowlist plus launcher success/failure,
  spawn errors, bounded diagnostics and unconfirmed timeout. Native GTK source selection, save/export,
  independent readback, overwrite-warning cancellation and backend-death flows
  were also checked in the actual application.
- Both workbenches carry the selected packet cutoff into inspection. A historical
  view cannot silently assemble a later sibling section.

The SDK upgrade has **165 current local tests passed**: engine30,
protocol43, SDK6, cancellation14, MCP17, HTTP6, Qt16, Qt-result publication8 and Chromium25. The integrated
Qt16 run includes both PR #6 export scenarios and the new protocol fixture checks.
The initial SDK head `6fcb135` passed all five jobs in run 38990955608,
including Windows SDK/Qt and both Rust jobs. A confirmed result-publication race
from PR #6's post-merge Windows run was then corrected in the test harness.
The strict local Qt gate now passes 16 native tests plus 8 publication tests;
its new exact-head hosted CI is pending. See [cloud validation](VALIDATION_CLOUD.md),
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

The linked SDK is **TSDuck/TSCore 3.45-4798**, using C++20. The Linux runtime
registers **58 table XML names / 347 descriptor XML names**, including aliases.
The offline standards index associates 227 descriptor names and 49 table names,
without bundling PDFs. These counts are not conformance percentages. See
[protocol coverage](PROTOCOL_COVERAGE.md) for measured, SDK-only and unknown cases.

Explicit DVB uses the SDK strict-DVB flag. Ambiguous DSM-CC module or private-dual
descriptor contexts retain generic bytes and show a warning instead of silently
asserting another namespace. Guarded XML is labelled; wire bytes are authoritative.
The split TSCore/TSDuck libraries, headers and runtime data must match; both
version-specific ABI symbols are enforced.

## Remaining boundaries

- Windows WebView2 interaction, macOS builds, installers and actual external-browser
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
