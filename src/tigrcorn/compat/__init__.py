"""Compatibility helpers and conformance surfaces."""
from .aioquic_preflight import (
    AioquicAdapterPreflightError,
    run_aioquic_adapter_preflight,
    write_status_documents as write_aioquic_preflight_status_documents,
)
from .interop import InteropResult, InteropVector, load_results, load_vectors, summarize_results
from .interop_runner import (
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
from .release_gates import (
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
