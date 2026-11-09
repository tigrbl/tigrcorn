"""Executable placeholders for the governed QUIC congestion-control test plan."""

import pytest


pytestmark = pytest.mark.skip(reason="planned QUIC congestion-control extension work")


@pytest.mark.parametrize(
    "case",
    [
        "migration_controller_lifecycle",
        "reload_new_connections_only",
        "rfc9002_separation",
        "pacing_admission",
        "fifo_provider_matrix",
        "anti_amplification_provider_matrix",
        "reno_randomized_differential",
        "reno_persistent_congestion",
        "fresh_wheel_discovery",
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
