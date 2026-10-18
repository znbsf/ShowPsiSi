# UI/UX refresh history (2026-10-18)

The initial family/column layouts below were superseded by the PR #13 rebase.
Current behavior and native interaction results are recorded in [STATUS](STATUS.md)
and [UI agent diagnostics](UI_AGENT_DEBUG.md). The retained refresh PNGs are local
historical artifacts and are not published.

This record covers the workbench improvements requested after the UI/UX review of
2026-10-18. It is a working record: it states what changed, the evidence that
exists, and what is deliberately deferred or unverified. It does not claim hosted
CI acceptance, native WebView2 interaction, macOS behaviour or installer
verification.

Base revision at the start of this iteration: `6e9df85` (working tree clean).
Development and verification environment: this Windows machine with the
already-built `.deps`/`build` SDK tree, the real `build/bin/showpsisi-core.exe`
engine, and the real `samples/generated/lab.ts` fixture (178,000 packets).

## 1. Findings driving this iteration

From the review, with the evidence that established them:

| # | Finding | Evidence |
| --- | --- | --- |
| F1 | Invalid Extra-PIDs feedback appears only in the far bottom status bar; measured 799 px away from the offending field | live Chromium/Edge capture + `verticalGapPx` measurement; `ui/tauri/web/app.js` `notice()` |
| F2 | The `Changes` mode inspector shows a generic "Select a service, table, programme or issue" empty state while the record list is replaced by comparison controls | live capture; `app.js` `renderInspector()` + `changeTab("Changes")` |
| F3 | The occurrence-density strip has no scale and no marker for the current snapshot position; A/B selection needs raw packet numbers | live DOM measurement (`hasAxisLabels: false`); `renderTimeline()` |
| F4 | Typography is not a scale: 8 px, 9 px and 10 px labels coexist with the declared 12 px field text | live computed-style histogram (8 px ×6, 9 px ×18, 10 px ×118, 11 px ×27) |
| F5 | Colour is not tokenised: 12 `:root` variables versus 95 distinct authored hex values in web CSS (Qt: 25) | repository scan |
| F6 | The two frontends drift: table-family order, statistics presentation, record rows (web has column headers, Qt does not), inspector metadata wording and control labels differ | `app.js` curated order vs `Main.qml` alphabetical sort; screenshots |
| F7 | Scan progress has no visual affordance in the web workbench (Qt has a 2 px indeterminate bar) | `Main.qml` `ProgressBar`; web `render()` |
| F8 | Both frontends show a small share of sub-11 px text that is below the project's own declared floor | see F4 |

## 2. Changes in this iteration

Accepted scope (implemented here) and deferrals are listed in section 5.

### Web workbench (`ui/tauri/web`)

- W1 (F1): field-level validation feedback for Extra PIDs. An inline message
  element is rendered next to the field, the input carries `aria-invalid` and
  `aria-describedby`, focus stays on the field, and the existing live-region
  status message is retained so screen-reader and status-bar behaviour does not
  regress.
- W2 (F2): mode-aware inspector empty state. In `Changes` mode the inspector
  explains the comparison workflow (A/B cutoffs, per-change evidence buttons,
  `Use snapshot` semantics) instead of instructing the user to select a record
  that is not on screen. Evidence loading into the inspector is unchanged.
- W3 (F3): the density strip becomes a keyboard-reachable snapshot position
  control (`role="slider"`, one tab stop, Arrow/Home/End) with start/middle/end
  packet ticks, a visible current-position cursor, an inner bar showing the
  invalid share of each bin, and pointer selection of a bin. Positioning the
  workbench this way is what the comparison presets consume: the A/B dropdowns
  already offer `Current snapshot · packet N`, start, latest and every captured
  transition, so no separate range-selection affordance was added.
- W4 (F4/F8): typography tokens `--font-xs`/`--font-sm`/`--font-md` with a 10 px
  floor; every authored 8 px or 9 px label moves to 10 px.
- W5 (F5): text and state colours move to named role tokens
  (`--label-text`, `--value-text`, `--changed-text`, `--changed-strong`,
  `--warn-text`, `--private-text`, `--density`, `--danger-text`, `--input-bg`).
  Near-duplicate secondary-text shades and the two different field-value colours
  collapse onto one label/value pair; the contrast-tested tokens keep their exact
  values so `tests/test_ui_contrast.py` measures the same pairs. Distinct surface
  and border shades stay local to their component: flattening them without a
  per-state visual review would erase deliberate hover/raised/selection steps.
