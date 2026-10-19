# Signal Topology workbench integration

Development-only work on `feat/signal-topology`; this document does not establish
Windows native interaction, release readiness, or complete protocol coverage.
The engine contract and adapter limitations are in [TOPOLOGY_API.md](TOPOLOGY_API.md).

## Shared presentation

`ui/tauri/web/workbench.js` is consumed by Web and Qt. It formats engine-returned
identities and states, searches already loaded objects, preserves ancestors,
pages sibling presentation, merges response pages by opaque IDs, and collects
all node and incoming/outgoing relation evidence. Compact row identities use
ONID / TSID / SID / PID and supplied ATSC channel numbers; full explanations and
opaque linkage identities remain available in inspector details. It does not parse protocol
bytes, infer a standard from a label, or join objects by name.

`resolveTopologyEvidence` validates the exact section ID, analysis revision,
inclusive cutoff and returned table identity. Exact field/container highlighting
requires the matching opaque engine anchor. The Structure tree contains a
section-local Source evidence anchors group before potentially large native
structures. It exposes the engine locator and its section byte range. Without
a supported anchor, the UI reports section-only fallback. Invalid/out-of-bounds
ranges are never highlighted. Merged scope does not reuse a section field
highlight as if it were a merged-table address.

## Web interaction

- Central tab order is Services / Topology / Tables / EPG / Issues / Changes.
  Existing left PID/table navigation still activates Tables.
- Topology has independent object selection, keyboard focus, search, expansion,
  evidence activation and return history. Arrow/type-ahead navigation does not
  inspect sources; Enter/Space or a row click selects an object.
- The object inspector exposes identities, incoming/outgoing relationships,
  attributes, unknowns and every available source assertion. Source activation
  reuses Structure / Hex / XML / Decoded / Metadata / References.
- Source reads carry immutable cutoff and analysis revision. Older asynchronous
  responses cannot replace a newer object or snapshot. Rescan resets cross-
  revision state; failed reads retain a visible error and explicit retry.
- Show in Tables reveals an exact source section only when its cutoff matches
  the workspace. Different-cutoff evidence remains inspectable on the right;
  there is no implicit snapshot mutation. Back restores the topology context.
- Comparison A/B sides offer Topology at A/B. That query and its source inspection
  keep the main workspace cutoff unchanged and provide a return to Changes.
- The initial request loads at most 500 objects. A visible Load next objects
  action retrieves subsequent deterministic pages. Search explicitly covers
  loaded objects only until all pages are fetched. Sibling rendering starts at
  100 and provides Show more child objects; parents remain present.

## Qt interaction

Qt uses the same central semantic tree and shared formatting/locator helpers,
with independent keyboard focus and object selection. All supplied wire-source
references are accessible through its virtualized source list. Matched field,
container and section-only precision are explicit; Hex selects only an engine-
verified source range. The existing six inspection views remain available.

Same-cutoff Tables reveal returns to the object context. Comparison A/B entry
and return keep the main snapshot unchanged, and related-section navigation
keeps the evidence cutoff while clearly downgrading to section-only precision.
Compact tab wrapping preserves the existing Changes layout threshold. Catalog
provenance is separate from inspectable wire evidence.

Qt-focused tests are in `tests/test_qt_topology.py`; final compiled/offscreen
results are recorded separately from actual native desktop interaction. The
shared/browser checks below do not certify Qt native windows.

## Reproducible checks and current evidence boundary

With the current feature core built, set `SHOWPSISI_CORE` explicitly before:

```
python -m unittest discover -s tests -p test_topology_presentation.py -v
python -m unittest discover -s tests -p test_web_ui.py -k topology -v
python -m unittest discover -s tests -p test_ui_contrast.py -v
```

The presentation suite requires Node.js and generates real wire fixtures for the
native core. Ten tests passed locally on 2026-10-19: three adapter families and
ISDB profile labels, ancestor-aware search, exact real field bytes, container/
section fallback, revision/cutoff/identity rejection, invalid ranges, complete
relationship evidence, compact/full identity formatting, paged merging and
explicit sibling paging. The six existing authored-color contrast tests and JavaScript syntax checks also passed.

The full Chromium integration suite passed **46/46** on the cloud desktop on
2026-10-19, including eight topology scenarios. These cover all six inspector
views and all sources, back/reveal, five standards profiles, both themes,
keyboard/widths, delayed/stale responses/rescan, mismatch and missing-anchor
rejection, read failure/retry, comparison-scoped entry, reverse-order pending
A/B queries, 601-object pagination and plain-text handling of broadcast names.
The long-tree case verifies nonzero scroll, search, selection, expansion and
actual focus restoration through source → Tables → Back. Real DVB-S2/C/T delivery
declarations and two co-located satellite candidates retain descriptor-container
precision, explicit uncertainty and separate catalog provenance.
Existing editing/export, timeline, cancellation, layout and Services regressions
also passed. The six cloud-preview bridge tests passed against the real core.

A restricted shell initially failed Chromium socket setup; its escalation also
failed before browser startup. The supported [cloud desktop wrapper route](CLOUD_DEVELOPMENT.md#cloud-desktop-launch-fallback-verified-2026-10-16)
then ran the same Playwright suite with Chromium sandboxing enabled. Fresh logs,
exit status and screenshots are under ignored `artifacts/topology-web/` and
`artifacts/web-ui-tests/`. These are actual Chromium plus native-engine tests,
not a Tauri runtime or Windows WebView2 validation. Actual Windows WebView2/Qt
interaction and release acceptance remain separate gates.
