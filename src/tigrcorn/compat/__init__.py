"""Compatibility helpers and conformance surfaces."""
from .interop import InteropResult, InteropVector, load_results, load_vectors, summarize_results
from .interop_runner import (
    ExternalInteropRunner,
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
    ReleaseGateError,
    ReleaseGateReport,
    assert_release_ready,
    evaluate_release_gates,
    load_certification_boundary,
)
