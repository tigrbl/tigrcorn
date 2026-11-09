from __future__ import annotations

import os
from pathlib import Path

from benchmarks.registry import get_driver
from tigrcorn.compat.perf_runner import PerfProfile, run_performance_matrix

ROOT = Path(__file__).resolve().parents[2]

_ITERATIONS = 10
_WARMUPS = 1


def _make_profile(
    driver: str,
    *,
    units_per_iteration: int = 1,
    driver_config: dict | None = None,
) -> PerfProfile:
    return PerfProfile(
        profile_id=f'correctness_{driver}',
        family='correctness',
        description=f'correctness test for {driver}',
        driver=driver,
        deployment_profile=driver,
        iterations=_ITERATIONS,
        warmups=_WARMUPS,
        units_per_iteration=units_per_iteration,
        driver_config=driver_config or {},
    )


def _run_driver(name: str, **kwargs) -> dict:
    profile = _make_profile(name, **kwargs)
    return get_driver(name)(profile, source_root=ROOT)


def _assert_correctness_keys(measurement: dict, expected_keys: list[str]) -> None:
    assert measurement['error_count'] == 0
    checks = measurement['correctness_checks']
    for key in expected_keys:
        assert key in checks, f'missing correctness key: {key}'
        assert checks[key], f'correctness check failed: {key}'


def test_http11_parser_correctness():
    measurement = _run_driver('http11_baseline')
    _assert_correctness_keys(measurement, ['parsed_head'])


def test_hpack_roundtrip_correctness():
    measurement = _run_driver('http2_multiplex', units_per_iteration=10, driver_config={'stream_count': 10})
    _assert_correctness_keys(measurement, ['hpack_roundtrip'])


def test_qpack_roundtrip_correctness():
    measurement = _run_driver('http3_clean_network')
    _assert_correctness_keys(measurement, ['qpack_roundtrip', 'quic_decode'])


def test_websocket_frame_correctness():
    m1 = _run_driver('ws_http11')
    _assert_correctness_keys(m1, ['frame_roundtrip'])
    m2 = _run_driver('ws_http11_permessage_deflate')
    _assert_correctness_keys(m2, ['deflate_roundtrip'])


def test_tls_context_correctness():
    m1 = _run_driver('tls_handshake')
    _assert_correctness_keys(m1, ['context_built', 'default_alpn'])
    m2 = _run_driver('mtls_handshake')
    _assert_correctness_keys(m2, ['context_built', 'requires_client_cert'])


def test_content_coding_correctness():
    measurement = _run_driver(
        'content_coding_under_load',
        driver_config={'policy': 'allowlist', 'codings': ['gzip', 'deflate']},
    )
    _assert_correctness_keys(measurement, ['status_ok', 'selection_valid', 'body_nonempty'])



def test_matrix_runs_each_profile_in_a_fresh_process(tmp_path):
    summary = run_performance_matrix(
        ROOT,
        artifact_root=tmp_path,
        profile_ids=['http11_baseline', 'http11_keepalive'],
        establish_baseline=True,
    )

    assert summary.total == 2
    metadata = [result.metrics['profile_metadata'] for result in summary.profiles]
    worker_pids = {record['worker_pid'] for record in metadata}
    assert len(worker_pids) == 2
    assert os.getpid() not in worker_pids
    assert all(record['worker_peak_before_workload_kib'] >= 0 for record in metadata)
