#!/usr/bin/env bash
# Run from any directory; all paths remain within this checkout.
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/make_fixture.py
python -m unittest discover -s tests -p test_engine.py -v
python -m unittest discover -s tests -p test_topology.py -v
python -m unittest discover -s tests -p test_topology_presentation.py -v
python -m unittest discover -s tests -p test_signal_metadata.py -v
python -m unittest discover -s tests -p test_satellite_metadata.py -v
python -m unittest discover -s tests -p test_section_evidence.py -v
python -m unittest discover -s tests -p test_protocol_coverage.py -v
python -m unittest discover -s tests -p test_application_signalling.py -v
python -m unittest discover -s tests -p test_application_summaries.py -v
python -m unittest discover -s tests -p test_application_carriage.py -v
python -m unittest discover -s tests -p test_dsmcc_summaries.py -v
python -m unittest discover -s tests -p test_dsmcc_reconstruction.py -v
python -m unittest discover -s tests -p test_nordig.py -v
python -m unittest discover -s tests -p test_scte_extensions.py -v
python -m unittest discover -s tests -p test_cable_oob.py -v
python -m unittest discover -s tests -p test_dvbi.py -v
python -m unittest discover -s tests -p test_dvbi_presentation.py -v
python -m unittest discover -s tests -p test_sdk_migration.py -v
python -m unittest discover -s tests -p test_cancellation.py -v
python -m unittest discover -s tests -p test_mcp_cancellation.py -v
python -m unittest discover -s tests -p test_cloud_preview.py -v
python -m unittest discover -s tests -p test_qt_ui.py -v
python -m unittest discover -s tests -p test_protocol_presentation.py -v
python -m unittest discover -s tests -p test_qt_protocol_cards.py -v

python -m unittest discover -s tests -p test_qt_topology.py -v
python -m unittest discover -s tests -p test_qt_dvbi.py -v
if [[ "${SHOWPSISI_BROWSER_TESTS:-0}" == 1 ]]; then
  python -m unittest discover -s tests -p test_web_ui.py -v
fi
