from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from tigrcorn.compat.release_gates import _evaluate_performance_target

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROMOTION_TARGET = json.loads((ROOT / 'docs/review/conformance/promotion_gate.target.json').read_text(encoding='utf-8'))
PERFORMANCE_CONFIG = dict(PROMOTION_TARGET['performance'])



def _copy_performance_tree() -> Path:
    tmpdir = tempfile.mkdtemp(prefix='tigrcorn-phase9h-')
    root = Path(tmpdir)
    shutil.copytree(ROOT / 'docs/review/performance', root / 'docs/review/performance', dirs_exist_ok=True)
    return root

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))

def test_actual_repository_performance_section_passes_under_hardened_evaluator() -> None:
    report = _evaluate_performance_target(ROOT, PERFORMANCE_CONFIG)
    assert report.passed, '\n'.join(report.failures)
    assert report.failures == []
def test_missing_metric_key_fails() -> None:
    root = _copy_performance_tree()
    try:
        artifact_root = root / 'docs/review/performance/artifacts/phase6_current_release'
        for result_file in artifact_root.glob('*/result.json'):
            payload = _load_json(result_file)
            payload['metrics'].pop('protocol_stalls', None)
            result_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        assert 'performance artifacts are missing required SLO metric keys' in '\n'.join(report.failures)
    finally:
        shutil.rmtree(root)

def test_missing_threshold_key_fails() -> None:
    root = _copy_performance_tree()
    try:
        matrix_file = root / 'docs/review/performance/performance_matrix.json'
        matrix = _load_json(matrix_file)
        matrix['profiles'][0]['thresholds'].pop('max_p99_9_ms', None)
        matrix_file.write_text(json.dumps(matrix, indent=2, sort_keys=False) + '\n', encoding='utf-8')
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        assert 'http11_baseline missing required threshold keys' in '\n'.join(report.failures)
    finally:
        shutil.rmtree(root)

def test_missing_relative_budget_key_fails() -> None:
    root = _copy_performance_tree()
    try:
        matrix_file = root / 'docs/review/performance/performance_matrix.json'
        matrix = _load_json(matrix_file)
        matrix['profiles'][0]['relative_regression_budget'].pop('max_cpu_increase_fraction', None)
        matrix_file.write_text(json.dumps(matrix, indent=2, sort_keys=False) + '\n', encoding='utf-8')
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        assert 'http11_baseline missing required relative regression budget keys' in '\n'.join(report.failures)
    finally:
        shutil.rmtree(root)

def test_missing_root_artifact_file_fails() -> None:
    root = _copy_performance_tree()
    try:
        (root / 'docs/review/performance/artifacts/phase6_current_release/summary.json').unlink()
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        failures = '\n'.join(report.failures)
        assert 'missing performance summary file' in failures
        assert 'performance artifact root is missing required files' in failures
    finally:
        shutil.rmtree(root)

def test_missing_profile_artifact_file_fails() -> None:
    root = _copy_performance_tree()
    try:
        (root / 'docs/review/performance/artifacts/phase6_current_release/http11_baseline/correctness.json').unlink()
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        failures = '\n'.join(report.failures)
        assert 'missing artifact file for http11_baseline' in failures
        assert 'http11_baseline performance artifact directory is missing required files' in failures
    finally:
        shutil.rmtree(root)

def test_missing_required_lane_fails() -> None:
    root = _copy_performance_tree()
    try:
        matrix_file = root / 'docs/review/performance/performance_matrix.json'
        matrix = _load_json(matrix_file)
        for profile in matrix['profiles']:
            if profile['lane'] == 'component_regression':
                profile['lane'] = 'end_to_end_release'
                profile['live_listener_required'] = True
        matrix_file.write_text(json.dumps(matrix, indent=2, sort_keys=False) + '\n', encoding='utf-8')

        summary_file = root / 'docs/review/performance/artifacts/phase6_current_release/summary.json'
        summary = _load_json(summary_file)
        summary['lane_counts'].pop('component_regression', None)
        summary['lane_counts']['end_to_end_release'] = summary['passed']
        summary_file.write_text(json.dumps(summary, indent=2, sort_keys=False) + '\n', encoding='utf-8')
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        failures = '\n'.join(report.failures)
        assert 'performance matrix is missing required lanes' in failures
        assert 'performance artifact summary is missing required lane counts' in failures
    finally:
        shutil.rmtree(root)

def test_missing_certification_platform_declaration_fails() -> None:
    root = _copy_performance_tree()
    try:
        matrix_file = root / 'docs/review/performance/performance_matrix.json'
        matrix = _load_json(matrix_file)
        matrix['metadata']['certification_platforms'] = []
        matrix['profiles'][0]['certification_platforms'] = []
        matrix_file.write_text(json.dumps(matrix, indent=2, sort_keys=False) + '\n', encoding='utf-8')
        env_file = root / 'docs/review/performance/artifacts/phase6_current_release/http11_baseline/env.json'
        env_payload = _load_json(env_file)
        env_payload.pop('certification_platform', None)
        env_payload['matrix_declared_platforms'] = []
        env_file.write_text(json.dumps(env_payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        failures = '\n'.join(report.failures)
        assert 'performance matrix metadata is missing certification_platforms declarations' in failures
        assert 'http11_baseline missing profile certification_platforms declarations in matrix' in failures
        assert 'http11_baseline missing env.json certification_platform declaration' in failures
    finally:
        shutil.rmtree(root)

def test_missing_rfc_correctness_checks_fails() -> None:
    root = _copy_performance_tree()
    try:
        correctness_file = root / 'docs/review/performance/artifacts/phase6_current_release/http11_baseline/correctness.json'
        correctness = _load_json(correctness_file)
        correctness['required'] = False
        correctness['checks'] = {}
        correctness_file.write_text(json.dumps(correctness, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        failures = '\n'.join(report.failures)
        assert 'http11_baseline correctness.json is not marked required=true for an RFC-scoped profile' in failures
        assert 'http11_baseline correctness.json is missing correctness checks for an RFC-scoped profile' in failures
    finally:
        shutil.rmtree(root)

def test_missing_live_listener_metadata_fails() -> None:
    root = _copy_performance_tree()
    try:
        command_file = root / 'docs/review/performance/artifacts/phase6_current_release/http11_baseline/command.json'
        payload = _load_json(command_file)
        payload['live_listener_required'] = False
        payload['lane'] = 'component_regression'
        command_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        report = _evaluate_performance_target(root, PERFORMANCE_CONFIG)
        assert not (report.passed)
        failures = '\n'.join(report.failures)
        assert 'http11_baseline command.json does not preserve live_listener_required=true' in failures
        assert 'http11_baseline command.json does not preserve lane="end_to_end_release"' in failures
    finally:
        shutil.rmtree(root)


