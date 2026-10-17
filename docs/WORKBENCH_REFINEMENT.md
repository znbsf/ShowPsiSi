# Workbench refinement — 2026-10-17

## Scope

This iteration follows six user findings: missing packaged application identity,
light/dark chrome, numeric PID order, misaligned explorer labels, service metadata,
logical multi-section cards and unlabeled arrival distributions.

- One original packet/tree SVG generates seven PNG sizes and a multi-frame ICO.
  Qt resources, Windows PE icon resources, Tauri configuration and Linux desktop
  metadata use the same artwork. Packaging validates embedded resource links,
  dimensions and bytes rather than trusting filenames.
- Both UIs provide persistent light/dark themes, meaningful focus/selection and
  aligned numeric identifiers. Windows Qt uses supported DWM caption attributes;
  Linux/macOS native decorations remain window-manager owned.
- PID sorting is numeric. Logical tables retain PID, TID, extension, version,
  current/next and generation evidence, with expandable raw section records.
  CRC filtering is in the table toolbar. Filtered-out invalid evidence remains
  available and counted; missing and mixed-validity states are not conflated.
- Services show actual LCN candidates/conflicts, SDT type name and code, PAT-bound
  PMT PID and classified audio/video PIDs. Unknown PMT differs from decoded PMT
  with no audio/video components. Private stream identifiers require namespace,
  descriptor or registration evidence. See [protocol scope](PROTOCOL_COVERAGE.md).
- Arrival strips have ticks and units. Without a supplied bitrate they show packet
  positions, explicitly without a measured clock. Supplied-bitrate elapsed time
  is an estimate, not PCR or wall time. These changes do not add PCR reconstruction.

## Validation and review

All development used the assistant's own Linux cloud environment.

- Strict native gate: 176 tests passed, zero skips: engine30, service metadata15,
  section12, protocol43, SDK6, HTTP6, cancellation17, MCP17, portable25, icons5.
- Dual-theme contrast: 5 static regressions passed, resolving CSS cascade and QML
  theme expressions separately. Review found genuine light control-border failures;
  both UIs now meet the unchanged 3:1 control and 4.5:1 text gates on actual states.
- Web: 31 real-engine sandboxed Chromium tests passed, including immediate theme
  contrast, keyboard behavior, metadata, 101 logical-table pagination and timing
  provenance. Browser results do not establish native Tauri/WebView2 acceptance.
- Qt: 37 compiled functional checks and 6 resource relocation checks passed.
  The final expanded-table count correction was retested in the full Qt suite.
  No hosted result is claimed before its exact source revision passes.
- Parent visually inspected dark/light layouts and actual media-PID fixtures.
- Native Linux XCB/software-rendered Qt was exercised on the cloud desktop:
  theme switch, service fields, two-section SDT expansion and exact second-section
  selection/merged provenance passed. Close returned zero with empty stderr.
  Xfwm retained its own blue caption and the cloud dock used a fallback icon;
  packaged resource correctness is separate from a desktop shell's icon cache.
- Independent review caught and fixed private 0x81 stream misclassification,
  duplicate LCN evidence causing a semantic false diff, and incomplete Windows
  icon-group verification. Negative tests retain these failure cases.

Windows DWM appearance, Explorer icon display and native Windows/macOS desktop
interaction remain unverified until run on those platforms. Windows CI compilation
and offscreen regression evidence must not be presented as manual GUI acceptance.
No installer or formal release is implied by a CI portable archive.
