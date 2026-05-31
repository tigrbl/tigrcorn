from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.perf_runner import load_performance_matrix, run_performance_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/review/performance/runtime_comparison_matrix.json"


class RuntimeComparisonMatrixTests(unittest.TestCase):
    def test_runtime_matrix_declares_expected_profiles(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        self.assertEqual(
            [profile.profile_id for profile in matrix.profiles],
            ["runtime_auto", "runtime_asyncio", "runtime_uvloop"],
        )
        self.assertTrue(all(profile.driver == "runtime_scheduler" for profile in matrix.profiles))

    def test_runtime_matrix_uses_public_runtime_values(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        configured = {profile.driver_config["runtime"] for profile in matrix.profiles}
        self.assertEqual(configured, {"auto", "asyncio", "uvloop"})

    def test_runner_can_execute_auto_and_asyncio_runtime_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                matrix_path=MATRIX_PATH,
                artifact_root=Path(tmp) / "perf",
                profile_ids=["runtime_auto", "runtime_asyncio"],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 2)
            self.assertEqual(summary.failed, 0)
            for profile_id in ("runtime_auto", "runtime_asyncio"):
                profile_dir = Path(summary.artifact_root) / profile_id
                result = json.loads((profile_dir / "result.json").read_text(encoding="utf-8"))
                self.assertTrue(result["passed"], profile_id)
                self.assertEqual(result["metrics"]["profile_metadata"]["requested_runtime"], profile_id.removeprefix("runtime_"))

    def test_runner_can_execute_uvloop_runtime_profile_when_dependency_is_present(self) -> None:
        if importlib.util.find_spec("uvloop") is None:
            self.skipTest("uvloop is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                matrix_path=MATRIX_PATH,
                artifact_root=Path(tmp) / "perf",
                profile_ids=["runtime_uvloop"],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            result = json.loads((Path(summary.artifact_root) / "runtime_uvloop" / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["metrics"]["profile_metadata"]["effective_runtime"], "uvloop")


if __name__ == "__main__":
    unittest.main()
