# Certification environment freeze

This checkpoint freezes the certification-environment installation contract for the strict-promotion workflow.

## Required bootstrap

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

## Current recorded state

- python minor version: `3.11`
- python version ready for the release workflow: `True`
- required imports ready: `False`
- missing imports: `aioquic`
- environment ready for the release workflow: `False`
- release workflow path: `.github/workflows/phase9-certification-release.yml`
- wrapper path: `tools/run_phase9_release_workflow.py`
- preserved bundle root: `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle`

## What this checkpoint changes

- makes the strict-promotion installation contract explicit
- records the observed environment snapshot in a preserved certification bundle
- adds a release-workflow guard that fails when the required imports are missing
- adds a local wrapper that freezes the environment before invoking Phase 9 checkpoint scripts

## Honest current result

This update improves the package operationally, but it does **not** by itself make the package certifiably fully featured or strict-target fully RFC compliant. The remaining strict-target HTTP/3 evidence blockers still need to be closed separately.
