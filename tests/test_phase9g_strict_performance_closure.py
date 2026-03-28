from __future__ import annotations

import json
import unittest
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_promotion_target
from tigrcorn.compat.perf_runner import validate_performance_artifacts

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
PERFORMANCE = ROOT / 'docs' / 'review' / 'performance'
CURRENT_ROOT = ROOT / 'docs' / 'review' / 'performance' / 'artifacts' / 'phase6_current_release'


class Phase9GStrictPerformanceClosureTests(unittest.TestCase):
    def _load_json(self, relative_path: str) -> dict:
        return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))

    def test_phase9g_docs_and_status_exist(self) -> None:
        self.assertTrue((CONFORMANCE / 'PHASE9G_STRICT_PERFORMANCE_CLOSURE.md').exists())
        self.assertTrue((CONFORMANCE / 'phase9g_strict_performance.current.json').exists())
        self.assertTrue((ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9G_STRICT_PERFORMANCE_CLOSURE.md').exists())
        status = self._load_json('docs/review/conformance/phase9g_strict_performance.current.json')
        self.assertEqual(status['phase'], '9G')
        self.assertEqual(status['checkpoint'], 'phase9g_strict_performance_closure')
        self.assertTrue(status['current_state']['performance_passed'])
        self.assertFalse(status['current_state']['promotion_target_passed'])

    def test_matrix_declares_required_lanes_platforms_and_threshold_keys(self) -> None:
        matrix = self._load_json('docs/review/performance/performance_matrix.json')
        lanes = {profile['lane'] for profile in matrix['profiles']}
        self.assertEqual(lanes, {'component_regression', 'end_to_end_release'})
        self.assertTrue(matrix['metadata']['certification_platforms'])
        for profile in matrix['profiles']:
            thresholds = profile['thresholds']
            self.assertIn('max_p50_ms', thresholds)
            self.assertIn('max_p95_ms', thresholds)
            self.assertIn('max_p99_ms', thresholds)
            self.assertIn('max_p99_9_ms', thresholds)
            self.assertIn('max_time_to_first_byte_ms', thresholds)
            self.assertIn('max_handshake_latency_ms', thresholds)
            self.assertIn('max_protocol_stalls', thresholds)
            self.assertIn('max_rss_kib', thresholds)
            self.assertIn('max_scheduler_rejections', thresholds)
            budget = profile['relative_regression_budget']
            self.assertIn('max_p99_9_increase_fraction', budget)
            self.assertIn('max_cpu_increase_fraction', budget)
            self.assertIn('max_rss_increase_fraction', budget)

    def test_current_artifacts_expose_required_metric_keys_and_files(self) -> None:
        matrix = self._load_json('docs/review/performance/performance_matrix.json')
        for profile in matrix['profiles']:
            profile_dir = CURRENT_ROOT / profile['profile_id']
            self.assertTrue((profile_dir / 'result.json').exists(), profile['profile_id'])
            self.assertTrue((profile_dir / 'summary.json').exists(), profile['profile_id'])
            self.assertTrue((profile_dir / 'correctness.json').exists(), profile['profile_id'])
            result = json.loads((profile_dir / 'result.json').read_text(encoding='utf-8'))
            self.assertIn('p99_9_ms', result['metrics'])
            self.assertIn('time_to_first_byte_ms', result['metrics'])
            self.assertIn('handshake_latency_ms', result['metrics'])
            self.assertIn('protocol_stalls', result['metrics'])

    def test_preserved_artifacts_validate_and_promotion_report_performance_section_is_green(self) -> None:
        failures = validate_performance_artifacts(
            ROOT,
            artifact_root='docs/review/performance/artifacts/phase6_current_release',
            baseline_root='docs/review/performance/artifacts/phase6_reference_baseline',
            require_relative_regression=True,
        )
        self.assertEqual(failures, [])
        report = evaluate_promotion_target(ROOT)
        self.assertTrue(report.performance.passed, msg=report.performance.failures)
        self.assertFalse(report.passed)
        self.assertFalse(report.strict_target_boundary.passed)


if __name__ == '__main__':
    unittest.main()
