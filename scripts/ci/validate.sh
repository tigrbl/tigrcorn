#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

python tools/cert/profile_bundles.py
python tools/cert/default_audits.py
python tools/cert/policy_surface.py
python tools/cert/quic_surface.py
python -m compileall -q src benchmarks tools
python -m unittest \
  tests.test_default_audits \
  tests.test_phase4_quic_surface \
  tests.test_phase3_policy_surface \
  tests.test_phase3_strict_rfc_surface \
  tests.test_phase7_flag_surface_truth_reconciliation \
  tests.test_release_gates \
  tests.test_phase2_cli_config_surface \
  tests.test_documentation_reconciliation \
  tests.test_config_matrix_pytest \
  tests.test_profile_resolution

python tools/cert/status.py
