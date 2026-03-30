from __future__ import annotations

from pathlib import Path

from benchmarks.registry import get_driver
from tigrcorn.compat.perf_runner import PerfProfile

ROOT = Path(__file__).resolve().parents[2]

_ITERATIONS = 20
_WARMUPS = 2


def _make_profile(
    driver: str,
    *,
    iterations: int = _ITERATIONS,
    warmups: int = _WARMUPS,
    units_per_iteration: int = 1,
    driver_config: dict | None = None,
) -> PerfProfile:
    return PerfProfile(
        profile_id=f'perf_test_{driver}',
        family='perf',
        description=f'perf test for {driver}',
        driver=driver,
        deployment_profile=driver,
        iterations=iterations,
        warmups=warmups,
        units_per_iteration=units_per_iteration,
        driver_config=driver_config or {},
    )


def _assert_measurement_healthy(measurement: dict, *, max_p99_ms: float = 10.0) -> None:
    assert measurement['error_count'] == 0
    samples = measurement['samples_ms']
    assert len(samples) > 0
    assert measurement['total_duration_seconds'] > 0.0
    sorted_samples = sorted(samples)
    if len(sorted_samples) >= 2:
        p99_index = int(0.99 * (len(sorted_samples) - 1))
        assert sorted_samples[p99_index] < max_p99_ms, (
            f'p99 latency {sorted_samples[p99_index]:.3f}ms exceeds {max_p99_ms}ms bound'
        )
    for key, value in measurement['correctness_checks'].items():
        assert value, f'correctness check failed: {key}'


def test_http11_baseline_latency():
    profile = _make_profile('http11_baseline')
    measurement = get_driver('http11_baseline')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)
    assert len(measurement['samples_ms']) == _ITERATIONS


def test_http11_keepalive_latency():
    profile = _make_profile('http11_keepalive')
    measurement = get_driver('http11_keepalive')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)


def test_http11_chunked_latency():
    profile = _make_profile('http11_chunked_upload_download')
    measurement = get_driver('http11_chunked_upload_download')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)


def test_http2_hpack_multiplex_latency():
    profile = _make_profile('http2_multiplex', units_per_iteration=10, driver_config={'stream_count': 10})
    measurement = get_driver('http2_multiplex')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)
    assert measurement['streams'] >= _ITERATIONS * 10


def test_http2_tls_context_latency():
    profile = _make_profile('http2_tls')
    measurement = get_driver('http2_tls')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=50.0)


def test_http3_qpack_clean_latency():
    profile = _make_profile('http3_clean_network')
    measurement = get_driver('http3_clean_network')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)


def test_http3_loss_recovery_latency():
    profile = _make_profile('http3_loss_jitter')
    measurement = get_driver('http3_loss_jitter')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)


def test_websocket_frame_latency():
    profile = _make_profile('ws_http11')
    measurement = get_driver('ws_http11')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)


def test_websocket_deflate_latency():
    profile = _make_profile('ws_http11_permessage_deflate')
    measurement = get_driver('ws_http11_permessage_deflate')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=10.0)


def test_tls_handshake_latency():
    profile = _make_profile('tls_handshake')
    measurement = get_driver('tls_handshake')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=50.0)


def test_mtls_handshake_latency():
    profile = _make_profile('mtls_handshake')
    measurement = get_driver('mtls_handshake')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=50.0)


def test_content_coding_latency():
    profile = _make_profile(
        'content_coding_under_load',
        driver_config={'policy': 'allowlist', 'codings': ['gzip', 'deflate']},
    )
    measurement = get_driver('content_coding_under_load')(profile, source_root=ROOT)
    _assert_measurement_healthy(measurement, max_p99_ms=20.0)
