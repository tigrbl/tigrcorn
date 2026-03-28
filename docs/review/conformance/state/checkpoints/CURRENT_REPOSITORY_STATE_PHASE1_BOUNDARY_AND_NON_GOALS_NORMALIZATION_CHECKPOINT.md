# Current repository state — Phase 1 boundary and non-goals normalization checkpoint

This checkpoint completes **Phase 1 — normalize boundary and non-goals truth** for the current tigrcorn repository snapshot.

## Scope completed

The repository now has one canonical authoritative **in-bounds** statement and one canonical authoritative **out-of-bounds** statement.

The current package boundary is now explicitly frozen as a **T/P/A/D/R** boundary:

- **T — transport**
- **P — protocol**
- **A — application hosting**
- **D — delivery/origin behavior**
- **R — runtime/operator**

## What changed

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md` now states the canonical T/P/A/D/R in-bounds boundary directly
- `docs/review/conformance/BOUNDARY_NON_GOALS.md` now states the canonical out-of-bounds policy directly
- `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md` now tracks the remaining **in-bounds** post-promotion backlog instead of acting like an older strict-promotion planning document
- `README.md` now points to the same canonical in-bounds and out-of-bounds policy sources
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` now treats the canonical boundary/non-goals pair as the current package-governance truth and no longer treats the repository as operating under a competing dual-boundary current-claim model
- `docs/review/conformance/README.md`, `docs/review/conformance/CURRENT_STATE_CHAIN.md`, and `docs/review/conformance/current_state_chain.current.json` now point to the same canonical policy chain
- `docs/review/conformance/CERTIFICATION_POLICY_ALIGNMENT.md` now reflects the current green state and the new in-bounds / out-of-bounds policy split

## Explicitly governed non-goals

This checkpoint makes the following items explicit non-goals for the current package boundary:

- Trio runtime
- RFC 9218 prioritization
- RFC 9111 caching/freshness
- RFC 9530 digest fields
- RFC 9421 signatures
- JOSE / COSE
- HTTP parser/backend selection
- WebSocket backend/engine selection
- alternate app-interface pluggability such as ASGI2 / WSGI / RSGI selection
- broader loop/topology/task-engine pluggability families

## Files changed in this checkpoint

- `README.md`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`
- `docs/review/conformance/README.md`
- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`
- `docs/review/conformance/CERTIFICATION_POLICY_ALIGNMENT.md`
- `docs/review/conformance/STRICT_PROFILE_TARGET.md`
- `docs/review/conformance/state/checkpoints/CURRENT_REPOSITORY_STATE_PHASE1_BOUNDARY_AND_NON_GOALS_NORMALIZATION_CHECKPOINT.md`
- `docs/review/conformance/phase1_boundary_and_non_goals_normalization.current.json`

## Validation completed

Validation was re-run against this checkpoint using the local repository snapshot.

- `python -m compileall -q src benchmarks tools`
- `PYTHONPATH=src pytest -q tests/test_public_api_cli_mtls_surface.py tests/test_public_api_tls_cipher_surface.py tests/test_documentation_truth_normalization_checkpoint.py tests/test_certification_policy_alignment.py tests/test_documentation_reconciliation.py tests/test_dependency_declaration_reconciliation_checkpoint.py tests/test_trio_runtime_surface_reconciliation_checkpoint.py tests/test_rfc_applicability_and_competitor_status.py tests/test_phase9_implementation_plan.py tests/test_phase9a_promotion_contract_freeze.py`
- `PYTHONPATH=src python -c "from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target; ..."`

Results from this checkpoint:

- targeted documentation/governance/public-surface regression suite: **35 passed**
- `evaluate_release_gates('.')`: **passed**
- `evaluate_release_gates(... strict_target ...)`: **passed**
- `evaluate_promotion_target('.')`: **passed**

## Honest repository-state note

This checkpoint completes the Phase 1 governance/doc-chain normalization work and preserves the existing canonical `0.3.9` release-gate posture.

Repository state after this checkpoint:

- under the canonical `0.3.9` certification boundary, the package remains **certifiably fully RFC compliant**
- under the canonical `0.3.9` release root, the package remains **certifiably fully featured**
- against the broader `tigrcorn_unified_policy_matrix.md` target, the package is **not yet complete** because later in-bounds phases remain open for static/pathsend, additional H1/H2/WS/TLS operator surfaces, and lifecycle/embedder publication

Phase 1 is complete. Later in-bounds phases are still required for the broader unified-policy target.
