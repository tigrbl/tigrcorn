"""Executable placeholders for the governed QUIC congestion-control test plan."""

import pytest


pytestmark = pytest.mark.skip(reason="planned QUIC congestion-control extension work")


@pytest.mark.parametrize(
    "case",
    [
        "api_v1_contract",
        "provider_discovery",
        "provider_version_rejection",
        "provider_duplicate_rejection",
        "provider_lazy_import",
        "config_precedence",
        "per_path_isolation",
        "migration_controller_lifecycle",
        "reload_new_connections_only",
        "invalid_output_fail_closed",
        "rfc9002_separation",
        "pacing_admission",
        "fifo_provider_matrix",
        "anti_amplification_provider_matrix",
        "reno_golden_traces",
        "reno_randomized_differential",
        "reno_persistent_congestion",
        "package_dag",
        "fresh_wheel_discovery",
        "runtime_describe",
        "metrics_cardinality",
        "loss_jitter_matrix",
        "bandwidth_rtt_matrix",
        "app_limited_matrix",
        "fairness_matrix",
        "control_latency_under_media",
        "multi_client_webtransport_soak",
        "third_party_http3_interop",
    ],
)
def test_quic_congestion_control_plan(case: str) -> None:
    """Reserve stable pytest cases until each planned assertion is implemented."""

    raise AssertionError(f"planned test executed unexpectedly: {case}")
