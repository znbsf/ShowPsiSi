# Protocol test contract

The supported subsets and exclusions are in [protocol coverage](PROTOCOL_COVERAGE.md#current-protocol-extension-support).
Tests assert application behavior and evidence preservation, not RF reception,
media playback, HbbTV execution, firmware installation or receiver certification.

## Required invariants

1. Pin the standard edition, input framing, namespace and fixture provenance.
   SDK registry entries or catalogue previews do not establish complete support.
2. Parse in the shared C++ engine. Keep validity, semantic projection and original
   evidence separate; frontends must not reconstruct binary protocol facts.
3. Exercise positive and negative inputs through the production JSONL/MCP core:
   malformed lengths, CRC, unknown namespaces, identity conflicts, incomplete and
   reused generations, cutoffs, same-packet ordering and bounded resources.
4. Preserve original bytes and exact source locators. Failed replacement and
   stale replies must not mix documents or analysis revisions. Signalled URLs,
   applications and firmware are inert metadata.
5. Test semantic consumers and both frontends: paging, keyboard focus, both themes,
   exact source jumps, Back restoration, session replacement and existing export
   behavior. A screenshot alone is not functional verification.
6. Rebuild and run combined gates after integration. Production binaries exclude
   cancellation seams; the separately gated helper covers those tests. Missing
   binaries, zero tests and unexpected skips fail the strict runner.

## Suite map

| Scope | Main tests |
| --- | --- |
| NorDig namespaces, lists, declarations and topology | `test_nordig.py`, `test_topology.py`, `test_protocol_coverage.py` |
| SCTE EAS/splice fields and byte-preserving export | `test_scte_extensions.py`, `test_protocol_coverage.py` |
| AIT/UNT summaries and PAT/PMT carriage | `test_application_signalling.py`, `test_application_summaries.py`, `test_application_carriage.py` |
| DSM-CC cards, epochs, blocks and complete-only hashes | `test_dsmcc_summaries.py`, `test_dsmcc_reconstruction.py` |
| J.94 context, section fields and bounded revision query | `test_cable_oob.py` |
| Local DVB-I input, security and independent document identity | `test_dvbi.py`, `test_dvbi_presentation.py`, `test_qt_dvbi.py` |
| Shared cards and frontend source navigation | `test_protocol_presentation.py`, `test_qt_protocol_cards.py`, `test_web_ui.py` |

## Reproduction

Prepare the documented matching SDK and build both native targets. With the
production core, helper, API/reference files and tests from one source revision:

```sh
export SHOWPSISI_CORE="$PWD/build/bin/showpsisi-core"
export SHOWPSISI_TEST_CORE="$PWD/build/bin/showpsisi-core-test"
python scripts/ci/windows_native_checks.py --engine --artifacts artifacts/protocol-engine
python scripts/ci/windows_native_checks.py --qt --artifacts artifacts/protocol-qt
python -m unittest discover -s tests -p test_web_ui.py -v
python -m unittest discover -s tests -p test_cloud_preview.py -v
python -m unittest discover -s tests -p test_ui_contrast.py -v
```

The strict runner's historical filename does not identify the host platform.
Use the correct native executable suffix on Windows. Browser tests retain the
Chromium sandbox. See [build instructions](../README.md#构建与测试),
[test setup](../tests/README.md) and [CI contracts](CI_TEST_CONTRACT.md).

Keep per-run source/SDK identities, commands, results and failure diagnostics in
ignored test-output directories. Do not share mutable build outputs across
concurrent runs. Only small licensed/synthetic inputs and reproducible tests
belong in the source tree. The separately sourced optional French recording may
be absent with its documented skip; that run makes no real-recording claim.

## Acceptance boundary

Exact-revision Linux/Windows core, Qt and browser gates remain distinct. Offscreen
Qt is not native desktop/GPU acceptance; Chromium is not Tauri/WebView2. Package
runtime, dependency/source notices, clean-Windows installation and update handoff
have separate [Windows acceptance gates](WINDOWS_APPLOCAL_ACCEPTANCE.md).
Successful synthetic cases do not certify a broadcaster, receiver or whole edition.
