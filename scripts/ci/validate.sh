#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

python tools/cert/profile_bundles.py
python -m compileall -q src benchmarks tools
python -m unittest \
  tests.test_release_gates \
  tests.test_phase2_cli_config_surface \
  tests.test_documentation_reconciliation \
  tests.test_config_matrix_pytest \
  tests.test_profile_resolution

python tools/cert/status.py
