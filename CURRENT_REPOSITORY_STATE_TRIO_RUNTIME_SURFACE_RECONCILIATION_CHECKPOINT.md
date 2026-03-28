> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Current Repository State — Trio Runtime Surface Reconciliation Checkpoint

## Scope of this checkpoint

This checkpoint resolves the public `trio` runtime surface **honestly** by taking the de-scope path.

What changed:

- `trio` is no longer advertised by the public CLI runtime selector
- config validation no longer accepts `runtime=trio`
- config validation no longer accepts `worker_class=trio`
- the runtime compatibility matrix now lists only supported runtimes
- flag-surface / contract / covering-array artifacts now match the descoped runtime surface
- current-state and package-review docs now explicitly say that `trio` is not supported in this checkpoint

## Decision

This checkpoint takes **Option B: de-scope**.

That means the honest supported runtime contract is now:

- `auto`
- `asyncio`
- `uvloop`

`trio` is deliberately **not** advertised as supported until it is wired end to end through the server core, workers, supervision, and embedding surface.

## Files reconciled

Primary code files:

- `src/tigrcorn/constants.py`
- `src/tigrcorn/cli.py`
- `src/tigrcorn/config/normalize.py`
- `src/tigrcorn/config/validate.py`
- `src/tigrcorn/server/bootstrap.py`

Primary artifact / documentation files:

- `docs/review/conformance/cli_flag_surface.json`
- `docs/review/conformance/flag_contracts.json`
- `docs/review/conformance/flag_covering_array.json`
- `docs/review/conformance/phase1_surface_parity_checkpoint.current.json`
- `docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json`
- `docs/review/conformance/phase4_advanced_delivery/runtime_compatibility_matrix.json`
- `docs/review/conformance/phase4_advanced_protocol_delivery/runtime_compatibility_matrix.json`
- `CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md`

Validation/tests:

- `tests/test_phase4_advanced_protocol_delivery_checkpoint.py`
- `tests/test_trio_runtime_surface_reconciliation_checkpoint.py`

## Validation completed

All validation below was run against this updated repository state.

- `python -m compileall -q src benchmarks tools` → passed
- `evaluate_release_gates('.')` → passed
- `evaluate_release_gates(... strict_target ...)` → passed
- `evaluate_promotion_target('.')` → passed
- targeted pytest bundle → **37 passed, 0 failed**

Targeted pytest files:

- `tests/test_phase1_surface_parity_checkpoint.py`
- `tests/test_phase2_cli_config_surface.py`
- `tests/test_phase4_advanced_protocol_delivery_checkpoint.py`
- `tests/test_trio_runtime_surface_reconciliation_checkpoint.py`
- `tests/test_phase8_promotion_targets.py`
- `tests/test_release_gates.py`

## Current honest status

Within the repository’s **current declared authoritative / strict / promotion model**:

- authoritative boundary: green
- strict target boundary: green
- promotion target: green

What this checkpoint does **not** claim:

- it does **not** implement a real `trio` server core
- it does **not** expand the certification boundary
- it does **not** newly certify any broader feature/RFC program beyond the repository’s current declared model

## Exit-criteria result

Step 2 exit criterion is satisfied via the de-scope path:

- `--runtime trio` no longer appears as supported
- runtime matrices and validation allowlists no longer advertise it
- flag contracts and public operator artifacts match the live parser/runtime surface
