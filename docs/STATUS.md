# ShowPsiSi status

Updated: 2026-10-16 UTC. Development branch: `feat/editor-workbench-integrity`.
Review: https://github.com/znbsf/ShowPsiSi/pull/1 (draft; not merged or released).

## Current result

Qt Quick and Tauri/Web share one native C++/TSDuck engine and JSONL API. Both have
an editor-style dark workbench, semantic PSI/SI trees, evidence views, keyboard
navigation and search. The parser exposes its linked native table/descriptor
registry, explicit standards/regional context, section-PID discovery and optional
extra PIDs. An offline metadata index provides verified standard-level links.

This iteration used the assistant's **own Linux cloud computer only**. No owner
Windows PC, television or phone was accessed. The actual native Linux Qt and
Tauri/WebKitGTK applications have been built and exercised, including native
edit/export. Browser validation is separately labeled and never substituted for
a native-runtime claim.

## Verified current behavior

- 25 engine tests: source preservation, analysis failure reset, exact PAT→PMT
  binding, snapshot inspection cutoff, regional text, extension validation,
  export exclusivity/cleanup, framing and regular-file input guards.
- 9 protocol/reference tests: ATSC and ISDB fixtures; DVB-S/S2/T/T2/C delivery
  parameters; private PDS isolation, nondefault PID discovery and unknown bytes.
- 4 HTTP bridge tests and 10 live Chromium/native-engine tests, including backend
  termination, keyboard/tree interaction, historical snapshots and responsive layout.
- 4 compiled native Qt tests: real workflows, search, literal untrusted text and
  tooltips, no remote image fetches, and failure-state cleanup.
- 2 Rust native-shell allowlist tests. Native GTK source selection, save/export,
  independent readback, overwrite-warning cancellation and backend-death flows
  were also checked in the actual application.
- Both workbenches carry the selected packet cutoff into inspection. A historical
  view cannot silently assemble a later sibling section.

Total automated test cases above: **54**. See [cloud validation](VALIDATION_CLOUD.md),
[native Tauri evidence](NATIVE_TAURI_VALIDATION.md) and [test commands](../tests/README.md).
These are local cloud results; check the PR's latest CI commit separately.

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
- Exact field-to-byte selection highlighting and persistent layout customization
  remain future work. Unknown private syntax is retained, never invented.
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
