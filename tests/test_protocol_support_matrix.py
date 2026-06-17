from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"

def _registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _rows_by_id(name: str) -> dict[str, dict[str, object]]:
    rows = _registry()[name]
    assert isinstance(rows, list)
    return {str(row["id"]): row for row in rows if isinstance(row, dict)}


def test_http3_iana_registry_feature_links_existing_constant_proof() -> None:
    features = _rows_by_id("features")
    feature = features["feat:http3-iana-registry-conformance"]

    assert feature["implementation_status"] == "implemented"
    assert feature["plan"]["horizon"] == "next"
    assert {"spc:2003", "spc:2069"} <= set(feature["spec_ids"])
    assert "tst:webtransport-h3-draft13-iana-settings-frame-stream-error-capsule-constants" in feature["test_ids"]


def test_webtransport_initial_flow_settings_are_runtime_tracked() -> None:
    features = _rows_by_id("features")
    tests = _rows_by_id("tests")
    feature = features["feat:webtransport-h3-draft13-initial-flow-settings"]

    assert feature["implementation_status"] == "implemented"
    assert feature["plan"]["horizon"] == "next"
    assert "initial WebTransport flow-control settings" in feature["description"]
    assert {"spc:2061", "spc:2069"} <= set(feature["spec_ids"])
    assert "tst:webtransport-h3-initial-flow-settings-gap" in feature["test_ids"]
    assert tests["tst:webtransport-h3-initial-flow-settings-gap"]["path"] == "tests/test_webtransport_h3_draft13_settings.py"
    assert tests["tst:webtransport-h3-initial-flow-settings-gap"]["status"] == "passing"


def test_http2_connect_relay_feature_does_not_claim_general_proxying() -> None:
    features = _rows_by_id("features")
    feature = features["feat:http2-connect-relay-not-general-proxy"]

    assert feature["implementation_status"] == "implemented"
    assert feature["plan"]["horizon"] == "current"
    assert "general HTTP/2 forward or reverse proxy" in feature["description"]
    assert "tst:pytest-file-tests-test-connect-tunnel-h2-h3-py" in feature["test_ids"]


def test_protocol_support_matrix_named_tests_are_linked_to_evidence() -> None:
    tests = _rows_by_id("tests")
    expected_paths = {
        "tst:http3-iana-registry-conformance": "tests/test_webtransport_h3_draft13_iana.py",
        "tst:webtransport-h3-initial-flow-settings-gap": "tests/test_webtransport_h3_draft13_settings.py",
        "tst:http2-connect-relay-not-general-proxy": "tests/test_protocol_support_matrix.py",
        "tst:pytest-file-tests-test-connect-tunnel-h2-h3-py": "tests/test_connect_tunnel_h2_h3.py",
        "tst:protocol-support-matrix-drift": "tests/test_protocol_support_matrix.py",
    }

    for test_id, expected_path in expected_paths.items():
        test = tests[test_id]
        assert test["path"] == expected_path
        assert test["evidence_ids"], test_id
