from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.profiles import REQUIRED_PROFILE_IDS
from tigrcorn.compat.perf_runner import (
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


class Phase6PerformanceHarnessTests(unittest.TestCase):
    def test_matrix_declares_all_required_profile_ids(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        ids = {profile.profile_id for profile in matrix.profiles}
        self.assertEqual(ids, set(REQUIRED_PROFILE_IDS))

    def test_preserved_artifacts_validate_for_current_release(self) -> None:
        failures = validate_performance_artifacts(
            ROOT,
            artifact_root=DEFAULT_CURRENT_ARTIFACT_ROOT,
            baseline_root=DEFAULT_BASELINE_ARTIFACT_ROOT,
            require_relative_regression=True,
        )
        self.assertEqual(failures, [])

    def test_each_profile_has_required_artifact_files(self) -> None:
        for profile_id in REQUIRED_PROFILE_IDS:
            profile_dir = CURRENT_ROOT / profile_id
            self.assertTrue((profile_dir / 'result.json').exists(), profile_id)
            self.assertTrue((profile_dir / 'summary.json').exists(), profile_id)
            self.assertTrue((profile_dir / 'env.json').exists(), profile_id)
            self.assertTrue((profile_dir / 'percentile_histogram.json').exists(), profile_id)
            self.assertTrue((profile_dir / 'raw_samples.csv').exists(), profile_id)
            self.assertTrue((profile_dir / 'command.json').exists(), profile_id)
            self.assertTrue((profile_dir / 'correctness.json').exists(), profile_id)
            result = json.loads((profile_dir / 'result.json').read_text(encoding='utf-8'))
            self.assertTrue(result['passed'], profile_id)
            self.assertEqual(result['profile_id'], profile_id)
            self.assertIn('p99_9_ms', result['metrics'])
            self.assertIn('time_to_first_byte_ms', result['metrics'])
            self.assertIn('handshake_latency_ms', result['metrics'])
            self.assertIn('protocol_stalls', result['metrics'])


    def test_each_profile_links_to_a_known_deployment_profile(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        deployment_payload = json.loads((ROOT / "docs/review/conformance/deployment_profiles.json").read_text(encoding="utf-8"))
        known = {item["profile_id"] for item in deployment_payload["profiles"]}
        for profile in matrix.profiles:
            self.assertIn(profile.deployment_profile, known, profile.profile_id)

    def test_rfc_scoped_profiles_require_correctness_checks(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        for profile in matrix.profiles:
            if profile.rfc_targets:
                self.assertTrue(profile.correctness_required, profile.profile_id)


    def test_matrix_declares_required_lanes_and_platforms(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        lanes = {profile.lane for profile in matrix.profiles}
        self.assertEqual(lanes, {'component_regression', 'end_to_end_release'})
        for profile in matrix.profiles:
            self.assertTrue(profile.certification_platforms, profile.profile_id)
            self.assertIn(profile.lane, {'component_regression', 'end_to_end_release'})


    def test_root_artifact_summary_declares_platform_and_lanes(self) -> None:
        summary = json.loads((CURRENT_ROOT / 'summary.json').read_text(encoding='utf-8'))
        self.assertIn('certification_platform', summary)
        self.assertTrue(summary['certification_platform'])
        self.assertEqual(set(summary['lane_counts']), {'component_regression', 'end_to_end_release'})
        self.assertGreater(summary['lane_counts']['component_regression'], 0)
        self.assertGreater(summary['lane_counts']['end_to_end_release'], 0)

    def test_rfc_scoped_profile_artifacts_record_correctness_requirements(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        for profile in matrix.profiles:
            if not profile.rfc_targets:
                continue
            correctness = json.loads((CURRENT_ROOT / profile.profile_id / 'correctness.json').read_text(encoding='utf-8'))
            self.assertTrue(correctness['required'], profile.profile_id)
            self.assertTrue(correctness['passed'], profile.profile_id)
            self.assertTrue(correctness['checks'], profile.profile_id)

    def test_end_to_end_release_profiles_preserve_live_listener_metadata(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        for profile in matrix.profiles:
            if profile.lane != 'end_to_end_release':
                continue
            self.assertTrue(profile.live_listener_required, profile.profile_id)
            for filename in ['result.json', 'summary.json', 'command.json', 'correctness.json']:
                payload = json.loads((CURRENT_ROOT / profile.profile_id / filename).read_text(encoding='utf-8'))
                self.assertEqual(payload['lane'], 'end_to_end_release', f'{profile.profile_id}::{filename}')
                self.assertTrue(payload['live_listener_required'], f'{profile.profile_id}::{filename}')

    def test_runner_can_execute_a_selected_profile_into_a_temp_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                artifact_root=Path(tmp) / 'perf',
                profile_ids=['http11_baseline'],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 1)
            profile_dir = Path(summary.artifact_root) / 'http11_baseline'
            self.assertTrue((profile_dir / 'result.json').exists())
            self.assertTrue((profile_dir / 'summary.json').exists())
            self.assertIn('p99_9_ms', summary.profiles[0].metrics)
            self.assertIn('time_to_first_byte_ms', summary.profiles[0].metrics)

if __name__ == '__main__':
    unittest.main()
