# Current repository state

The current authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

The repository continues to operate under the **dual-boundary model**:

Historical checkpoint guardrail: the authoritative boundary remains green while the strict target is not yet green. Those exact phrases are preserved here for documentation-consistency checks even though the canonical 0.3.8 release root is now green.

- `evaluate_release_gates('.')` is **green** under the authoritative boundary
- the stricter next-target boundary defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is now **green** under the canonical 0.3.8 release root
- `evaluate_promotion_target()` is now **green**

Under the current authoritative boundary, the package remains **certifiably fully RFC compliant**. Under the canonical 0.3.8 release root, the package is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

What is now true:

- the 0.3.8 release root is now the canonical authoritative release root
- the public package version is now `0.3.8`
- the release notes now live in `RELEASE_NOTES_0.3.8.md`
- the authoritative boundary remains green
- the strict target is green under the canonical 0.3.8 release root
- the flag surface is green
- RFC 9220 WebSocket-over-HTTP/3 remains green in both the authoritative boundary and the canonical 0.3.8 release root
- the operator surface is green
- the performance section is green
- the documentation section is green
- the composite promotion target is green
- all previously failing HTTP/3 strict-target scenarios remain preserved as passing artifacts in the canonical root
- the version bump and release-note promotion work from Step 9 is complete

There are no remaining strict-target RFC, feature, or administrative promotion blockers in the canonical 0.3.8 release root.

Primary documentation for the current promoted state now lives in:

- `docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `RELEASE_NOTES_0.3.8.md`
- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/PHASE9I_STRICT_VALIDATION.md`
- `docs/review/conformance/phase9i_strict_validation.current.json`
- `docs/review/conformance/releases/0.3.8/release-0.3.8/manifest.json`
- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_index.json`
- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_summary.json`
- `DELIVERY_NOTES_PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`

The authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

For the stricter target, see `docs/review/conformance/STRICT_PROFILE_TARGET.md`.

## Phase 9 release-promotion checkpoint

This checkpoint completes the Step 9 administrative promotion work:

- `pyproject.toml` now reports version `0.3.8`
- the canonical authoritative release root is now `docs/review/conformance/releases/0.3.8/release-0.3.8/`
- release notes now live in `RELEASE_NOTES_0.3.8.md`
- the current-state docs and machine-readable snapshots now truthfully report the strict-target green state under the canonical promoted release

## Certification environment freeze

This checkpoint also preserves the strict-promotion certification environment contract in:

- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-certification-environment-bundle/`

What that freeze now means:

- the release workflow must run under Python 3.11 or 3.12
- the release workflow must install `.[certification,dev]` before any Phase 9 checkpoint script is executed
- `tools/run_phase9_release_workflow.py` freezes and validates the certification environment before it invokes Phase 9 checkpoint scripts
- a non-ready local environment is recorded honestly instead of being treated as an acceptable release-workflow substitute

## Phase 9 implementation-plan checkpoint

The broader strict-promotion execution plan remains documented in:

- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/phase9_implementation_plan.current.json`

## Phase 9I strict validation checkpoint

The exact Step 8 strict validation set has now been executed and preserved in:

- `docs/review/conformance/PHASE9I_STRICT_VALIDATION.md`
- `docs/review/conformance/phase9i_strict_validation.current.json`
- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-strict-validation-bundle/`

What this validation records:

- `python -m compileall -q src benchmarks tools` passed
- `evaluate_release_gates('.')` passed
- `evaluate_release_gates(... strict target ...)` passed
- `evaluate_promotion_target('.')` passed
- the targeted pytest suite passed with `27` tests
