from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tigrcorn.compat.perf_runner import run_performance_matrix

ROOT = Path(__file__).resolve().parents[2]


def _run_profiles_and_assert(profile_ids: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_performance_matrix(
            ROOT,
            artifact_root=Path(tmp) / 'perf',
            profile_ids=profile_ids,
            establish_baseline=True,
        )
        assert summary.total == len(profile_ids)
        for result in summary.profiles:
            assert result.metrics['throughput_ops_per_sec'] > 0
            assert result.metrics['error_count'] == 0
            assert result.metrics['error_rate'] == 0.0
            assert result.metrics['sample_count'] > 0
            if result.correctness.get('required'):
                assert result.correctness['passed'], f'{result.profile_id}: correctness failed'
            profile_dir = Path(result.artifact_dir)
            for filename in ('result.json', 'summary.json', 'env.json', 'correctness.json'):
                assert (profile_dir / filename).exists(), f'{result.profile_id}: missing {filename}'
            result_json = json.loads((profile_dir / 'result.json').read_text(encoding='utf-8'))
            assert result_json['profile_id'] == result.profile_id
            assert 'p99_9_ms' in result_json['metrics']
            assert 'throughput_ops_per_sec' in result_json['metrics']


def test_http_profiles_pass_thresholds():
    _run_profiles_and_assert(['http11_baseline', 'http11_keepalive'])


def test_websocket_profiles_pass_thresholds():
    _run_profiles_and_assert(['ws_http11'])


def test_tls_profiles_pass_thresholds():
    _run_profiles_and_assert(['tls_handshake'])
