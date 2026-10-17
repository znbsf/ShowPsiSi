# ShowPsiSi development

Read README.md, docs/STATUS.md, docs/ARCHITECTURE.md and docs/REQUIREMENTS_AUDIT.md first. For this iteration's cloud build/test route and known environment issues, read docs/CLOUD_DEVELOPMENT.md and docs/NATIVE_TAURI_VALIDATION.md. Protocol claims belong in docs/PROTOCOL_COVERAGE.md and must distinguish SDK support from tested application behavior.

The C++/TSDuck engine owns parsing, provenance, edit validation and export. Qt and Tauri consume the same JSONL API. Preserve evidence and explicit unknowns. Never infer private descriptor meaning from its tag alone.

Keep UI design editor-like: compact dark neutral surfaces, visible focus, semantic field colors, hexadecimal identifiers with correct widths, readable acronym explanations, and navigable trees. Both UIs must retain existing functionality. Do not substitute screenshots or mocked data for functional verification.

SDKs, generated files, samples and artifacts stay ignored. Tests should be reproducible without owner-machine paths. Document environment-specific validation boundaries rather than claiming a platform passed.

For scan lifecycle changes, read docs/ANALYSIS_CANCELLATION.md. Engine state remains single-owner; cancellation control may set only the matching analysis flag. Test-only gates must be compile-time excluded from the production binary. Do not infer successful Windows UI interaction from a compile artifact or offscreen test alone.

For delivery, interruption recovery and completion reporting, follow [docs/DELIVERY_RUNBOOK.md](docs/DELIVERY_RUNBOOK.md). Local tests alone are not delivery; resume from verified repository and hosted state within the user's authorized scope.

For CI completion, state ordering, isolation and failure-evidence contracts, read [docs/CI_TEST_CONTRACT.md](docs/CI_TEST_CONTRACT.md).
