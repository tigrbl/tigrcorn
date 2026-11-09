from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from tigrcorn.compat.interop_runner import ExternalInteropRunner, load_external_matrix, summarize_matrix_dimensions

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/review/conformance/external_matrix.current_release.json"
RELEASE_ROOT = ROOT / "docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-mixed-compatibility-release-matrix"
EXPECTED_SCENARIO_IDS = {
    "http1-server-curl-client",
    "http2-server-h2-client",
    "http2-tls-server-h2-client",
    "websocket-server-websockets-client",
    "websocket-http2-server-h2-client",
    "http3-server-public-client-post",
    "http3-server-public-client-post-mtls",
    "http3-server-public-client-post-retry",
    "http3-server-public-client-post-resumption",
    "http3-server-public-client-post-zero-rtt",
    "http3-server-public-client-post-migration",
    "http3-server-public-client-post-goaway-qpack",
    "websocket-http3-server-public-client",
    "websocket-http3-server-public-client-mtls",
}


def test_current_release_matrix_document_covers_expected_peers_and_dimensions() -> None:
    matrix = load_external_matrix(MATRIX_PATH)
    assert matrix.name == "tigrcorn-current-release-matrix"
    assert {scenario.id for scenario in matrix.scenarios} == EXPECTED_SCENARIO_IDS
    assert {scenario.peer for scenario in matrix.scenarios} == {"curl", "python-h2", "tigrcorn-public-client", "websockets"}
    assert matrix.metadata["evidence_tier"] == "mixed"
    assert matrix.metadata["canonical_release_root"] == "docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-mixed-compatibility-release-matrix"
    assert {scenario.evidence_tier for scenario in matrix.scenarios} == {"independent_certification", "same_stack_replay"}
    assert all(s.peer_process.provenance_kind == "same_stack_fixture" for s in matrix.scenarios if s.peer == "tigrcorn-public-client")

    dimensions = summarize_matrix_dimensions(matrix)
    assert dimensions["evidence_tier"] == ["independent_certification", "same_stack_replay"]
    assert dimensions["retry"] == [False, True]
    assert dimensions["resumption"] == [False, True]
    assert dimensions["zero_rtt"] == [False, True]
    assert dimensions["migration"] == [False, True]
    assert dimensions["goaway"] == [False, True]
    assert dimensions["qpack_blocking"] == [False, True]


def test_committed_current_release_artifact_bundle_is_present_and_passing() -> None:
    assert RELEASE_ROOT.exists()
    index_payload = json.loads((RELEASE_ROOT / "index.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads((RELEASE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert index_payload["total"] == 14
    assert index_payload["passed"] == 14
    assert index_payload["failed"] == 0
    assert manifest_payload["environment"]["tigrcorn"]["commit_hash"] == "release-0.3.9"
    assert manifest_payload["environment"]["tigrcorn"]["version"] == "0.3.9"
    assert manifest_payload["bundle_kind"] == "mixed"

    scenarios = {item["id"]: item for item in index_payload["scenarios"]}
    assert set(scenarios) == EXPECTED_SCENARIO_IDS

    h2_result = json.loads((RELEASE_ROOT / "http2-server-h2-client" / "result.json").read_text(encoding="utf-8"))
    assert h2_result["passed"]
    assert h2_result["negotiation"]["peer"]["protocol"] == "h2c"
    assert h2_result["transcript"]["peer"]["response"]["body"] == "echo:hello-http2"

    h3_result = json.loads((RELEASE_ROOT / "http3-server-public-client-post" / "result.json").read_text(encoding="utf-8"))
    assert h3_result["passed"]
    assert h3_result["negotiation"]["peer"]["protocol"] == "h3"
    assert (RELEASE_ROOT / "http3-server-public-client-post" / "qlog.json").exists()


def test_current_release_matrix_can_be_replayed_with_local_peers() -> None:
    if os.environ.get("TIGRCORN_RUN_EXTERNAL_CURRENT_RELEASE_MATRIX") != "1":
        pytest.skip("set TIGRCORN_RUN_EXTERNAL_CURRENT_RELEASE_MATRIX=1 to rerun the full current-release matrix")
    if shutil.which("curl") is None:
        pytest.skip("curl is not available")
    if importlib.util.find_spec("websockets") is None:
        pytest.skip("websockets is not available")
    if importlib.util.find_spec("h2") is None:
        pytest.skip("python-h2 is not available")

    with tempfile.TemporaryDirectory() as artifact_root:
        prior = os.environ.get("TIGRCORN_COMMIT_HASH")
        os.environ["TIGRCORN_COMMIT_HASH"] = "test-current-release-matrix"
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

    assert summary.total == 14
    assert summary.passed == 14
    assert summary.failed == 0
    assert {item.scenario_id for item in summary.scenarios} == EXPECTED_SCENARIO_IDS
