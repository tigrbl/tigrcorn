from __future__ import annotations

import json
import tempfile
from pathlib import Path

from benchmarks.profiles import REQUIRED_PROFILE_IDS
from tigrcorn.compat.perf_runner import (
import pytest
    DEFAULT_BASELINE_ARTIFACT_ROOT,
    DEFAULT_CURRENT_ARTIFACT_ROOT,
    load_performance_matrix,
    run_performance_matrix,
    validate_performance_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / 'docs/review/performance/performance_matrix.json'
BASELINE_ROOT = ROOT / DEFAULT_BASELINE_ARTIFACT_ROOT
CURRENT_ROOT = ROOT / DEFAULT_CURRENT_ARTIFACT_ROOT


class TestPhase6PerformanceHarnessTests:
    def test_matrix_declares_all_required_profile_ids(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        ids = {profile.profile_id for profile in matrix.profiles}
        assert ids == set(REQUIRED_PROFILE_IDS)
    def test_preserved_artifacts_validate_for_current_release(self) -> None:
        failures = validate_performance_artifacts(
            ROOT,
            artifact_root=DEFAULT_CURRENT_ARTIFACT_ROOT,
            baseline_root=DEFAULT_BASELINE_ARTIFACT_ROOT,
            require_relative_regression=True,
        )
        assert failures == []
    def test_each_profile_has_required_artifact_files(self) -> None:
        for profile_id in REQUIRED_PROFILE_IDS:
            profile_dir = CURRENT_ROOT / profile_id
            assert (profile_dir / 'result.json').exists(), profile_id
            assert (profile_dir / 'summary.json').exists(), profile_id
            assert (profile_dir / 'env.json').exists(), profile_id
            assert (profile_dir / 'percentile_histogram.json').exists(), profile_id
            assert (profile_dir / 'raw_samples.csv').exists(), profile_id
            assert (profile_dir / 'command.json').exists(), profile_id
            assert (profile_dir / 'correctness.json').exists(), profile_id
            result = json.loads((profile_dir / 'result.json').read_text(encoding='utf-8'))
            assert result['passed'], profile_id
            assert result['profile_id'] == profile_id
            assert 'p99_9_ms' in result['metrics']
            assert 'time_to_first_byte_ms' in result['metrics']
            assert 'handshake_latency_ms' in result['metrics']
            assert 'protocol_stalls' in result['metrics']
    def test_each_profile_links_to_a_known_deployment_profile(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        deployment_payload = json.loads((ROOT / "docs/review/conformance/deployment_profiles.json").read_text(encoding="utf-8"))
        known = {item["profile_id"] for item in deployment_payload["profiles"]}
        for profile in matrix.profiles:
            assert profile.deployment_profile in known, profile.profile_id
    def test_rfc_scoped_profiles_require_correctness_checks(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        for profile in matrix.profiles:
            if profile.rfc_targets:
                assert profile.correctness_required, profile.profile_id
    def test_matrix_declares_required_lanes_and_platforms(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        lanes = {profile.lane for profile in matrix.profiles}
        assert lanes == {'component_regression', 'end_to_end_release'}
        for profile in matrix.profiles:
            assert profile.certification_platforms, profile.profile_id
            assert profile.lane in {'component_regression', 'end_to_end_release'}
    def test_root_artifact_summary_declares_platform_and_lanes(self) -> None:
        summary = json.loads((CURRENT_ROOT / 'summary.json').read_text(encoding='utf-8'))
        assert 'certification_platform' in summary
        assert summary['certification_platform']
        assert set(summary['lane_counts']) == {'component_regression', 'end_to_end_release'}
        assert summary['lane_counts']['component_regression'] > 0
        assert summary['lane_counts']['end_to_end_release'] > 0
    def test_rfc_scoped_profile_artifacts_record_correctness_requirements(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        for profile in matrix.profiles:
            if not profile.rfc_targets:
                continue
            correctness = json.loads((CURRENT_ROOT / profile.profile_id / 'correctness.json').read_text(encoding='utf-8'))
            assert correctness['required'], profile.profile_id
            assert correctness['passed'], profile.profile_id
            assert correctness['checks'], profile.profile_id
    def test_end_to_end_release_profiles_preserve_live_listener_metadata(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        for profile in matrix.profiles:
            if profile.lane != 'end_to_end_release':
                continue
            assert profile.live_listener_required, profile.profile_id
            for filename in ['result.json', 'summary.json', 'command.json', 'correctness.json']:
                payload = json.loads((CURRENT_ROOT / profile.profile_id / filename).read_text(encoding='utf-8'))
                assert payload['lane'] == 'end_to_end_release', f'{profile.profile_id}::{filename}'
                assert payload['live_listener_required'], f'{profile.profile_id}::{filename}'
    def test_runner_can_execute_a_selected_profile_into_a_temp_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                artifact_root=Path(tmp) / 'perf',
                profile_ids=['http11_baseline'],
                establish_baseline=True,
            )
            assert summary.total == 1
            profile_dir = Path(summary.artifact_root) / 'http11_baseline'
            assert (profile_dir / 'result.json').exists()
            assert (profile_dir / 'summary.json').exists()
            assert 'p99_9_ms' in summary.profiles[0].metrics
            assert 'time_to_first_byte_ms' in summary.profiles[0].metrics
