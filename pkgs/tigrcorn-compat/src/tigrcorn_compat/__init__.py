"""Compatibility helpers and conformance surfaces."""

__all__ = [
    "AioquicAdapterPreflightError",
    "run_aioquic_adapter_preflight",
    "write_aioquic_preflight_status_documents",
    "InteropResult",
    "InteropVector",
    "load_results",
    "load_vectors",
    "summarize_results",
    "ExternalInteropRunner",
    "INTEROP_ARTIFACT_SCHEMA_VERSION",
    "INTEROP_BUNDLE_REQUIRED_FILES",
    "INTEROP_SCENARIO_REQUIRED_FILES",
    "InteropMatrix",
    "InteropProcessResult",
    "InteropProcessSpec",
    "InteropRunSummary",
    "InteropScenario",
    "InteropScenarioResult",
    "build_environment_manifest",
    "detect_source_revision",
    "evaluate_assertions",
    "generate_observer_qlog",
    "load_external_matrix",
    "run_external_matrix",
    "summarize_matrix_dimensions",
    "INDEPENDENT_BUNDLE_REQUIRED_ROOT_FILES",
    "INDEPENDENT_BUNDLE_REQUIRED_SCENARIO_FILES",
    "IndependentBundleReport",
    "PromotionSectionReport",
    "PromotionTargetError",
    "PromotionTargetReport",
    "ReleaseGateError",
    "ReleaseGateReport",
    "assert_independent_certification_bundle_ready",
    "assert_promotion_target_ready",
    "assert_release_ready",
    "evaluate_promotion_target",
    "evaluate_release_gates",
    "load_certification_boundary",
    "load_promotion_target",
    "validate_independent_certification_bundle",
]


def __getattr__(name: str):
    if name in {
        "AioquicAdapterPreflightError",
        "run_aioquic_adapter_preflight",
        "write_aioquic_preflight_status_documents",
    }:
        from tigrcorn_certification.aioquic_preflight import (
            AioquicAdapterPreflightError,
            run_aioquic_adapter_preflight,
            write_status_documents,
        )

        mapping = {
            "AioquicAdapterPreflightError": AioquicAdapterPreflightError,
            "run_aioquic_adapter_preflight": run_aioquic_adapter_preflight,
            "write_aioquic_preflight_status_documents": write_status_documents,
        }
        return mapping[name]
    if name in {"InteropResult", "InteropVector", "load_results", "load_vectors", "summarize_results"}:
        from .interop import InteropResult, InteropVector, load_results, load_vectors, summarize_results

        mapping = {
            "InteropResult": InteropResult,
            "InteropVector": InteropVector,
            "load_results": load_results,
            "load_vectors": load_vectors,
            "summarize_results": summarize_results,
        }
        return mapping[name]
    if name in {
        "ExternalInteropRunner",
        "INTEROP_ARTIFACT_SCHEMA_VERSION",
        "INTEROP_BUNDLE_REQUIRED_FILES",
        "INTEROP_SCENARIO_REQUIRED_FILES",
        "InteropMatrix",
        "InteropProcessResult",
        "InteropProcessSpec",
        "InteropRunSummary",
        "InteropScenario",
        "InteropScenarioResult",
        "build_environment_manifest",
        "detect_source_revision",
        "evaluate_assertions",
        "generate_observer_qlog",
        "load_external_matrix",
        "run_external_matrix",
        "summarize_matrix_dimensions",
    }:
        from tigrcorn_certification.interop_runner import (
            ExternalInteropRunner,
            INTEROP_ARTIFACT_SCHEMA_VERSION,
            INTEROP_BUNDLE_REQUIRED_FILES,
            INTEROP_SCENARIO_REQUIRED_FILES,
            InteropMatrix,
            InteropProcessResult,
            InteropProcessSpec,
            InteropRunSummary,
            InteropScenario,
            InteropScenarioResult,
            build_environment_manifest,
            detect_source_revision,
            evaluate_assertions,
            generate_observer_qlog,
            load_external_matrix,
            run_external_matrix,
            summarize_matrix_dimensions,
        )

        mapping = locals().copy()
        return mapping[name]
    if name in {
        "INDEPENDENT_BUNDLE_REQUIRED_ROOT_FILES",
        "INDEPENDENT_BUNDLE_REQUIRED_SCENARIO_FILES",
        "IndependentBundleReport",
        "PromotionSectionReport",
        "PromotionTargetError",
        "PromotionTargetReport",
        "ReleaseGateError",
        "ReleaseGateReport",
        "assert_independent_certification_bundle_ready",
        "assert_promotion_target_ready",
        "assert_release_ready",
        "evaluate_promotion_target",
        "evaluate_release_gates",
        "load_certification_boundary",
        "load_promotion_target",
        "validate_independent_certification_bundle",
    }:
        from tigrcorn_certification.release_gates import (
            INDEPENDENT_BUNDLE_REQUIRED_ROOT_FILES,
            INDEPENDENT_BUNDLE_REQUIRED_SCENARIO_FILES,
            IndependentBundleReport,
            PromotionSectionReport,
            PromotionTargetError,
            PromotionTargetReport,
            ReleaseGateError,
            ReleaseGateReport,
            assert_independent_certification_bundle_ready,
            assert_promotion_target_ready,
            assert_release_ready,
            evaluate_promotion_target,
            evaluate_release_gates,
            load_certification_boundary,
            load_promotion_target,
            validate_independent_certification_bundle,
        )

        mapping = locals().copy()
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
