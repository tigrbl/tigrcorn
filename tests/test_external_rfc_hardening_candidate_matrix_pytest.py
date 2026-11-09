from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from tigrcorn.compat.interop_runner import ExternalInteropRunner, load_external_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/review/conformance/external_matrix.rfc_hardening_candidate.json"
RELEASE_ROOT = ROOT / "docs/review/conformance/releases/0.3.6-rfc-hardening/release-0.3.6-rfc-hardening/tigrcorn-rfc-hardening-candidate-matrix"
EXPECTED_SCENARIO_IDS = {
    "http2-tls-server-curl-client",
    "websocket-http2-server-h2-client",
}


def test_candidate_matrix_document_covers_added_http2_independent_peers() -> None:
    matrix = load_external_matrix(MATRIX_PATH)
    assert matrix.name == "tigrcorn-rfc-hardening-candidate-matrix"
    assert {scenario.id for scenario in matrix.scenarios} == EXPECTED_SCENARIO_IDS
    assert {scenario.peer for scenario in matrix.scenarios} == {"curl", "python-h2"}


def test_committed_candidate_artifact_bundle_is_present_and_passing() -> None:
    assert RELEASE_ROOT.exists()
    index_payload = json.loads((RELEASE_ROOT / "index.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads((RELEASE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert index_payload["total"] == 2
    assert index_payload["passed"] == 2
    assert index_payload["failed"] == 0
    assert manifest_payload["environment"]["tigrcorn"]["commit_hash"] == "release-0.3.6-rfc-hardening"
    assert manifest_payload["environment"]["tigrcorn"]["version"] == "0.3.6"
    assert "curl" in manifest_payload["environment"]["tools"]

    scenarios = {item["id"]: item for item in index_payload["scenarios"]}
    assert set(scenarios) == EXPECTED_SCENARIO_IDS
    for scenario_id in EXPECTED_SCENARIO_IDS:
        result = json.loads((RELEASE_ROOT / scenario_id / "result.json").read_text(encoding="utf-8"))
        assert result["passed"]
        assert (RELEASE_ROOT / scenario_id / "packet_trace.jsonl").exists()
        assert (RELEASE_ROOT / scenario_id / "peer_transcript.json").exists()
        assert result["peer"]["exit_code"] == 0


def test_candidate_matrix_can_be_replayed_with_local_independent_peers() -> None:
    if os.environ.get("TIGRCORN_RUN_EXTERNAL_RFC_HARDENING_MATRIX") != "1":
        pytest.skip("set TIGRCORN_RUN_EXTERNAL_RFC_HARDENING_MATRIX=1 to rerun the HTTP/2 hardening matrix")
    if shutil.which("curl") is None:
        pytest.skip("curl is not available")
    if importlib.util.find_spec("h2") is None:
        pytest.skip("python-h2 is not available")

    with tempfile.TemporaryDirectory() as artifact_root:
        prior = os.environ.get("TIGRCORN_COMMIT_HASH")
        os.environ["TIGRCORN_COMMIT_HASH"] = "test-rfc-hardening-candidate-matrix"
        try:
            runner = ExternalInteropRunner(
                matrix=load_external_matrix(MATRIX_PATH),
                artifact_root=artifact_root,
                source_root=ROOT,
            )
            summary = runner.run()
        finally:
            if prior is None:
                os.environ.pop("TIGRCORN_COMMIT_HASH", None)
            else:
                os.environ["TIGRCORN_COMMIT_HASH"] = prior

    assert summary.total == 2
    assert summary.passed == 2
    assert summary.failed == 0
    assert {item.scenario_id for item in summary.scenarios} == EXPECTED_SCENARIO_IDS
