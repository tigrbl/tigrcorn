# Certification environment freeze

This checkpoint freezes the certification-environment installation contract for the strict release workflow and preserved certification bundle.

Canonical sources:

- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/delivery/DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`
- `.github/workflows/phase9-certification-release.yml`
- `tools/run_phase9_release_workflow.py`

## Purpose

The goal of this document is to make the release-workflow environment contract explicit and stable:

- how the certification environment is installed
- which extras are mandatory
- which imports must succeed before Phase 9 scripts run
- where the preserved bundle lives
- whether the **current observed local environment** is ready

The workflow contract is frozen even when the current editing environment is not fully ready.

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

| Item | Value |
|---|---|
| status | `environment_contract_frozen_but_not_ready` |
| required install command | `python -m pip install -e ".[certification,dev]"` |
| required extras | `certification, dev` |
| required imports | `aioquic, h2, websockets, wsproto` |
| required imports ready | `False` |
| missing imports | `aioquic` |
| python minor version | `3.11` |
| python version ready | `True` |
| supported release workflow versions | `3.11, 3.12` |
| environment ready for release workflow | `False` |
| release root | `docs/review/conformance/releases/0.3.9/release-0.3.9` |
| bundle root | `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle` |
| workflow path | `.github/workflows/phase9-certification-release.yml` |
| wrapper path | `tools/run_phase9_release_workflow.py` |

## Interpretation

This checkpoint records two different facts:

1. the **authoritative release-workflow contract** is frozen
2. the **currently observed local environment** may still be non-ready

At this checkpoint, the frozen contract is explicit, but the observed environment still reports a missing `aioquic` import. That is an honest status report, not a contradiction.

## What this checkpoint changes

- makes the strict release-workflow installation contract explicit
- records the observed environment snapshot in a preserved certification bundle
- ties the release workflow and local wrapper to the same install/import expectations
- removes ambiguity about which extras and imports are mandatory before Phase 9 release scripts run

## What this checkpoint does not mean

This freeze does **not** by itself widen the product boundary, close unrelated strict-target blockers, or replace the canonical current-state/promotion docs.

Use:

- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`

for promotion and current-state truth.
