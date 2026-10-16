# ShowPsiSi development

Read README.md, docs/STATUS.md, docs/ARCHITECTURE.md and docs/REQUIREMENTS_AUDIT.md first. For this iteration's cloud build/test route and known environment issues, read docs/CLOUD_DEVELOPMENT.md and docs/NATIVE_TAURI_VALIDATION.md. Protocol claims belong in docs/PROTOCOL_COVERAGE.md and must distinguish SDK support from tested application behavior.

The C++/TSDuck engine owns parsing, provenance, edit validation and export. Qt and Tauri consume the same JSONL API. Preserve evidence and explicit unknowns. Never infer private descriptor meaning from its tag alone.

Keep UI design editor-like: compact dark neutral surfaces, visible focus, semantic field colors, hexadecimal identifiers with correct widths, readable acronym explanations, and navigable trees. Both UIs must retain existing functionality. Do not substitute screenshots or mocked data for functional verification.

SDKs, generated files, samples and artifacts stay ignored. Tests should be reproducible without owner-machine paths. Document environment-specific validation boundaries rather than claiming a platform passed.
