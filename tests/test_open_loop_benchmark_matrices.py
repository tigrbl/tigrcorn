from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.drivers_vegeta import parse_vegeta_report_json
from benchmarks.drivers_wrk2 import parse_wrk2_latency_output
from benchmarks.open_loop_common import require_binary
from benchmarks.profiles import REQUIRED_PROFILE_IDS
from benchmarks.registry import get_driver
from tigrcorn.compat.perf_runner import load_performance_matrix, run_performance_matrix

ROOT = Path(__file__).resolve().parents[1]
WRK2_MATRIX = ROOT / "docs/review/performance/wrk2_benchmark_matrix.json"
VEGETA_MATRIX = ROOT / "docs/review/performance/vegeta_benchmark_matrix.json"
STRICT_MATRIX = ROOT / "docs/review/performance/performance_matrix.json"


def _mock_measurement() -> dict:
    return {
        "samples_ms": [1.0, 1.5, 2.0, 2.5, 3.0],
        "total_duration_seconds": 1.0,
        "total_attempts": 5,
        "total_units": 5,
        "error_count": 0,
        "cpu_seconds": 0.01,
        "rss_kib": 1.0,
        "connections": 1,
        "streams": 0,
        "scheduler_rejections": 0,
        "protocol_stall_counts": {},
        "correctness_checks": {"mock_open_loop_completed": True},
        "correctness_note": "mocked open-loop benchmark result",
        "metadata": {
            "benchmark_tool": "mock",
            "tool_version": "test",
            "offered_rate": 5,
            "duration_seconds": 1.0,
            "connections": 1,
            "target_url": "http://127.0.0.1:1/plain",
            "pattern_name": "mock",
            "phase_name": "mock",
        },
        "time_to_first_byte_ms": 1.0,
        "handshake_latency_ms": 1.0,
    }


