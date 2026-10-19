# ShowPsiSi development

Read README.md, docs/STATUS.md, docs/ARCHITECTURE.md and docs/REQUIREMENTS_AUDIT.md first. For this iteration's cloud build/test route and known environment issues, read docs/CLOUD_DEVELOPMENT.md and docs/NATIVE_TAURI_VALIDATION.md. Protocol claims belong in docs/PROTOCOL_COVERAGE.md and must distinguish SDK support from tested application behavior.

The C++/TSDuck engine owns parsing, provenance, edit validation and export. Qt and Tauri consume the same JSONL API. Preserve evidence and explicit unknowns. Never infer private descriptor meaning from its tag alone.

Keep UI design editor-like: compact dark neutral surfaces, visible focus, semantic field colors, hexadecimal identifiers with correct widths, readable acronym explanations, and navigable trees. Both UIs must retain existing functionality. Do not substitute screenshots or mocked data for functional verification.

SDKs, generated files, samples and artifacts stay ignored. Tests should be reproducible without owner-machine paths. Document environment-specific validation boundaries rather than claiming a platform passed.

For scan lifecycle changes, read docs/ANALYSIS_CANCELLATION.md. Engine state remains single-owner; cancellation control may set only the matching analysis flag. Test-only gates must be compile-time excluded from the production binary. Do not infer successful Windows UI interaction from a compile artifact or offscreen test alone.

For delivery, interruption recovery and completion reporting, follow [docs/DELIVERY_RUNBOOK.md](docs/DELIVERY_RUNBOOK.md). Local tests alone are not delivery; resume from verified repository and hosted state within the user's authorized scope.

For CI completion, state ordering, isolation and failure-evidence contracts, read [docs/CI_TEST_CONTRACT.md](docs/CI_TEST_CONTRACT.md).

For Windows release work, read [release acceptance gates](docs/RELEASE_READINESS.md), [installer/runtime handling](docs/WINDOWS_INSTALLER.md), and [update-client trust and lifecycle](docs/UPDATES.md). Preserve exact source/artifact identity, explicit install consent, dependency review and active-export guards. A green CI run does not establish a clean Windows machine or publisher code-signing reputation.

For broadcast protocol increments, follow [the phased protocol test loop](docs/PROTOCOL_TEST_PLAN.md), [AIT/SSU inspection semantics](docs/APPLICATION_SIGNALLING.md), [DVB-I input boundaries](docs/DVB_I_INPUT_DESIGN.md), and [cable OOB edition/framing](docs/CABLE_OOB_INPUT_DESIGN.md). NorDig is decoded automatically in the existing DVB evidence path when its on-wire namespace is present; do not add a separate activation toggle. Regional/list selection is distinct from enabling the parser. Preserve public-spec edition, input framing, raw bytes, source identity and explicit unsupported cases. SDK registration, section assembly, semantic decoding and complete protocol support are separate claims. Keep new dependencies pinned and distribution-reviewed before the next package; never modify a frozen first-release candidate to hide a later feature dependency.
