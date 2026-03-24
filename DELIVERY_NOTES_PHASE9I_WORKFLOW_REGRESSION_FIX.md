# Delivery notes — Phase 9I workflow regression fix

This checkpoint fixes the two CI regressions reported against the promoted `0.3.8` package.

Fixed regressions:

- rerunning `tools/create_phase9i_release_assembly_checkpoint.py` on an already promoted repository no longer rolls `docs/review/conformance/phase9i_release_assembly.current.json` back to a pre-promotion state
- the preserved certification-environment bundle and `docs/review/conformance/certification_environment_freeze.current.json` are now resynchronized during the Phase 9I assembly refresh path, so the status document no longer drifts from the release-root bundle after workflow regeneration

Implementation changes:

- `tools/create_phase9i_release_assembly_checkpoint.py`
  - detects the already-promoted canonical `0.3.8` state
  - reapplies the Step 9 promotion overlay when the repository is already promoted
  - rewrites certification-environment and aioquic-preflight status documents from the preserved release-root bundles before publishing current-state docs

Validation run for this fix:

- `python -m compileall -q src benchmarks tools`
- `PYTHONPATH=src pytest -q tests/test_phase9i_release_assembly_checkpoint.py tests/test_release_gates.py tests/test_certification_environment_freeze.py tests/test_aioquic_adapter_preflight.py`

Result:

- `16 passed`

The package in this checkpoint remains the promoted canonical `0.3.8` release and remains truthfully documented as certifiably fully featured and strict-target certifiably fully RFC compliant.
