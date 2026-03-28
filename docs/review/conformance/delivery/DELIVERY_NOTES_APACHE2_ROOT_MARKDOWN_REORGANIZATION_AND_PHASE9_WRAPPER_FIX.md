# Delivery notes — Apache 2.0 migration, root Markdown reorganization, and Phase 9 wrapper fix

This maintenance update applies three repository-level changes requested for the promoted `0.3.9` package.

## What changed

- the repository license was changed from MIT to Apache License 2.0
- packaging metadata in `pyproject.toml` was updated to publish the Apache Software License classifier and include the `LICENSE` file in built artifacts
- root-level current-state, delivery-note, and RFC-status Markdown clutter was moved under `docs/review/conformance/`
- canonical pointer paths were updated to the new locations
- the Phase 9 release-checkpoint regeneration path was hardened so rerunning `tools/create_phase9i_release_assembly_checkpoint.py` and the Step 9 promotion overlay does not fail on brittle Markdown section replacement logic
- the canonical current-state record now explicitly includes the **Canonical current-state chain** section required by the normalization checks

## Canonical documentation locations

- current repository state: `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- current-state chain: `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- delivery notes archive: `docs/review/conformance/delivery/`
- RFC and conformance reports: `docs/review/conformance/reports/`

## Validation performed

- `PYTHONPATH=src python tools/create_phase9i_release_assembly_checkpoint.py`
- `PYTHONPATH=src pytest -q tests/test_phase9i_release_assembly_checkpoint.py tests/test_release_gates.py tests/test_documentation_reconciliation.py tests/test_documentation_truth_normalization_checkpoint.py tests/test_certification_environment_freeze.py tests/test_aioquic_adapter_preflight.py`
- `python tools/govchk.py scan`

## Result

- the Phase 9 certification/documentation regression targeted by this maintenance update is fixed
- the certification/documentation/governance verification slice listed above is green (`25 passed`)
- the root Markdown layout is normalized so the repository root no longer carries current-state, delivery-note, and RFC-report clutter
- the canonical promoted-state documentation continues to report the package as certifiably fully RFC compliant and certifiably fully featured under the repository's defined certification boundary and promoted release root

## Honest environmental note

In this container, `tools/run_phase9_release_workflow.py` still halts at the certification-environment gate because the external optional dependency `aioquic` is not installed locally. That halt is the intended safety behavior of the wrapper, and the repository now records it honestly rather than masking it.
