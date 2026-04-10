#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

python tools/cert/profile_bundles.py
python tools/cert/default_audits.py
python tools/cert/policy_surface.py
python tools/cert/quic_surface.py
python tools/cert/origin_contract.py
python tools/cert/observability_surface.py
python tools/cert/negative_surface.py
python tools/cert/governance_surface.py
python tools/cert/release_auto.py
python tools/govchk.py scan
python -m compileall -q src benchmarks tools
python -m pytest -q \
  tests/test_default_audits.py \
  tests/test_phase4_quic_surface.py \
  tests/test_phase5_origin_contract.py \
  tests/test_phase6_observability_surface.py \
  tests/test_phase7_negative_certification.py \
  tests/test_phase9f2_logging_exporter_closure.py \
  tests/test_phase3_policy_surface.py \
  tests/test_phase3_strict_rfc_surface.py \
  tests/test_phase7_flag_surface_truth_reconciliation.py \
  tests/test_release_gates.py \
  tests/test_phase2_cli_config_surface.py \
  tests/test_documentation_reconciliation.py \
  tests/test_config_matrix_pytest.py \
  tests/test_profile_resolution.py \
  tests/test_p8_gov.py \
  tests/test_p8_sf.py \
  tests/test_p9_auto.py

python tools/cert/status.py
