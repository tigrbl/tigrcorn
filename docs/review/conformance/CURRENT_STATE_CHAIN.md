# Current-state chain

This document defines the **one canonical package-wide current-state chain** for the repository.

## Canonical package-wide current-state sources

### Human-readable sources

- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/state/checkpoints/CURRENT_REPOSITORY_STATE_PHASE9J_RELEASED_0_3_8_REPAIR_AND_0_3_9_PROMOTION_CHECKPOINT.md`
- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`
- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md`
- `docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md`

### Machine-readable sources

- `docs/review/conformance/current_state_chain.current.json`
- `docs/review/conformance/phase9j_released_0_3_8_repair_and_0_3_9_promotion.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/phase9i_strict_validation.current.json`

## Canonical policy sources

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/STRICT_PROFILE_TARGET.md`
- `docs/review/conformance/certification_boundary.strict_target.json`
- `docs/review/conformance/promotion_gate.target.json`

## Scoped current audits that are **not** package-wide current-state sources

- `docs/review/conformance/HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md`
- `docs/review/conformance/http_integrity_caching_signatures_status.current.json`
- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- `docs/review/conformance/rfc_applicability_and_competitor_status.current.json`
- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md`
- `docs/review/conformance/rfc_applicability_and_competitor_support.current.json`

Those documents are current for their own focused scopes, but they are **not** the canonical package-wide current-state source.

## Historical snapshots that still use `.current.json` names

Many earlier checkpoint and phase-closure artifacts retain stable `*.current.json` file names for tests, tooling, and provenance. They are historical snapshots when their `document_role` is `archival_named_current_snapshot_for_stability`.

Representative archival current-alias paths include:

- `docs/review/conformance/dependency_declaration_reconciliation_checkpoint.current.json`
- `docs/review/conformance/documentation_truth_normalization_checkpoint.current.json`
- `docs/review/conformance/phase0_public_cli_contract_drift_reconciliation.current.json`
- `docs/review/conformance/phase1_boundary_and_non_goals_normalization.current.json`
- `docs/review/conformance/phase1_surface_parity_checkpoint.current.json`
- `docs/review/conformance/phase2_core_http_entity_semantics_checkpoint.current.json`
- `docs/review/conformance/phase2_rfc_boundary_formalization_checkpoint.current.json`
- `docs/review/conformance/phase2_static_and_file_delivery_surface.current.json`
- `docs/review/conformance/phase3_h1_and_websocket_operator_surface.current.json`
- `docs/review/conformance/phase3_transport_core_strictness_checkpoint.current.json`
- `docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json`
- `docs/review/conformance/phase4_h2_operator_surface.current.json`
- `docs/review/conformance/phase4_rfc_boundary_formalization_checkpoint.current.json`
- `docs/review/conformance/phase5_phase6_phase7_tls_lifecycle_flag_truth.current.json`
- `docs/review/conformance/phase7_canonical_promotion_status.current.json`
- `docs/review/conformance/phase8_strict_promotion_target_status.current.json`
- `docs/review/conformance/phase9_implementation_plan.current.json`
- `docs/review/conformance/phase9a_execution_backlog.current.json`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/phase9b_independent_harness.current.json`
- `docs/review/conformance/phase9c_rfc7692_independent_closure.current.json`
- `docs/review/conformance/phase9d1_connect_relay_independent.current.json`
- `docs/review/conformance/phase9d2_trailer_fields_independent.current.json`
- `docs/review/conformance/phase9d3_content_coding_independent.current.json`
- `docs/review/conformance/phase9e_ocsp_independent.current.json`
- `docs/review/conformance/phase9f1_tls_cipher_policy.current.json`
- `docs/review/conformance/phase9f2_logging_exporter.current.json`
- `docs/review/conformance/phase9f3_concurrency_keepalive.current.json`
- `docs/review/conformance/phase9g_strict_performance.current.json`
- `docs/review/conformance/phase9h_promotion_evaluator.current.json`
- `docs/review/conformance/promotion_artifact_reconciliation_checkpoint.current.json`
- `docs/review/conformance/response_pipeline_streaming_checkpoint.current.json`
- `docs/review/conformance/static_delivery_productionization_checkpoint.current.json`
- `docs/review/conformance/trio_runtime_surface_reconciliation_checkpoint.current.json`

## Example-path policy

- `examples/advanced_delivery/` is the canonical current integrated Phase 4 example tree.
- `examples/advanced_protocol_delivery/` is retained as an archival compatibility path for focused single-feature examples from the original Phase 4 checkpoint.
- `examples/PHASE4_PROTOCOL_PAIRING.md` is the canonical current pairing matrix.

## Naming policy

A file name ending in `.current.json` does **not** by itself mean the file is the canonical package-wide current truth source. The controlling signal is the machine-readable `document_role` and `current_truth_source` fields.
