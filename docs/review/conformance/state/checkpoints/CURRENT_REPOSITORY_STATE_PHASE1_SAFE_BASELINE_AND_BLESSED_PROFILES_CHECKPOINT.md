> Historical checkpoint note: this file is retained as a mutable working-tree checkpoint for provenance and handoff. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` for the current package-wide truth.

# Phase 1 safe baseline and blessed profiles checkpoint

This checkpoint records the mutable Phase 1 deployment-profile work completed in the current working tree.

Completed in this checkpoint:

- added the canonical profile registry in `src/tigrcorn/config/profiles.py`
- wired profile selection and effective-default resolution through `build_config_from_sources()` and `build_config()`
- added the generated profile artifacts:
  - `profiles/default.profile.json`
  - `profiles/strict-h1-origin.profile.json`
  - `profiles/strict-h2-origin.profile.json`
  - `profiles/strict-h3-edge.profile.json`
  - `profiles/strict-mtls-origin.profile.json`
  - `profiles/static-origin.profile.json`
- added generated operator/conformance docs:
  - `docs/ops/profiles.md`
  - `docs/conformance/profile_bundles.md`
  - `docs/conformance/profile_bundles.json`
- updated CI to regenerate profile bundles before validation
- promoted the Phase 1 deployment-profile claim rows to implemented `TC-PROFILE-*` entries in `docs/review/conformance/claims_registry.json`

Current honesty statement:

- the package still evaluates as **certifiably fully RFC compliant under the authoritative certification boundary**
- the canonical `0.3.9` release root still evaluates as **strict-target certifiably fully RFC compliant** and **certifiably fully featured**
- this checkpoint does **not** by itself regenerate the frozen `0.3.9` release root with the new Phase 1 mutable profile artifacts

Local validation used for this checkpoint:

- `python tools/cert/profile_bundles.py`
- `python -m unittest tests.test_profile_resolution`
- `python -m unittest tests.test_release_gates tests.test_phase2_cli_config_surface tests.test_documentation_reconciliation`
- `python -m compileall -q src tools`
- `python tools/cert/status.py`