- W6 (F7): a 2 px indeterminate scan progress bar, matching the native
  workbench, disabled under `prefers-reduced-motion: reduce`.
- W7 (F6): the `Tables` record view gains a column header
  (`TABLE · PID · VERSION · SECTION · REPEATS · OK`) and a matching grid, so both
  frontends present the same scanning structure for the densest list.

### Qt workbench (`ui/qt/Main.qml`)

- Q1 (F6): table families use the same curated protocol order as the web
  workbench (PAT, PMT, SDT, EIT, NIT, CAT, BAT, TDT, TOT, then remaining names
  alphabetically) and gain the same `Private / other` pseudo-family with the
  equivalent predicate.
- Q2 (F6): `Services` and `Tables` record lists gain column headers and
  column-aligned rows (LCN / service-provider / PMT PID / group, and
  kind / PID-version-section / bytes / state), matching the web table while
  keeping row heights, selection identity and every existing `objectName`.
- Q3 (F3): the section-occurrence strip gains a current-position cursor and
  pointer selection of a bin, matching the web behaviour.
- Q4 (F6): the standards selector reads `Standards: …` like the web control.

### Records, tests and documentation

- R1: this document, plus pointers from `docs/UI_UX_REVIEW.md` and `docs/STATUS.md`.
- R2: `tests/test_web_ui.py` gains assertions for the inline field error, the
  comparison-mode inspector state and the timeline slider contract.
- R3: the Qt self-check script gains a `refresh` mode that verifies the new
  column headers, family order and timeline cursor through the real application;
  `tests/test_qt_ui.py` runs it.

## 3. Verification record

All entries below were run on 2026-10-18 on this Windows machine with the
workspace SDK tree, against `samples/generated/lab.ts` (178,000 packets) and the
locally built `showpsisi-core.exe` / `showpsisi-qt.exe` (rebuilt from this
working tree; not a hosted CI result).

### 3.1 Native Qt self-check (`SHOWPSISI_SCRIPT=refresh`)

Command shape (offscreen, software backend, isolated settings):

```powershell
$env:QT_QPA_PLATFORM='offscreen'; $env:QT_QUICK_BACKEND='software'
$env:SHOWPSISI_SCRIPT='refresh'; $env:SHOWPSISI_TEST_RESULT='...\qt-refresh.json'
$env:SHOWPSISI_SCREENSHOT='...\qt-refresh.png'
build\bin\showpsisi-qt.exe
```

Observed `passed: true` with ten checks true:

| Check | What it exercises |
| --- | --- |
| `family_order` | Families start `All tables, PAT, PMT …` and end `Private / other` |
| `service_columns` / `table_columns_hidden` | Services header visible with real width, table header hidden |
| `table_columns` | Tables header visible after switching tab |
| `private_family` | `Private / other` filter selects exactly the unclassified rows |
| `bin_positions` | First bin maps to packet 0, last bin stays inside the stream |
| `bin_click` / `bin_click_snapshot` | Clicking bin 40 issues a real query and the workbench lands on packet 89,000 |
| `density_cursor` | Cursor visible and positioned inside the strip (x = 718.9 px) |
| `latest_restored` | The check restores the latest observed state afterwards |

Screenshots: `qt-refresh.png` (final state) and `qt-refresh.png.cursor.png`
(selected snapshot with the cursor) under `artifacts/analysis/`. The retained,
visually inspected copy of the selected-snapshot view is
[docs/images/qt-refresh.png](images/qt-refresh.png).

### 3.2 Native Qt smoke regression (`SHOWPSISI_SCRIPT=smoke`)

The existing smoke script still passes unchanged after the record-list and
timeline edits: `passed: true`, 6 services, 2,495 observations, all 11 search
checks true, `history_cutoff: true`, `references: 1`, rename preview, SI-only
export and the API dialog exercised. No QML diagnostic
(`ReferenceError`, `TypeError`, `Cannot assign`, `Unable to assign`,
`QQmlApplicationEngine failed`) appears in the runtime log — the CI gate rejects
those strings.

### 3.3 Native Qt unit-test subset

`tests/test_qt_ui.py` was run with `SHOWPSISI_QT` pointing at the rebuilt binary
for every case that does not need the opt-in cancellation helper:
`test_native_interaction_smoke`, `test_record_columns_family_order_and_density_cursor`,
`test_snapshot_comparison_and_evidence_cutoffs`,
`test_populated_compact_comparison_keyboard_and_controls`,
`test_stream_markup_is_literal_without_network_fetches`,
`test_layout_drag_keyboard_persistence_and_reset`,
`test_corrupt_layout_uses_safe_defaults`. Result: **7 tests, 22 s, OK**
(log in `artifacts/analysis/qt-subset.log`). The cancellation-helper cases were
not run because this tree was configured without
`-DSHOWPSISI_BUILD_CANCELLATION_TESTS=ON`.

