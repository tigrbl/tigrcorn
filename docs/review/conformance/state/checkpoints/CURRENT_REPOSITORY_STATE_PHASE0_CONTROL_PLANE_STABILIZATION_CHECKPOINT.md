# Current repository state Phase 0 control-plane stabilization checkpoint

This checkpoint records the mutable working-tree stabilization pass that prepared the repository for a trustworthy GitHub control plane without widening the certified package boundary.

## What changed

- hardened default operator posture:
  - `connect_policy=deny`
  - `early_data_policy=deny`
  - `include_server_header=False`
  - `enable_h2c=False`
- removed reliance on a static shared QUIC default secret by randomizing listener secrets at runtime when they are not explicitly configured
- hardened `evaluate_release_gates()` so blocked or pending matrix metadata now fails closed
- added mutable GitHub control-plane scaffolding under:
  - `.github/workflows/`
  - `.github/actions/`
  - `scripts/ci/`
  - `tools/cert/`
  - `docs/governance/`
  - `docs/conformance/`

## Validation snapshot

Targeted local validation in this working tree:

- `python -m unittest tests.test_release_gates tests.test_phase2_cli_config_surface tests.test_documentation_reconciliation tests.test_config_matrix_pytest` -> `OK`
- `python tools/cert/status.py` -> authoritative release gates `passed=true`, strict release gates `passed=true`, promotion target `passed=true`

## Honest current state

Under `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, the package remains certifiably fully RFC compliant.

Under `docs/review/conformance/releases/0.3.9/release-0.3.9/`, the package remains strict-target certifiably fully RFC compliant and certifiably fully featured.

The GitHub governance rollout is only partially complete from this working tree alone:

- local workflow, script, and policy files now exist
- remote rulesets, environment protections, and repository settings still require GitHub-side activation
