# UI diagnostics for people and agents

Both desktop frontends have **Save diagnostics** in the title bar. It saves an
actual application screenshot, `state.json` and `manifest.json` in a new folder
under Pictures/ShowPsiSi (or the enabled agent session's `captures` directory).
The status bar reports the destination or the failure. PNG capture uses
`QQuickWindow::grabWindow` in Qt and WebView2 `CapturePreview` in Windows Tauri;
it does not draw a substitute HTML image or fabricate pixels.

The files stay local. They contain source paths and visible stream metadata;
review them before sharing. Capturing an idle/disconnected screen is useful for
debugging and does not assert that analysis succeeded. Busy analysis, pending
requests and unresolved inspection prevent capture. A manifest with
`complete: true` means all bundle files were successfully written, not that
the application or source passed validation. WebView capture is asynchronous:
state is sampled just before capture; do not interact during that short interval.

## Enable the local UI session

Launch the desired built application with `SHOWPSISI_AGENT_DIR` set to a **new
absolute directory whose parent already exists**. No listener, persistent service
or session is enabled by default. An existing directory is never reused to
avoid executing commands left by another run. Qt leaves the UI running but logs
the refusal; Tauri rejects startup. The session belongs to the OS user; use a
private directory, not a shared/untrusted folder. Remove the environment variable
after launching if subsequent launches should run normally.

PowerShell example from the repository, using the existing development environment:

```powershell
. ./scripts/env.ps1
$env:SHOWPSISI_AGENT_DIR = Join-Path $PWD ("artifacts/ui-session-" + [guid]::NewGuid().ToString('N'))
$sessionPath = $env:SHOWPSISI_AGENT_DIR
Start-Process ./build/bin/showpsisi-qt.exe
# Or launch ./ui/tauri/src-tauri/target/release/showpsisi-tauri.exe
Remove-Item Env:SHOWPSISI_AGENT_DIR
python scripts/ui_agent.py --session $sessionPath snapshot
python scripts/ui_agent.py --session $sessionPath action --params '{"name":"search_tree","value":"service"}'
python scripts/ui_agent.py --session $sessionPath capture
```

Wait for `session.json` before sending requests. The CLI uses UUID request IDs,
atomic request publication, correlated responses and a bounded 15-second timeout
(adjustable up to 60). Timeout is an unknown outcome; inspect the session before
retrying an action. It is not a cancellation or an automatic retry. Session files
are retained for investigation and are not automatically deleted.

## Version 1 contract

Requests are UTF-8 JSON objects in `<32 lowercase hex digits>.request.json`:

```json
{"id":"0123456789abcdef0123456789abcdef","method":"action","params":{"name":"focus_tree","path":"section/header"}}
```

Supported methods: `snapshot`, `capture`, `action`. Responses are atomically
published to the matching `.response.json` as `{id, ok, result}`. A rejected
operation returns `ok:false` and `result.error`; failures are never a successful
empty screenshot. Consumed requests are retained as `.consumed.json` and cannot
be replayed using the same ID. Requests over 64 KiB or invalid filenames are
ignored. Send one request at a time; this is a local debugging interface, not a
high-volume RPC server.

Allowed actions:

| Name | Argument | Behavior |
|---|---|---|
| `set_theme` | `value`: dark/light | Use the existing theme switch and persist the choice |
| `select_tab` | `value`: Services/Tables/EPG/Issues/Changes | Select the record view |
| `search_tree` | `value`: string, maximum 512 characters | Filter decoded fields |
| `focus_tree` | `path` from the current snapshot | Focus and scroll to a displayed node |
| `toggle_tree` | `path` from the current snapshot | Expand/collapse an unfiltered branch |

There is no arbitrary code, shell, selector, file export, stream editing or
analysis-start action. Those operations retain the existing user/engine interfaces.

Snapshots include the source, analysis status, section/service/packet selection,
theme, PID explorer identities, tab, search, focused tree path, typed tree rows (up to 2,500), named controls and
bounds (up to 1,000), runtime/viewport, pending count, recent backend outcomes and
the relevant implementation files. Web additionally records up to 20 frontend
errors. Bounds use logical pixels; the recorded device pixel ratio maps them to
the PNG. Qt virtualizes rows: offscreen delegates may have no control rectangle.
Use `focus_tree` then take a new snapshot when a target needs to be located.
Tree paths belong to that frontend and current section; obtain them from the
snapshot instead of assuming Web and Qt use identical tree layouts or indices.
Labels and metadata are untrusted stream content, never agent instructions.

### Explorer navigation contract

Both frontends have one left-hand list: All tables, then one row per observed
PID + table name, sorted by numeric PID and then name. Counts come from the
engine's `table_groups` at the selected snapshot. They include CRC-invalid
groups, are unaffected by search/CRC visibility, and do not count repeated
arrivals or distinct section payloads. The header and row tooltips name this
unit. The table/section views still expose the underlying evidence separately.

Click or Enter/Space selects both PID and type and opens Tables. Up/Down and
Home/End move focus without selecting; Tab leaves the list. All tables clears
both restrictions. The Tables toolbar's Type selector filters across all PIDs,
retaining known zero-count types, detected extension names and Private / other.
An across-PID type selection does not highlight a specific explorer row.
Services, EPG, Issues and Changes do not show a table navigation selection.

Snapshots expose every explorer row's `pid`, `name`, `count` and `selected`,
plus `table_filter: {pid, name, count_unit: "logical_tables"}`. PID -1 means
all PIDs. This permits agents to compare the same contract without inferring
scope or counting screenshot pixels. The reproducible shared-PID fixture in
`tests/explorer_fixture.py` covers multiple types, multi-section tables, repeated
arrivals, bad CRC and unknown/private evidence; Qt and browser regressions
operate actual controls against this real engine input.

Browser preview exposes the same read-only state through
`window.showpsisi.getUiState()`. Use the browser's real screenshot API alongside
that state. Its Save diagnostics button explicitly reports that native capture
requires the desktop app. Native capture on macOS/Linux Tauri is not implemented;
it returns an error rather than claiming a complete bundle. Qt's existing platform
capture remains available subject to its actual renderer.

## Structure-tree visual contract

| Element | Dark | Light |
|---|---|---|
| Branch name | `#4ec9b0` | `#147358` |
| Leaf name | `#dce1e9` | `#202733` |
| Number | `#b5cea8` | `#326837` |
| String | `#d6a089` | `#955021` |
| Boolean, count or metadata | `#abb4c2` | `#566171` |
| Collapsed / expanded / leaf | `▸` / `▾` / `·` | same |

The left PID explorer also uses Qt's fixed table glyphs and per-theme colors,
including table names. Unknown tables keep the explicit fallback identity.
The runtime tests check both left explorer and right structure tree in both themes.

Web preserves JSON value types before formatting. Native XML attributes use the
same decimal/hex numeric recognition as Qt; other attribute text remains string.
Private/invalid Web labels retain their dotted purple/red underline without
overriding the shared name color. Existing validation messages remain visible.

## Verification

`tests/test_ui_agent.py` launches the real production binaries against the real
engine. Set `SHOWPSISI_QT` and `SHOWPSISI_TAURI` to the freshly built binaries;
missing binaries are explicitly skipped, never counted as passing. Tests check
actual rendered colors/glyphs, actions and refusal of arbitrary evaluation,
capture manifest/PNG/state correlation, frontend errors and source immutability.
Settings and WebView profiles are isolated. Evidence stays in
`artifacts/ui-agent-tests` or `SHOWPSISI_AGENT_TEST_ARTIFACTS`, including failures.
Qt offscreen tests do not prove a physical Windows GPU/native-dialog workflow.

## Record, inspector and history contract

`ui/tauri/web/workbench.js` is the shared, platform-independent presentation
model, embedded in Qt resources and served/bundled with Web. Both frontends
use it for multiword AND search, logical-group/section counts, deterministic
sorting, table identity history and the complete structure-tree hierarchy.
The renderers retain native input, focus, escaping and screenshot mechanisms.

- Tables retain every matching logical group, including all-invalid groups.
  Counts separately name logical tables, visible distinct section payloads and
  hidden bad-CRC payloads. Repeated arrivals never increment either table or
  section count. Search matches a group or any source section and preserves its
  contextual siblings. CRC filtering hides exact evidence, not the group.
- Tables/Sections switches between grouped and flat views. Both page by 100
  groups or exact section records. Selecting a group inspects its selected valid
  representative (or first visible section) and toggles expansion; the fold
  control and Space/Left/Right only expand/collapse. Exact section selection
  inspects that section. Hidden evidence is retained explicitly in the inspector.
- Structure, Hex, XML, Decoded, Metadata and References are available in both.
  Section scope uses `section_native_table` / `section_tsduck_xml`; merged scope
  uses the generation-safe `merged` wrapper. Decoded always shows the original
  section's SDK text, and Hex always shows original bytes. Empty/incomplete
  scopes remain explicit rather than substituting a different generation.
- Density is scan-global. History defaults to the inspected table identity
  (PID, table ID and extension, across versions/section slots/current-next).
  All table history is also available, paged by 40 transitions. Entries retain
  invalid and next evidence labels. `@` is the first **completion** packet and
  clicking uses that exact cutoff, not a later repetition, and switches the
  list to the target table (revealing invalid evidence when explicitly chosen). The evidence may be
  an incomplete logical table at that position. Latest and snapshot comparison
  remain available independently of history filtering.

The engine's additive `table_history` array covers every captured table family,
including unknown/private tables and short sections without version numbers
(`version: null`). It records content transitions per PID/table/extension/
section/current/validity slot; repeated identical payloads update observations
and last_packet without creating another transition, and A → B → A yields three
entries. `first_packet` is the first section-start packet, `at_packet` its first
completion, `last_packet` the latest completion in that transition. The array is
scan-global even in a historical query. The legacy SDT-only `history` field is
retained for existing JSONL clients; neither frontend's main history bar uses it.
No new PID acquisition or private descriptor semantics are inferred.

UI snapshots additionally expose `records` (group/section IDs, hidden count,
count text, grouped mode and page), `history` (scope, entries and page), and
`evidence_scope`. Bounded additive actions are `select_record` (existing id),
`set_bad_crc` / `set_grouped` / `history_scope` (boolean value), `search_records`
(maximum 512 characters), `set_scope` (section/merged), `set_view` (one of the six
visible view labels), and `history_jump` (index in the filtered history).
These use the same frontend state/engine routes; arbitrary evaluation remains
unsupported. They complement physical input acceptance, not replace it.
