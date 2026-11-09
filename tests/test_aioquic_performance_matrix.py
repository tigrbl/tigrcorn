from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.perf_runner import load_performance_matrix, run_performance_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/review/performance/aioquic_comparison_matrix.json"


class AioquicComparisonMatrixTests(unittest.TestCase):
    def test_matrix_declares_expected_profiles(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        self.assertEqual(
            [profile.profile_id for profile in matrix.profiles],
            ["http3_prepare_tigrcorn", "http3_prepare_aioquic"],
        )
        self.assertTrue(all(profile.driver == "http3_peer_prepare" for profile in matrix.profiles))

    def test_internal_profile_runs_in_temp_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                matrix_path=MATRIX_PATH,
                artifact_root=Path(tmp) / "perf",
                profile_ids=["http3_prepare_tigrcorn"],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            result = json.loads((Path(summary.artifact_root) / "http3_prepare_tigrcorn" / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["metrics"]["profile_metadata"]["backend"], "tigrcorn")

    def test_aioquic_profile_runs_when_dependency_is_present(self) -> None:
        if importlib.util.find_spec("aioquic") is None:
            self.skipTest("aioquic is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                matrix_path=MATRIX_PATH,
                artifact_root=Path(tmp) / "perf",
                profile_ids=["http3_prepare_aioquic"],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            result = json.loads((Path(summary.artifact_root) / "http3_prepare_aioquic" / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["metrics"]["profile_metadata"]["backend"], "aioquic")


if __name__ == "__main__":
    unittest.main()