Local-run note: the suite launcher only extends `LD_LIBRARY_PATH`, so on Windows
the Qt `bin` directory must be added to `PATH` (and `QT_QPA_FONTDIR` set) or the
application exits with `0xC0000135` and every case reports a missing result. That
is an environment gap in this local run, not a product regression; the hosted
workflow configures both explicitly.

### 3.4 Engine regression gate

`python -m unittest discover -s tests -p test_engine.py -v` → **30 tests, OK**
(real TSDuck engine, export/readback, MCP, snapshot diff, cancellation-free
paths). The presentation edits in this iteration do not touch `core/main.cpp`.

### 3.5 Web workbench, real engine in a real browser

`scripts/cloud_preview.py` served the exact web assets over the loopback bridge
to the real engine; system Edge (Chromium) was driven by Playwright. Eighteen
checks passed after the review corrections in section 6
(`artifacts/analysis/web-refresh.json`):

| Check | Observed |
| --- | --- |
| `inline_field_error` | Reason rendered beside the field, `aria-invalid=true`, `aria-describedby=extra-pids-error`, focus kept, footer live region still carries the message |
| `inline_error_clears` | Editing the value hides the field error again |
| `changes_inspector_state` | Comparison mode shows "Compare two observed states"; the old "Select a service…" instruction is gone |
| `change_evidence_still_loads` | Per-change evidence still loads the section into the inspector |
| `density_slider_contract` | `role=slider`, one tab stop, 80 bins, ticks `0 · 89,000 · 177,999 packets` |
| `bin_fill_painted` | A populated bin computes `rgb(111, 157, 215)` from `--density-fill`; the per-bin opacity is the separate `--density-alpha` |
| `invalid_marker_contained` | Every partial-invalid marker stays inside its own bin (width ≤ bin width, ≥ 3 px tall) |
| `bin_click_selects_packet` | Clicking bin 40 loads packet 90,126 (the proportional position for that bin) |
| `density_cursor_positioned` | 2 px cursor inside the strip at the selected bin |
| `keyboard_steps_advance` | Three consecutive ArrowRight presses: 90,126 → 92,379 → 94,632 → 96,886, strictly increasing |
| `slider_focus_retained` | `document.activeElement.id` is still `density` after the query re-render |
| `keyboard_end_home_bounds` | End → 177,999 = `aria-valuemax`; Home → 0 |
| `type_scale_floor` | Smallest rendered text is 10 px; no 8 px or 9 px label remains |
| `tables_column_header` | `TABLE · PID · VERSION · SECTION · REPEATS · OK` |
| `table_columns_aligned` | All four header cells and row cells share left edges and widths (delta 0 px) |
| `scan_progress_element` | `role=progressbar`, hidden when idle |
| `no_horizontal_overflow` | 1440 / 1000 / 520 px: `bodyScrollWidth == innerWidth` |
| `no_console_errors` | No page error or console error beyond the known favicon 404 |

Captures: `web-refresh-01-workbench.png` … `web-refresh-06-compact.png`. The
retained, visually inspected copy of the selected-snapshot view is
[docs/images/web-refresh.png](images/web-refresh.png).

The driver used for this run was an ad-hoc Node/Playwright script kept in the
ignored `artifacts/analysis/` directory, chosen because the Python `playwright`
package is unavailable here. Its checks are mirrored one-for-one by the committed
`tests/test_web_ui.py::test_refresh_field_error_comparison_state_and_density_slider`,
which is the reproducible form that CI runs.

### 3.6 Contrast and token regression

`python -m unittest discover -s tests -p test_ui_contrast.py -v` → 2/2 OK after
the same tokens were re-read from the changed CSS/QML. The test previously read
both files with the platform default encoding, which fails on a non-UTF-8
Windows locale; it now reads UTF-8 explicitly. No assertion was relaxed.

## 4. Boundaries and deliberately unverified items

- Windows WebView2 native window interaction, native open/save dialogs, macOS
  builds and installers remain outside this iteration's evidence, as before.
- `tests/test_web_ui.py` needs the Python `playwright` package. It is not
  installed in this workspace and the package network is unavailable here
  (a `pip download` attempt did not complete), so that suite is updated but was
  not executed locally. Browser evidence in this iteration comes from a real
  Chromium (system Edge) driving the real bridge and the real engine.
