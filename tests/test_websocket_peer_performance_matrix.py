from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tigrcorn.compat.perf_runner import load_performance_matrix, run_performance_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/review/performance/websocket_peer_comparison_matrix.json"


class WebSocketPeerComparisonMatrixTests(unittest.TestCase):
    def test_matrix_declares_expected_profiles(self) -> None:
        matrix = load_performance_matrix(MATRIX_PATH)
        self.assertEqual(
            [profile.profile_id for profile in matrix.profiles],
            ["websocket_frame_tigrcorn", "websocket_frame_wsproto", "websocket_frame_websockets"],
        )
        self.assertTrue(all(profile.driver == "websocket_peer_frame" for profile in matrix.profiles))

    def test_tigrcorn_profile_runs_in_temp_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                matrix_path=MATRIX_PATH,
                artifact_root=Path(tmp) / "perf",
                profile_ids=["websocket_frame_tigrcorn"],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            result = json.loads((Path(summary.artifact_root) / "websocket_frame_tigrcorn" / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["metrics"]["profile_metadata"]["backend"], "tigrcorn")

    def test_wsproto_profile_runs_when_dependency_is_present(self) -> None:
        if importlib.util.find_spec("wsproto") is None:
            self.skipTest("wsproto is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                matrix_path=MATRIX_PATH,
                artifact_root=Path(tmp) / "perf",
                profile_ids=["websocket_frame_wsproto"],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            result = json.loads((Path(summary.artifact_root) / "websocket_frame_wsproto" / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["metrics"]["profile_metadata"]["backend"], "wsproto")

    def test_websockets_profile_runs_when_dependency_is_present(self) -> None:
        if importlib.util.find_spec("websockets") is None:
            self.skipTest("websockets is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_performance_matrix(
                ROOT,
                matrix_path=MATRIX_PATH,
                artifact_root=Path(tmp) / "perf",
                profile_ids=["websocket_frame_websockets"],
                establish_baseline=True,
            )
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.failed, 0)
            result = json.loads((Path(summary.artifact_root) / "websocket_frame_websockets" / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["metrics"]["profile_metadata"]["backend"], "websockets")


if __name__ == "__main__":
    unittest.main()
