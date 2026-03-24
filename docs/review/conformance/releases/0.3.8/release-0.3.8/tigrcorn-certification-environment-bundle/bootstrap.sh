#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[certification,dev]"
python - <<'PY'
import aioquic, h2, websockets, wsproto
print('certification deps OK')
PY