- Screen-reader behaviour is checked structurally (roles, names, states, one tab
  stop), not with assistive technology on a live desktop.
- Contrast remains a targeted token regression, not a full visual audit.
- The colour work consolidated text and state colours onto role tokens
  (95 → 77 authored values in the web stylesheet). The remaining values are
  surface, border and hover steps that differ per component on purpose;
  collapsing them without a per-state visual review would erase the
  raised/hover/selected hierarchy, so that is a follow-up rather than a
  mechanical substitution.
- Two parts of finding F6 are left deliberately different rather than being
  aligned. The statistics row (web metric tiles with per-metric captions versus
  the Qt single status line) and the inspector metadata wording (Qt spells out
  "Packet identifier" and "repeats" per the repository's acronym-explanation
  rule, while the narrower web header uses "PID" and "observations") serve their
  own available width; forcing one form would either drop the explanations or
  overflow the other workbench at 1000 px. Record columns, family order and
  control labels — the parts that mislead when they differ — are aligned.
- Qt's occurrence strip is pointer-only: it has a position cursor and bin
  selection, but no `slider` role or arrow-key contract, so keyboard users reach
  snapshots through the history chips and "Latest"/"Compare A / B". The web strip
  is keyboard-operable. This parity gap is recorded rather than claimed as done.

## 5. Explicitly deferred (with reasons)

| Item | Reason |
| --- | --- |
| Field-to-byte highlighting | Needs backend byte ranges for arbitrary SDK XML fields; descriptors already carry offsets, so a descriptor-level subset is the next step rather than part of this pass |
| Cross-navigation from PID/SID fields to the referenced section | Requires new backend query/index work; not a presentation-only change |
| EPG time grid, sortable columns, multi-select | Larger feature work; recorded as follow-up |
| File drag-and-drop | Needs a native shell (Tauri) file-drop path that the browser bridge cannot exercise |
| i18n / localisation | No `qsTr` or message catalogue exists; a separate, larger change |
| Full surface/border palette reduction | Needs a per-state visual review; see section 4 |
| Moving the QML test scaffolding out of the production file | Valuable but orthogonal to the user-visible review findings; recorded as follow-up |

## 6. Review corrections, 2026-10-18 (second pass)

An independent review of the working-tree diff found five defects in the web
timeline and table work. All five reproduce against the code as it was written,
and all five are now fixed with a guard that was itself negative-tested by
reintroducing the defect.

| # | Defect | Root cause | Fix | Guard that fails on it |
| --- | --- | --- | --- | --- |
| 1 | Populated bins rendered transparent | The fill colour token and the per-bin opacity custom property were both called `--density`; the inline number shadowed the token, so `background` received an invalid value | Fill colour is `--density-fill`; per-bin opacity is `--density-alpha` | `bin_fill_painted` (computed `background-color`) |
| 2 | A partial-invalid marker stretched across the whole strip | `.bin` was not a containing block; only the all-invalid variant had `position: relative`, so the marker positioned against `.bins` | Every `.bin` is `position: relative` | `invalid_marker_contained` (marker rect vs its own bin) |
| 3 | Keyboard stepping stalled and `End` stopped at 175,775 | Bin→packet used `i × packets / bins` while packet→bin used `p × (bins-1) / (packets-1)`; the round trip was not inverse (89,000 → 91,225 → 91,225) | One shared mapping over `[0, packets-1]` (`packetForBin` / `binForPacket`) used by clicks, the cursor and the keys | `keyboard_steps_advance`, `keyboard_end_home_bounds` |
| 4 | Slider lost focus after the first keyboard jump | Each snapshot query re-renders the strip and replaces the focused `#density`; focus was never restored, so later keys went to `body` | `renderTimeline` records whether the slider had focus and restores it after re-render | `slider_focus_retained` |
| 5 | Tables header and rows did not align | The header used the four-column Services grid while table rows stayed a flex row | `.service-head.tables` and `.record.tables` share one grid definition, with `.cell-count`/`.cell-state` alignment classes and a matching 2 px header border | `table_columns_aligned` |

### Negative-test evidence

Each guard was checked against the defect, not only against the fix. With the
defect reintroduced, the corresponding check reports a failure; the stylesheet and
script were restored byte-identically afterwards:

