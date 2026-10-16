# Workbench UI/UX review

Reviewed 2026-10-16 UTC in the Linux cloud workspace. No owner-computer access. This review inspected actual application screenshots and implementation; it does not claim Windows runtime or user acceptance.

## Evidence and findings

- Qt baseline: `docs/images/qt-workbench.png` (1440 × 900). Selected service, decoded hierarchy, source evidence and occurrence timeline are visible. The central list has substantial unused width, while permanently visible hex reduces tree height. Secondary text and values are unusually small. Sidebar families lack counts in this baseline image.
- Web baseline: `artifacts/web-ui-tests/test_real_analysis_and_selection.png` (1440 × 1000). Clear record columns, local search, selected-row state, tree indent guides and inspection tabs already establish useful hierarchy. Long descriptor headings visibly extend beyond the inspector edge. The center occupies approximately 815 pixels while the inspector has 440 pixels; technical content needs more of the available width. Default descriptor branches are closed, so selecting a service does not immediately reveal its name/provider fields.
- Source inspection: web uses resizable pane columns, explicit focus-visible styling and responsive rules. The original tree uses `min-width: max-content`, causing horizontal overflow, and 10px field typography. Qt already uses SplitView, keyboard tree navigation and semantic identifier formatting; these are foundations to retain.

## Official references actually inspected

Official documentation and the linked screenshots were opened and inspected, rather than relying on product names or assumed appearances.

1. [Wireshark main window](https://www.wireshark.org/docs/wsug_html_chunked/ChUseMainWindowSection.html) and [packet details](https://www.wireshark.org/docs/wsug_html_chunked/ChUsePacketDetailsPaneSection.html). [Screenshot inspected](https://www.wireshark.org/docs/wsug_html_chunked/images/ws-details-pane.png). The tree uses compact protocol summaries, expandable payload groups and explicit generated-field/link distinctions. Its record selection drives details and bytes. Map this to section selection → semantic SI hierarchy → authoritative bytes, with consistent version/PID context. Retain left/right expand/parent keyboard behavior. Field-to-byte highlighting is an aspirational follow-on requiring reliable byte ranges; this review does not claim ShowPsiSi implements it.

2. [VS Code workbench and tree navigation](https://code.visualstudio.com/docs/editing/getting-started/userinterface). [Screenshot inspected](https://code.visualstudio.com/assets/docs/editing/userinterface/hero.png). Distinct explorer, content tabs, lower panel and slim status bar make the workspace understandable. Indent guides and path context clarify nesting; tree search supports matching without losing navigation context. Map to compact table-family navigation, resizable detail workspace, stable selected-section context and visible keyboard focus. Do not add decorative activity icons with no functioning view.

3. [Chrome DevTools Properties](https://developer.chrome.com/docs/devtools/dom/properties). [Screenshot inspected](https://developer.chrome.com/static/docs/devtools/dom/properties/image/elements-properties-6e2e946a2f506.png). The property panel separates label/value semantics, supports name/value filtering and collapsible groups, and gives the selected object an independent detailed view. Map to readable SI field/value rows, contextual descriptor groups and local search. Unlike generic DOM inspection, unavailable protocol values must remain explicit rather than silently disappearing.

## Initial targeted changes and acceptance checks (20:18 UTC)

| Priority | Target | Acceptance evidence still needed |
| --- | --- | --- |
| High | Default inspector around 520px at 1440px, with usable splitters | New screenshot and actual resize interaction; long descriptor names fully available |
| High | Structure / Hex / XML tabs in both frontends | Same selected section/PID/version across all tabs; raw text remains authoritative |
| High | At least 11px tree values, semantic label/value styling, wrapping or deliberate ellipsis with full text available | Inspect expanded long/private descriptors and native SDK nodes |
| High | Open the selected service's meaningful descriptor; collapse verbose headers/source metadata | Selection immediately shows useful payload without an overwhelming fully expanded tree |
| Medium | Family counts, acronym explanations, selected-family and selected-record distinction | Empty and populated families; keyboard focus visibly differs from selection |
| Medium | Local tree search preserves ancestor context and distinguishes no matches | Find a deeply nested field/value and clear the filter without losing context |
| Medium | Narrow-window stability | Check 1000px desktop and compact web widths with long source paths and filters |

At the initial review, both implementation owners acknowledged the high-priority findings and reported corresponding changes underway. The fresh-render review below supersedes that pending visual status. Baseline screenshots cannot validate newer code. Existing empty center space is not itself a defect; the actionable issue is allocating width away from overflowing technical content.

## Fresh-render review, 20:23 UTC

Independently opened the regenerated `docs/images/qt-workbench.png`, `docs/images/web-workbench.png` and `docs/images/web-references.png` with image inspection. No checkpoint-blocking visual defect found in these views.

**Visually passed in the fresh screenshots:**

- Qt uses separate Structure / Hex / XML views; raw hex no longer consumes the default tree's vertical space. The wider inspector shows the selected service name, provider and type immediately. Long private-descriptor labels fit in the observed view. Family counts and native-decoder context are visible.
- Web inspector is wider and tree text more readable. The selected service descriptor is expanded; observed field names and values remain inside the panel. Selection, tab, search and ancestry cues remain distinct.
- References view explicitly calls mappings standard-level and includes edition, access and conformance caveats. This is appropriate disclosure rather than a misleading standards-compliance badge.

**Reported functional evidence, not independently rerun by this reviewer:** the validation owner reports eight live-engine web tests passed, including 1100/900/520px viewport checks with no horizontal overflow and labels fitting; two native Qt tests passed. A screenshot alone does not verify tab context preservation, full keyboard behavior, filter semantics or every long value.

**Remaining polish, not blockers for the checkpoint:**

- Qt still has less discoverable list structure than the web table: no equivalent visible column headings or list/tree search in the screenshot. Keep this as a later parity improvement rather than expanding the current checkpoint.
- Web's expanded service descriptor presents technical metadata and raw bytes ahead of later sibling descriptors. This is accurate, but deeper trees could benefit from payload-first ordering or collapsible descriptor metadata. The current vertical scroll is legitimate and not horizontal clipping.
- Field-to-byte highlighting, persistent layout customization and user visual acceptance remain unverified or unimplemented; do not describe them as delivered.
- The original Qt baseline image path has now been overwritten with the fresh render. The earlier findings above describe the image inspected at 20:18 UTC, not the current file contents. The web baseline remains separately identified above.

## Follow-up parity and safety loop

Qt record and ancestry-preserving field/value search have now been implemented, including Ctrl+K, Escape and retained selection. Native tests also check literal hostile stream text, plain tooltip rendering and no image fetches. Both workbenches pass the selected historical cutoff into inspection; the native tree cannot silently use later sibling sections. Browser/native-shell disconnection handling disables unavailable backend actions rather than leaving an endless loading state. These extend, rather than retroactively alter, the visual checkpoint above.
