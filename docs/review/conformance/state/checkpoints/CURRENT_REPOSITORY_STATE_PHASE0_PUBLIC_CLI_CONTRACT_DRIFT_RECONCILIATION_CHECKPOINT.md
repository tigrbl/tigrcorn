# Current repository state — Phase 0 public CLI contract drift reconciliation checkpoint

This checkpoint completes **Phase 0 — fix repo contract drift** for the current tigrcorn repository snapshot.

## Scope completed

The public CLI/API surface drift around the old `tigrcorn.cli.serve_import_string` patch seam is now reconciled.

The current CLI implementation is config-driven:

- `tigrcorn.cli.main()` parses arguments
- `tigrcorn.cli.main()` builds a `ServerConfig` with `build_config_from_namespace(...)`
- `tigrcorn.cli.main()` invokes `run_config(config)`

The import-string convenience coroutine remains part of the supported Python API surface in `tigrcorn.api.serve_import_string()`. It is **not** a supported `tigrcorn.cli` module-level patch target.

## What changed

- CLI public-surface regression tests now patch `tigrcorn.cli.run_config` and assert against the constructed `ServerConfig`
- the stale `tigrcorn.cli.serve_import_string` patch target has been removed from the public CLI regression tests
- `src/tigrcorn/cli.py` now documents the config-driven CLI handoff explicitly in `main()`
- `docs/review/conformance/reports/RFC_PUBLIC_API_CLI_QUIC_MTLS_VERIFICATION.md` now describes the real CLI forwarding path truthfully

## Files changed in this checkpoint

- `src/tigrcorn/cli.py`
- `tests/test_public_api_cli_mtls_surface.py`
- `tests/test_public_api_tls_cipher_surface.py`
- `docs/review/conformance/reports/RFC_PUBLIC_API_CLI_QUIC_MTLS_VERIFICATION.md`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/phase0_public_cli_contract_drift_reconciliation.current.json`
- `docs/review/conformance/state/checkpoints/CURRENT_REPOSITORY_STATE_PHASE0_PUBLIC_CLI_CONTRACT_DRIFT_RECONCILIATION_CHECKPOINT.md`

## Validation completed

Validation was re-run against this checkpoint using the local repository snapshot.

- `python -m compileall -q src benchmarks tools`
- `PYTHONPATH=src pytest -q tests/test_public_api_cli_mtls_surface.py tests/test_public_api_tls_cipher_surface.py`
- `PYTHONPATH=src python -c "from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target; ..."`

Results from this checkpoint:

- targeted public CLI/API regression tests: **passed**
- `evaluate_release_gates('.')`: **passed**
- `evaluate_release_gates(... strict_target ...)`: **passed**
- `evaluate_promotion_target('.')`: **passed**

## Honest repository-state note

This checkpoint fixes the Phase 0 public-surface drift and preserves the existing canonical 0.3.9 release-gate posture.

Repository state after this checkpoint:

- under the current canonical 0.3.9 certification boundary, the package remains **certifiably fully RFC compliant**
- under the current canonical 0.3.9 release root, the package remains **certifiably fully featured**
- against the broader `tigrcorn_unified_policy_matrix.md` target, the package is **not yet complete** because later phases remain open for static/pathsend, additional H1/H2/WS/TLS operator surfaces, lifecycle/embedder publication, and governance normalization

Phase 0 is complete. Later phases are still required for the broader unified-policy target.