| Reintroduced defect | Observed result |
| --- | --- |
| 1 + 2 (shared `--density`, `.bin` unpositioned) | `bin_fill_painted`, `invalid_marker_contained` failed |
| 3 + 4 (old mapping, no focus restore) | `keyboard_steps_advance` failed (steps `90,126 → 92,379`, then stuck), `slider_focus_retained` failed (`activeElement.id` empty), `keyboard_end_home_bounds` failed |
| 5 (table grid rules removed) | `table_columns_aligned` failed (column 2 off by 102 px, column 3 by 65 px) |

### What the first pass got wrong

Two of these defects were visible in the retained first-pass screenshot — an
unpainted strip and a red line running along the bottom of the timeline — and were
misread as correct rendering. The checks behind that claim were too shallow: they
measured the marker's height but not its width or the bin fill colour, and the
keyboard check pressed a single key instead of a sequence. The guards above close
those specific gaps; the corrected capture replaces `docs/images/web-refresh.png`.

### Behaviour notes

- Selecting a bin (click or keys) now loads the proportional packet position for
  that bin, so bin 40 maps to packet 90,126 rather than the bin's start packet
  (89,000). `End` therefore reaches the declared maximum, and one key press always
  moves by at least one packet for streams with at least as many packets as bins.
- Empty-bin opacity is now `0.12` and the scale `0.35 + min(0.65, count/50)`,
  matching the Qt strip; the value only becomes visible now that the fill colour
  actually paints.
- The header now carries the same transparent 2 px left border as the records, so
  columns align exactly instead of being offset by the selection border.

No Qt source changed in this correction pass. The Qt build, `refresh` self-check
and the seven-test subset recorded in section 3 therefore still describe the
current `Main.qml`; the web workbench is the only surface affected by these five
defects.

## 7. Structure-tree parity and agent diagnostics (2026-10-18)

The follow-up working-tree change aligns Web branch/leaf/typed-value colors and
`▸`, `▾`, `·` glyphs with the existing Qt tree. Numeric SDK attributes retain
numeric styling instead of being flattened into strings. Private/invalid Web
labels use dotted underlines so their annotation does not replace the shared
name color. Tree layouts/data projections remain frontend-specific.

Both applications now have Save diagnostics and an explicitly enabled local UI
session. The [UI agent contract](UI_AGENT_DEBUG.md) documents real screenshots,
state/control geometry, semantic paths, bounded request traces and allowed
navigation. This pass changes Qt as well as Web; the previous section's
"No Qt source changed" statement applies only to that earlier correction pass.

Local validation uses HEAD `6e9df857f3a16dfa955635ec66da681f398fdfff` plus the
pre-existing dirty refresh patch and this follow-up, not the clean committed HEAD.
The 33-test Qt suite initially passed 30 tests; two required the missing
`showpsisi-core-test`, and a Python proxy emitted non-UTF-8 output under Windows.
After building the test-only target and setting fixture `PYTHONIOENCODING=utf-8`,
all three failed cases passed on a focused rerun. Production engine code was not
changed. Evidence: `artifacts/ui-agent-qt-tests.log`,
`artifacts/ui-agent-qt-rerun.log` and the per-case retained directories.

Browser validation used a hidden Chromium page with the real loopback engine:
typed rendered colors, collapsed/expanded/leaf glyphs, Left/Right/Down focus
navigation and search were checked. Screenshot and computed styles are retained
in `artifacts/review-20261018/tree-parity`. The temporary server and owned core
exited (core exit 0). A disconnected browser request logged Windows socket 10053
during cleanup; it was not a frontend assertion failure.

Qt offscreen and Windows Tauri/WebView2 diagnostic tests use fresh isolated
settings/profiles, actual production binaries and the real sample. They preserve
PNG, state, manifest and logs in `artifacts/ui-agent-tests`. Their scope includes
typed colors/glyphs, navigation, unsupported-action refusal and screenshot/state
selection correlation. Offscreen Qt is not physical Windows GPU validation;
browser checks are not a substitute for native Tauri evidence. No new hosted CI,
PR, merge or release is claimed by this local pass.

Final local results: both UI-agent integration cases passed with explicit Qt and
Tauri binaries (no skips), both contrast tests passed, and all six Windows Rust
unit tests passed. The final diagnostic tests also assert glyph colors and
focus-by-path, verify there are no captured frontend errors, and recheck the input
sample hash. See `artifacts/ui-agent-final-tests.log`,
`artifacts/ui-agent-rust-tests.log` and `artifacts/ui-agent-final-evidence.json`
for reports, binary SHA-256 values and final capture paths. Owned application,
engine and test-profile WebView2 processes were absent after cleanup.
