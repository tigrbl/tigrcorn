# Certification environment bundle

This bundle freezes the release-workflow installation contract for the strict-promotion certification path.

Required bootstrap commands:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[certification,dev]"
python - <<'PY'
import aioquic, h2, websockets, wsproto
print('certification deps OK')
PY
```

Observed Python minor version: `3.11`

Observed required-import readiness: `False`

Observed missing imports: `aioquic`

Release workflow path: `.github/workflows/phase9-certification-release.yml`

Checkpoint wrapper path: `tools/run_phase9_release_workflow.py`
