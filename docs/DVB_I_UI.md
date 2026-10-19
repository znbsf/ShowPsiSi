# Local DVB-I XML workspace

The Web frontend has an explicit **Input kind** selector for the retained
transport-stream workspace and an independent local DVB-I XML workspace. The
XML workspace is a read-only metadata inspector for the bounded profile in
[DVB_I_API.md](DVB_I_API.md), not a DVB-I receiver or full schema validator.

## Session and navigation

- Import a local UTF-8 file with **Open XML** or an entered path, then **Import
  XML**. The profile is explicitly ETSI TS 103 770 V1.2.1. Import reports that
  asynchronous cancellation is unavailable. It never calls TS cancellation.
- Successful imports replace only the XML document. Failed reads, XML/security
  errors and stale expected revisions retain the previous document. The loaded
  path/revision/hash remain visible separately from the proposed input path.
- Switching input kinds retains TS search, selected object/section, snapshot,
  topology and inspection context; XML search, selection and inspection remain
  independent. XML mode does not display TS PID navigation, CRC, packet history,
  TS editing/export controls or the TS status footer.
- The left explorer identifies the original file and its coverage/diagnostics.
  The central tree follows only the core's parent IDs. Arrow keys move focus,
  Left/Right fold or enter, and Enter/Space select. Ctrl/Cmd+K focuses the active
  workspace's search. Alt+Left follows the active workspace's source history.
  Saved TS splitter widths are retained across XML-mode resizes. Reset layout
  and splitter keyboard controls are TS-only and hidden in XML mode; the XML
  panes use responsive widths. The existing TS-only UI-agent action vocabulary
  rejects actions while XML is active instead of changing hidden TS state.
- Same-name services retain separate declared IDs. LCN table alternatives show
  declared region references and a stable XML element identity; absent region
  declarations remain explicit. All attributes, announced
  alternatives, unknowns and source references remain available. There is no
  service-name join, implicit regional/list selection or URL fetching.

## Bounded results and exact sources

Semantic pages contain at most 500 nodes. **Load next objects** merges exact
node IDs without duplicates. Search explicitly covers loaded objects only and
keeps matching ancestors. Source-reference internals such as SHA hashes, line
numbers and byte offsets are not mistaken for semantic search values. Tree
branches and source lists initially display 100 entries with explicit more
controls. Back history retains at most 100 navigation states.

Each source action carries the document revision, SHA-256 and opaque element
ID. The shared resolver checks all three plus namespace-expanded path and
location. Attribute highlights require the exact expanded attribute name from
the inspected element. A missing attribute produces an explicit element
fallback; a foreign revision/hash/path is rejected without a highlight.

The element view separates XML-normalized direct text from original file
source. **Original XML** shows the core's bounded original UTF-8 page and marks
only the opening element character. HTML display normalizes line breaks; the
adjacent **Original hex** view retains exact original bytes. UTF-16 display
indices are not byte offsets and no attribute byte span is claimed. Source
pages are 4096 bytes, with Previous/Next and Element start navigation. The
left element navigator pages 100 child summaries, includes parent navigation,
and permits unknown extensions or raw-only unsupported namespaces to be
inspected without a semantic node.

A replacement import supersedes old queries and source reads. Epoch checks
prevent delayed results from changing the new document. Query/inspect errors
have explicit retry controls; disconnect disables backend actions while
retaining cached evidence. The runtime never parses XML in JavaScript.

## Reproducible validation

- `test_dvbi_presentation.py`: six real-core shared-helper tests, including
  511-node pagination/loaded-only search, unknown nested references, exact
  attribute matching, fallback and revision/hash/path/location rejection.
- `test_cloud_preview.py`: real JSONL forwarding for import, query and inspect,
  static assets, origin/token boundaries and backend lifecycle.
- `test_web_ui.py`: real sandboxed Chromium with the native engine, covering
  independent TS/XML sessions, failed replacement, unsupported raw XML,
  Unicode/BOM/declaration/CRLF source positions, semantic/child/source paging,
  delayed old-query/new-import and old-source/new-source supersession,
  foreign-source rejection, retry/disconnect, keyboard focus and both themes.

## Qt frontend

The compiled Qt workspace uses the same document and source-reference helpers
with an independent input-kind switch, local path/Open/Import actions and an
explicit bounded-import/no-async-cancel label. Switching back retains the TS
session, including subsequent rescans. It uses 500-node semantic pages and
loaded-only search; raw XML child pages contain 200 summaries, original
XML/hex pages are 4 KiB, and Back retains 64 navigation states.

Qt offers Summary, Element, XML, Hex, JSON and Metadata document views. Source
activation checks revision, SHA and opaque element identity; character markers
are explicitly element-start locations. Qt's text widget normalizes displayed
line breaks, with the original byte page kept separate. Keyboard navigation
includes Ctrl+K, arrows/Return/Space, F6 and Alt+Left. Both themes and a compact
1000×680 layout have dedicated interaction checks.

`test_qt_dvbi.py` exercises all fixture objects/source references, 511-node
paging, 405-child unknown XML, rejected DTD replacement, Unicode/BOM/CRLF,
loading ownership, retry/stale/disconnect behavior and TS restoration/rescan.

Run the [Qt and browser gates](../tests/README.md#protocol-source-navigation)
against matching production inputs. Offscreen Qt and Chromium checks do not
establish native Windows Qt/WebView2 interaction, GPU behavior or receiver
conformance.
