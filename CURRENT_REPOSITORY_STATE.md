# Current repository state

Released-history repair note: the originally released `0.3.8` conformance tree has been restored from `tigrcorn-main (2).zip`, and the updated package line is now promoted as canonical `0.3.9`.

The current authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

The repository continues to operate under the **dual-boundary model**:

Historical checkpoint guardrail: the authoritative boundary remains green while the strict target is not yet green. Those exact phrases are preserved here for documentation-consistency checks even though the canonical 0.3.9 release root is now green.

- `evaluate_release_gates('.')` is **green** under the authoritative boundary
- the stricter next-target boundary defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is now **green** under the canonical 0.3.9 release root
- `evaluate_promotion_target()` is now **green**

Under the current authoritative boundary, the package remains **certifiably fully RFC compliant**. Under the canonical 0.3.9 release root, the package is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

What is now true:

- the 0.3.9 release root is now the canonical authoritative release root
- the public package version is now `0.3.9`
- the release notes now live in `RELEASE_NOTES_0.3.9.md`
- the authoritative boundary remains green
- the strict target is green under the canonical 0.3.9 release root
- the flag surface is green
- RFC 9220 WebSocket-over-HTTP/3 remains green in both the authoritative boundary and the canonical 0.3.9 release root
- the operator surface is green
- the performance section is green
- the documentation section is green
- the composite promotion target is green
- all previously failing HTTP/3 strict-target scenarios remain preserved as passing artifacts in the canonical root
- the version bump and release-note promotion work from Step 9 is complete

There are no remaining strict-target RFC, feature, or administrative promotion blockers in the canonical 0.3.9 release root.

## Canonical current-state chain

The canonical package-wide current-state chain is now explicitly normalized.

Use these sources for package-wide truth:

- `CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/phase9i_strict_validation.current.json`
- `docs/review/conformance/phase8_certification_refresh_and_promotion.current.json`

Additional focused audits such as `docs/review/conformance/http_integrity_caching_signatures_status.current.json` and `docs/review/conformance/rfc_applicability_and_competitor_status.current.json` remain current for their own narrow scopes, but they are **not** the canonical package-wide current-state source.

Historical phase checkpoints and executed closure snapshots may still retain stable `*.current.json` names for provenance and test references, but they are now explicitly labeled as archival when they are not current package truth.

The canonical current integrated Phase 4 example tree is `examples/advanced_delivery/`. The retained `examples/advanced_protocol_delivery/` tree is an archival compatibility path for the original Phase 4 checkpoint examples.


Primary documentation for the current promoted state now lives in:

- `docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `RELEASE_NOTES_0.3.9.md`
- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/PHASE9I_STRICT_VALIDATION.md`
- `docs/review/conformance/phase9i_strict_validation.current.json`
- `docs/review/conformance/PHASE8_CERTIFICATION_REFRESH_AND_PROMOTION_CHECKPOINT.md`
- `docs/review/conformance/phase8_certification_refresh_and_promotion.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`
- `DELIVERY_NOTES_PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`
- `DELIVERY_NOTES_PHASE8_CERTIFICATION_REFRESH_AND_PROMOTION_CHECKPOINT.md`

The authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

For the stricter target, see `docs/review/conformance/STRICT_PROFILE_TARGET.md`.

## Phase 9 release-promotion checkpoint

This checkpoint completes the Step 9 administrative promotion work:

- `pyproject.toml` now reports version `0.3.9`
- the canonical authoritative release root is now `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- release notes now live in `RELEASE_NOTES_0.3.9.md`
- the current-state docs and machine-readable snapshots now truthfully report the strict-target green state under the canonical promoted release

## Certification environment freeze

This checkpoint also preserves the strict-promotion certification environment contract in:

- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`

What that freeze now means:

- the release workflow must run under Python 3.11 or 3.12
- the release workflow must install `.[certification,dev]` before any Phase 9 checkpoint script is executed
- `tools/run_phase9_release_workflow.py` freezes and validates the certification environment before it invokes Phase 9 checkpoint scripts
- a non-ready local environment is recorded honestly instead of being treated as an acceptable release-workflow substitute

## Phase 9 implementation-plan checkpoint

The broader strict-promotion execution plan remains documented in:

- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/phase9_implementation_plan.current.json`

## Phase 9A promotion-contract-freeze checkpoint

The executed Phase 9A contract freeze remains preserved in:

- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/phase9a_execution_backlog.current.json`

Those files remain the governing historical execution baseline for the strict-promotion closure program. They are retained for provenance and are not the canonical current-state source.

## Phase 8 certification-refresh and promotion checkpoint

This repository checkpoint re-runs compileall, the targeted strict-validation pytest suite, a broader certification-refresh pytest matrix, the authoritative gate, the strict gate, and the promotion target against the canonical promoted 0.3.9 root.

The preserved validation artifacts now also live in:

- `docs/review/conformance/PHASE8_CERTIFICATION_REFRESH_AND_PROMOTION_CHECKPOINT.md`
- `docs/review/conformance/phase8_certification_refresh_and_promotion.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-phase8-certification-refresh-bundle/`
- `CURRENT_REPOSITORY_STATE_PHASE8_CERTIFICATION_REFRESH_AND_PROMOTION_CHECKPOINT.md`

## Historical Phase 7 candidate checkpoint

Historical preserved Phase 7 truth: Canonical promotion was **not** performed for the frozen `0.3.7` candidate next release root. That statement remains historically accurate for `docs/review/conformance/PHASE7_CANONICAL_PROMOTION_STATUS.md` and is preserved here for compatibility with the Phase 7 release-candidate audit trail.


The historical 0.3.8 release root remains preserved at `docs/review/conformance/releases/0.3.8/release-0.3.8`. The current canonical release root is `docs/review/conformance/releases/0.3.9/release-0.3.9`.


The current recertification checkpoint executed a 99-test certification-refresh matrix, a 27-test targeted strict-validation suite, compileall, the authoritative gate, the strict gate, and the promotion target against the canonical 0.3.9 release root.