class OpenLoopBenchmarkMatrixTests(unittest.TestCase):
    def test_wrk2_and_vegeta_matrices_load_separately(self) -> None:
        wrk2 = load_performance_matrix(WRK2_MATRIX)
        vegeta = load_performance_matrix(VEGETA_MATRIX)

        self.assertEqual(wrk2.matrix_name, "tigrcorn-wrk2-open-loop-benchmark-matrix")
        self.assertEqual(vegeta.matrix_name, "tigrcorn-vegeta-open-loop-benchmark-matrix")
        self.assertEqual({profile.lane for profile in wrk2.profiles}, {"wrk2_open_loop"})
        self.assertEqual({profile.lane for profile in vegeta.profiles}, {"vegeta_open_loop"})

    def test_open_loop_profile_ids_are_not_strict_profile_ids(self) -> None:
        strict_ids = set(REQUIRED_PROFILE_IDS)
        wrk2_ids = {profile.profile_id for profile in load_performance_matrix(WRK2_MATRIX).profiles}
        vegeta_ids = {profile.profile_id for profile in load_performance_matrix(VEGETA_MATRIX).profiles}

        self.assertTrue(wrk2_ids.isdisjoint(strict_ids))
        self.assertTrue(vegeta_ids.isdisjoint(strict_ids))
        self.assertTrue(wrk2_ids.isdisjoint(vegeta_ids))

    def test_open_loop_artifact_roots_do_not_reuse_strict_roots(self) -> None:
        strict = load_performance_matrix(STRICT_MATRIX)
        wrk2 = load_performance_matrix(WRK2_MATRIX)
        vegeta = load_performance_matrix(VEGETA_MATRIX)

        strict_roots = {strict.current_artifact_root, strict.baseline_artifact_root}
        self.assertNotIn(wrk2.current_artifact_root, strict_roots)
        self.assertNotIn(wrk2.baseline_artifact_root, strict_roots)
        self.assertNotIn(vegeta.current_artifact_root, strict_roots)
        self.assertNotIn(vegeta.baseline_artifact_root, strict_roots)
        self.assertIn("wrk2_open_loop_current", wrk2.current_artifact_root)
        self.assertIn("vegeta_open_loop_current", vegeta.current_artifact_root)

    def test_driver_registry_exposes_open_loop_drivers(self) -> None:
        for driver_id in (
            "wrk2_http11_constant_rate",
            "wrk2_http11_step_rate",
            "vegeta_http11_constant_rate",
            "vegeta_http11_step_rate",
            "vegeta_http11_recovery_pattern",
        ):
            self.assertTrue(callable(get_driver(driver_id)), driver_id)

    def test_missing_external_binary_fails_clearly(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "required open-loop benchmark binary not found"):
            require_binary("definitely-missing-tigrcorn-open-loop-binary")

    def test_wrk2_latency_parser_handles_representative_output(self) -> None:
        output = """
Running 10s test @ http://127.0.0.1:8000/plain
  2 threads and 64 connections
  Latency Distribution (HdrHistogram - Recorded Latency)
 50.000%    1.15ms
 95.000%    3.00ms
 99.000%    8.50ms
 99.900%   20.00ms
 10000 requests in 10.00s, 1.20MB read
Requests/sec:   1000.00
Socket errors: connect 0, read 1, write 0, timeout 2
Non-2xx or 3xx responses: 4
"""
        parsed = parse_wrk2_latency_output(output)

        self.assertEqual(parsed["total_attempts"], 10000)
        self.assertEqual(parsed["total_duration_seconds"], 10.0)
        self.assertEqual(parsed["throughput_ops_per_sec"], 1000.0)
        self.assertEqual(parsed["error_count"], 7)
        self.assertEqual(parsed["percentiles_ms"]["p99_9"], 20.0)

    def test_vegeta_json_parser_handles_representative_report(self) -> None:
        output = json.dumps(
            {
                "latencies": {
                    "50th": 1_000_000,
                    "95th": 3_000_000,
                    "99th": 8_000_000,
                    "99.9th": 12_000_000,
                },
                "duration": 10_000_000_000,
                "requests": 1000,
                "rate": 100.0,
                "throughput": 99.5,
                "success": 0.998,
                "status_codes": {"200": 998, "503": 2},
                "errors": ["two errors"],
            }
        )
        parsed = parse_vegeta_report_json(output)

        self.assertEqual(parsed["total_attempts"], 1000)
        self.assertEqual(parsed["total_duration_seconds"], 10.0)
        self.assertEqual(parsed["throughput_ops_per_sec"], 99.5)
        self.assertEqual(parsed["error_count"], 2)
        self.assertEqual(parsed["percentiles_ms"]["p95"], 3.0)

    def test_runner_can_write_wrk2_artifacts_with_mocked_driver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("benchmarks.drivers_wrk2._run_wrk2_http11", return_value=_mock_measurement()):
                summary = run_performance_matrix(
                    ROOT,
                    matrix_path=WRK2_MATRIX,
                    artifact_root=Path(tmp) / "wrk2",
                    profile_ids=["wrk2_http11_baseline_constant_rate"],
                    establish_baseline=True,
                )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            profile_dir = Path(summary.artifact_root) / "wrk2_http11_baseline_constant_rate"
            self.assertTrue((profile_dir / "result.json").exists())
            self.assertTrue((profile_dir / "command.json").exists())

    def test_runner_can_write_vegeta_artifacts_with_mocked_driver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("benchmarks.drivers_vegeta._run_vegeta_http11", return_value=_mock_measurement()):
                summary = run_performance_matrix(
                    ROOT,
                    matrix_path=VEGETA_MATRIX,
                    artifact_root=Path(tmp) / "vegeta",
                    profile_ids=["vegeta_http11_warmup_baseline"],
                    establish_baseline=True,
                )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            profile_dir = Path(summary.artifact_root) / "vegeta_http11_warmup_baseline"
            self.assertTrue((profile_dir / "result.json").exists())
            self.assertTrue((profile_dir / "correctness.json").exists())


if __name__ == "__main__":
    unittest.main()
