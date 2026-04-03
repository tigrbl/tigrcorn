from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_promotion_target
from tigrcorn.compat.perf_runner import validate_performance_artifacts

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
PERFORMANCE = ROOT / 'docs' / 'review' / 'performance'
CURRENT_ROOT = ROOT / 'docs' / 'review' / 'performance' / 'artifacts' / 'phase6_current_release'



def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))

def test_phase9g_docs_and_status_exist() -> None:
    assert (CONFORMANCE / 'PHASE9G_STRICT_PERFORMANCE_CLOSURE.md').exists()
    assert (CONFORMANCE / 'phase9g_strict_performance.current.json').exists()
    assert (ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9G_STRICT_PERFORMANCE_CLOSURE.md').exists()
    status = _load_json('docs/review/conformance/phase9g_strict_performance.current.json')
    assert status['phase'] == '9G'
    assert status['checkpoint'] == 'phase9g_strict_performance_closure'
    assert status['current_state']['performance_passed']
    assert not (status['current_state']['promotion_target_passed'])
def test_matrix_declares_required_lanes_platforms_and_threshold_keys() -> None:
    matrix = _load_json('docs/review/performance/performance_matrix.json')
    lanes = {profile['lane'] for profile in matrix['profiles']}
    assert lanes == {'component_regression', 'end_to_end_release'}
    assert matrix['metadata']['certification_platforms']
    for profile in matrix['profiles']:
        thresholds = profile['thresholds']
        assert 'max_p50_ms' in thresholds
        assert 'max_p95_ms' in thresholds
        assert 'max_p99_ms' in thresholds
        assert 'max_p99_9_ms' in thresholds
        assert 'max_time_to_first_byte_ms' in thresholds
        assert 'max_handshake_latency_ms' in thresholds
        assert 'max_protocol_stalls' in thresholds
        assert 'max_rss_kib' in thresholds
        assert 'max_scheduler_rejections' in thresholds
        budget = profile['relative_regression_budget']
        assert 'max_p99_9_increase_fraction' in budget
        assert 'max_cpu_increase_fraction' in budget
        assert 'max_rss_increase_fraction' in budget
def test_current_artifacts_expose_required_metric_keys_and_files() -> None:
    matrix = _load_json('docs/review/performance/performance_matrix.json')
    for profile in matrix['profiles']:
        profile_dir = CURRENT_ROOT / profile['profile_id']
        assert (profile_dir / 'result.json').exists(), profile['profile_id']
        assert (profile_dir / 'summary.json').exists(), profile['profile_id']
        assert (profile_dir / 'correctness.json').exists(), profile['profile_id']
        result = json.loads((profile_dir / 'result.json').read_text(encoding='utf-8'))
        assert 'p99_9_ms' in result['metrics']
        assert 'time_to_first_byte_ms' in result['metrics']
        assert 'handshake_latency_ms' in result['metrics']
        assert 'protocol_stalls' in result['metrics']
def test_preserved_artifacts_validate_and_promotion_report_performance_section_is_green() -> None:
    failures = validate_performance_artifacts(
        ROOT,
        artifact_root='docs/review/performance/artifacts/phase6_current_release',
        baseline_root='docs/review/performance/artifacts/phase6_reference_baseline',
        require_relative_regression=True,
    )
    assert failures == []
    report = evaluate_promotion_target(ROOT)
    assert report.performance.passed, report.performance.failures
    assert not (report.passed)
    assert not (report.strict_target_boundary.passed)
