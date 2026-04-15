# Phase 8 checkpoint

Date: 2026-04-07

This checkpoint records the mutable-tree completion of Phase 8 governance, release-gating, RFC 9651 hygiene, retained-bundle manifests, and pytest-forward validation.

What was added:

- governance authority docs under `docs/governance/`
- ADRs `.ssot/adr/ADR-1007-gov-auth.md` and `.ssot/adr/ADR-1008-gate-graph.md`
- `docs/reference/risk_register.schema.json`
- `docs/conformance/risk/RISK_REGISTER.json`
- `docs/conformance/risk/RISK_TRACEABILITY.json`
- `LEGACY_UNITTEST_INVENTORY.json`
- `docs/conformance/sf9651.json` and `docs/conformance/sf9651.md`
- `docs/conformance/interop_retention.json` and `docs/conformance/perf_retention.json`
- package-owned RFC 9651 helper implementation in `src/tigrcorn/http/structured_fields.py`
- governance-graph enforcement in `src/tigrcorn/compat/release_gates.py`

Validation run for this checkpoint:

- `python tools/cert/governance_surface.py`
- `python -m compileall -q src benchmarks tools`
- `python -m pytest -q tests/test_p8_gov.py tests/test_p8_sf.py tests/test_release_gates.py tests/test_config_matrix_pytest.py`
- `python tools/cert/status.py`

Truth statement:

- the working tree remains certifiably fully RFC compliant under the authoritative certification boundary
- the canonical frozen `0.3.9` release root remains strict-target certifiably fully RFC compliant and certifiably fully featured
- these Phase 8 artifacts live in the mutable tree and have not yet been promoted into a new frozen release root
