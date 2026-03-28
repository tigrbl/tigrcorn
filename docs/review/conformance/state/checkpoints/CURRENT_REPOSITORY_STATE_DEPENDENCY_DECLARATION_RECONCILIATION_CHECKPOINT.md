> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Current repository state — dependency declaration reconciliation checkpoint

This checkpoint aligns `pyproject.toml`, install documentation, optional dependency hints, and the current-state review documents with the package's surfaced optional feature paths.

## What changed

- declared explicit extras for YAML config loading, Brotli content coding, uvloop, trio, and the aggregated public optional feature bundle
- kept the certification workflow install contract at `.[certification,dev]`
- added installation guidance to `README.md` and `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md`
- updated Phase 4 example notes so they no longer imply that `trio` is publicly supported
- updated missing-dependency error messages to point at `tigrcorn[config-yaml]`, `tigrcorn[compression]`, and `tigrcorn[runtime-uvloop]`

## Honest current state

- the public runtime contract remains `auto`, `asyncio`, and `uvloop`
- `runtime-trio` is declared only as a reserved dependency path; it does **not** enable `--runtime trio`
- this checkpoint does **not** expand the RFC certification boundary
- under the repository's current authoritative / strict / promotion model, the package remains green after these packaging changes

## Validation performed

- `python -m compileall -q src benchmarks tools`
- `pytest -q tests/test_dependency_declaration_reconciliation_checkpoint.py tests/test_certification_environment_freeze.py tests/test_trio_runtime_surface_reconciliation_checkpoint.py`
- `evaluate_release_gates('.')`
- `evaluate_release_gates('.', boundary_path='docs/review/conformance/certification_boundary.strict_target.json')`
- `evaluate_promotion_target('.')`
