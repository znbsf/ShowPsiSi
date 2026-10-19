# Protocol metadata presentation

First UI increment, 2026-10-19: the existing Metadata inspector presents engine
NorDig lists and AIT/UNT application-signalling objects. No new top-level tab or
NorDig activation option is introduced. The shared `workbench.protocolCards`
formatter contains no protocol parser, device selection or URL execution.

Cards preserve separate country/list alternatives, application attributes,
resolution/unsupported states and original object/relationship evidence. Twenty
cards are shown per page, with explicit total and Previous/Next controls; the
page resets when the inspected section/revision/cutoff changes. Opaque graph and
section linkage IDs stay in expanded evidence rather than the compact summary.
All broadcast text remains plain text, escaped by Web and explicitly PlainText
in Qt. A bound index prevents quadratic relation filtering for large summaries.

Validation so far:

- Six shared-format tests, including real-engine NorDig and AIT summaries,
  pagination, hostile labels, invalid/unsupported states and no fabricated cards.
- Actual compiled Qt paging in dark and light themes, immutable synthetic input,
  source evidence and retained screenshots.
- Actual sandboxed Chromium paging, keyboard activation, both themes, evidence
  disclosure and section-switch reset, backed by the production C++ engine.
- Node syntax, Python compilation and diff checks passed.

Visual review found that Qt's existing sort could reorder equal-priority cards;
this increment uses stable filtered ordering and puts protocol cards adjacent
to their pager. A browser test initially toggled an already-open evidence panel
closed on the second theme; the test now observes disclosure state before
opening it. The original failure is retained in ignored test artifacts.

Evidence: `artifacts/protocol-ui/`, `artifacts/web-ui-tests/protocol-cards-*.png`.
These tests do not establish native Windows interaction. Full combined
regressions and independent review remain required after topology integration.
This increment exposes source evidence; clickable exact source jumps reuse the
separate topology contract in the next integration. DVB-I import UI and cable
short-header presentation remain separate follow-on work.

## Independent presentation review

After topology integration, review reproduced a Web keyboard-pager defect:
Next moved focus to Previous, so repeated Enter reversed direction. Focus now
stays on the chosen direction while enabled, moving to the other button only at
a page boundary. The real Chromium case traverses all four pages in both
directions and verifies actual focus. Eight shared protocol-card checks pass,
including malformed real NorDig descriptors with full original section, table,
revision and cutoff context. Formatting is lazy per displayed page: the
4096-object case formats 19 object cards plus the envelope instead of 4096
objects. All original data remains available through paging.

Five real-core DVB-I presentation checks validate independent revision/hash
identity, parent-preserving rows, 511-object page merging, all nested evidence
(including unknown extensions), attribute/element fallback and mismatch refusal.
These helpers do not parse XML; they are groundwork for the separate DVB-I UI,
not proof of completed XML workspace interaction.
