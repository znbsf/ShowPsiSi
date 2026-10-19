# Protocol metadata presentation

Qt and Web present engine-owned NorDig, AIT/UNT and DSM-CC source cards in the
existing Metadata inspector. NorDig needs no activation switch. The shared
`workbench.protocolCards` formatter performs no protocol parsing, receiver
selection, URL fetching or application execution.

## Cards and navigation

- Cards preserve country/list alternatives, attributes, unresolved/unsupported
  states and original object/relationship evidence. Text is plain text in both UIs.
- Twenty cards are shown per page, with explicit total and Previous/Next controls.
  Paging resets when the inspected section, revision or cutoff changes. Keyboard
  focus stays on the chosen direction until that control reaches its boundary.
- Formatting is lazy per page, with a bounded relation index. Large summaries do
  not discard evidence; source references page after 100 rendered rows.
- `protocolCardSources` preserves original locators, analysis revision and cutoff.
  Exact highlights require a core-verified range; unsupported locators provide
  section evidence instead of guessed field offsets.
- Source actions reuse the six inspector views. Back restores the origin metadata
  page, disclosure, scroll, source-action focus, table selection, history and
  snapshot/filter context without replacing independent topology selection.
- NorDig simulcast declarations and PAT/PMT/AIT carriage cards retain source
  identity and unresolved semantics. Complete/incomplete DSM-CC module cards
  preserve the core's hash-or-null result at the selected cutoff.

## Short headers and independent XML input

The standards chooser exposes **J.94 (2016) System B**. Shared row/header/history
formatters label absent MPEG long-header fields **not carried**, with no invented
version, extension, section number or expected-section count. Exact observations
remain separate from descriptor-revised `query_cable_oob` assembly; the inspector
does not claim a synchronized complete cable lineup.

The separate [DVB-I workspace](DVB_I_UI.md) has document/hash identity and source
navigation without fabricated TS fields. Its XML parsing remains in the core.

## Tests and limits

`test_protocol_presentation.py`, `test_qt_protocol_cards.py`,
`test_dvbi_presentation.py`, `test_qt_dvbi.py` and `test_web_ui.py` cover real-core
cards, hostile labels, paging/focus, exact source jumps, Back restoration,
malformed/unsupported evidence, short headers, both themes and revision isolation.
Use the [combined test commands](../tests/README.md#protocol-source-navigation).
Offscreen Qt and Chromium results do not establish Windows/WebView2 desktop,
GPU, RF reception, receiver policy or standard-wide conformance.
