# Desktop workbench UX: standards-informed pass

Reviewed 2026-10-17 UTC, starting from `4d2635d`. Development and tests use the
assistant's Linux cloud workspace only. This is a bounded improvement to the
existing professional PSI/SI inspector, not a replacement design system or a
claim of WCAG conformance.

## What the references actually establish

There is no single universal “standard app UI”. These sources have different
scopes and are applied deliberately:

- [VS Code UX overview](https://code.visualstudio.com/api/ux-guidelines/overview)
  describes the editor's containers, views, scoped actions and contextual status.
  Its audience is extension authors. We adopt the existing explorer → records →
  inspector → history organization and local action scope, not decorative icons
  or a literal VS Code clone.
- [Fluent 2 layout](https://fluent2.microsoft.design/layout) uses a flexible
  four-unit spacing ramp with exceptions and emphasizes proximity and responsive
  grouping. We use 4/8/12/16 spacing where useful, 12px inspection text and compact
  28px tree rows. These sizes are our desktop design decisions, not universal
  accessibility requirements or mobile touch-target claims.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) supplies measurable web requirements:
  normal text contrast (1.4.3), non-text control/state contrast (1.4.11), keyboard
  operation (2.1.1), visible/non-obscured focus (2.4.7/2.4.11), target size with
  exceptions (2.5.8), and status messages (4.1.3). We test selected color pairs and
  interactions. Native Qt uses these as design targets, not a web certification.
- [WAI-APG tree pattern](https://www.w3.org/WAI/ARIA/apg/patterns/treeview/)
  specifies visible-node arrow navigation, expand/child and collapse/parent,
  Home/End, type-ahead and tree semantics. Our web inspection tree is focus-only:
  choosing a stream record selects evidence; moving within decoded fields does
  not pretend to select a different section. Tab enters/exits the composite once.
- [WAI-APG grid pattern](https://www.w3.org/WAI/ARIA/apg/patterns/grid/) describes
  interactive two-dimensional cell navigation. The current record view selects
  whole records and is not cell-editable. We retain its listbox model rather than
  assigning a grid role without implementing a grid keyboard contract.
- [Qt Accessible documentation](https://doc.qt.io/qt-6/qml-qtquick-accessible.html)
  distinguishes accessible names, descriptions and actions. The pinned Qt 6.7.3
  does not have newer QML `expandable`/`expanded` properties (introduced in 6.12).
  The native flattened ListView honestly exposes list items with depth and
  expanded/collapsed descriptions and press actions. It is not claimed as a
  complete native accessibility tree adapter.

## Evidence-backed gap plan, before editing

Inspected `Main.qml`, `app.js`, `style.css`, existing integration tests and the
actual `docs/images/{qt,web}-workbench.png` baseline images. Earlier screenshots
remain historical evidence for their recorded versions.

| Priority | Verified gap | Bounded change / check |
| --- | --- | --- |
| P1 | Every web field was a Tab stop; no tree roles or expansion states | One roving entry, declared tree/group/item semantics, state synchronization; real keyboard tests |
| P1 | Qt Right on an open branch did not enter its first child; delegate Tab stops could traverse many fields | List-level keyboard ownership, Home/End and child/parent behavior; real key-event smoke assertions |
| P1 | Keyboard focus depended on weak one-pixel borders or a fill resembling selection | Two-pixel focus outlines; separate selection/focus in native tree |
| P1 | Muted text failed 4.5:1 on selected surfaces; interactive input borders were much weaker than 3:1 | Stronger secondary-text/control-border tokens; keep decorative separators quiet; numeric regression |
| P2 | Inspection text was 11px with inconsistent compact spacing; shortcuts were largely implicit | 12px field text, 28px rows, visible local keyboard help; populated/narrow screenshots |
| P2 | A long web error was ellipsized in the footer | Wrapping error status, assertive live update, complete tooltip; narrow error layout check |

## Interaction contract and implementation boundaries

- Web: plain `div` treeitems contain their own `group`; disclosure is implemented
  explicitly, without overriding native `<summary>` semantics. Leaves never
  receive `aria-expanded`. Roles do not imply selection. The
  [ARIA-in-HTML summary rules](https://www.w3.org/TR/html-aria/#el-summary) prohibit
  changing the role of a summary belonging to details. An intermediate prototype
  violated that rule despite Chromium exposing its requested AX roles; it was
  replaced before acceptance. A real Chromium accessibility-tree regression now
  verifies the root treeitem's label, expanded state and contained group.
- Tab moves into one current visible node and then out of the tree. Arrow keys
  navigate only visible nodes. Right expands or enters a child; Left folds or
  returns to its parent. Home/End go to the first/last visible node. Web type-ahead
  matches visible labels; local search still preserves ancestor context.
- Enter from tree search moves to its current result; an empty search leaves
  focus in the search input. Clearing a query restores saved collapse state.
  Folding a branch cannot leave the roving entry hidden in its descendants.
- Qt keeps keyboard ownership at the virtualized ListView. Its row press action
  mirrors mouse activation, and descriptions include depth and disclosure state.
  Full screen-reader behavior still needs platform/assistive-technology testing.
- IDs, numeric formatting, raw hex/XML, source immutability, cutoff provenance,
  cancellation and comparison semantics are unchanged by these presentation edits.

## Targeted contrast evidence

`tests/test_ui_contrast.py` calculates sRGB relative luminance from actual authored
CSS/QML tokens. It checks normal text at **4.5:1** and the sampled focus/control
boundaries at **3:1**, including default/raised/selected backgrounds. Decorative
pane separators remain intentionally low contrast. Disabled controls are excluded
from these checks; this is not a test of all rendered pixels or all states.

Before: web secondary `#929eb0` against selected `#253b58` was **4.19:1**;
Qt secondary `#969696` against selected `#04395e` was **4.05:1**;
Qt string `#ce9178` against current-field `#37373d` was **4.47:1**.
After: secondary colors are `#a3afc0` / `#a3a3a3` (**5.12:1 / 4.75:1** on those selected backgrounds); native string values use
`#d6a089` (**5.21:1**); a dedicated `#7b8799` control-border token separates interactive
boundaries from passive panel dividers. Primary native button hover was also
corrected after its white label measured **4.16:1** on `#1684bb`.

## Verification

Validated on Linux with the compiled Qt 6.7.3 application and sandboxed Chromium
154, both using the real TSDuck-backed engine:

- **24/24 Qt integration tests passed**, including real Home/End, child/parent,
  disclosure and Tab-exit key events; cancellation and comparison tests retained.
- **26/26 browser integration tests passed, zero skips**, including the final
  valid treeitem/group DOM, repeated pointer/key disclosure, single Tab entry,
  filtered/empty focus states and Chromium accessibility-tree ownership.
- **2/2 authored-token contrast tests passed**. JavaScript syntax, Python
  compilation and `git diff --check` also passed.
- Six live browser captures compare 32px and 28px rows at 1440×900, 1000×680 and
  520×1000. The final 28px choice fits respectively **12, 6 and 5 complete rows**
  versus **11, 5 and 4** at 32px, with the same 12px text and focus outline.
  Compact inspector spacing retains provenance while recovering tree height.
- A real invalid-PID submission at 520px width verifies the complete error fits
  inside the footer, has assertive live status, and causes no horizontal overflow.

Retained, visually inspected screenshots:

| Surface | Normal | Compact / focus / error |
| --- | --- | --- |
| Compiled Qt | [1440×900](images/qt-ux-standards.png) | [1000×680](images/qt-ux-compact.png), [keyboard focus](images/qt-ux-keyboard-focus.png) |
| Chromium web frontend | [1440×900](images/web-ux-standards.png) | [1000×680](images/web-ux-compact.png), [520px error](images/web-ux-narrow-error.png) |

These web captures are not native Tauri acceptance. Qt is a real compiled
application rendered with the offscreen/software backend, not a mockup.
Reproduction commands are in [tests/README.md](../tests/README.md). Local run
artifacts include `artifacts/ux-standards/qt-final-tests.log`,
`artifacts/restore/web-aria-final.log`, and `artifacts/ux-standards/web/`
(metrics, six density captures and accessibility-tree JSON).

Remaining work: real screen-reader/AT validation, full zoom/text-scale and forced
colors audit, all-platform native dialogs, and true semantic field-to-byte mapping.
No screenshot or limited color test establishes these capabilities.
