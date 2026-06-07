from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs/review/performance/PERFORMANCE_OPTIONAL_COMPARISONS.md"
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"

OPTIONAL_FEATURE_IDS = {
    "feat:perf-runtime-loop-comparison",
    "feat:perf-http3-peer-aioquic-comparison",
    "feat:perf-websocket-peer-comparison",
}
OPTIONAL_CLAIM_IDS = {
    "clm:perf-runtime-loop-comparison",
    "clm:perf-http3-peer-aioquic-comparison",
    "clm:perf-websocket-peer-comparison",
}
OPTIONAL_TEST_IDS = {
    "tst:perf-runtime-loop-comparison": "tests/test_runtime_performance_matrix.py",
    "tst:perf-http3-peer-aioquic-comparison": "tests/test_aioquic_performance_matrix.py",
    "tst:perf-websocket-peer-comparison": "tests/test_websocket_peer_performance_matrix.py",
}


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_optional_performance_comparison_doc_exists() -> None:
    assert DOC_PATH.is_file()
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "outside the strict RFC certification boundary" in text
    assert "do not become active release proof" in text


def test_optional_performance_comparison_rows_are_tracked_in_registry() -> None:
    registry = _registry()
    features = {row["id"]: row for row in registry["features"]}
    claims = {row["id"]: row for row in registry["claims"]}
    tests = {row["id"]: row for row in registry["tests"]}
    evidence = {row["id"]: row for row in registry["evidence"]}
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    release = registry["releases"][0]

    boundary = boundaries["bnd:performance-comparison-optional"]
    assert boundary["status"] == "frozen"
    assert boundary["frozen"] is True
    assert set(boundary["feature_ids"]) == OPTIONAL_FEATURE_IDS
    assert boundary["profile_ids"] == []

    for feature_id in OPTIONAL_FEATURE_IDS:
        feature = features[feature_id]
        assert feature["implementation_status"] == "implemented"
        assert feature["plan"]["horizon"] == "explicit"
        assert feature["plan"]["target_claim_tier"] == "T2"

    for claim_id in OPTIONAL_CLAIM_IDS:
        claim = claims[claim_id]
        assert claim["tier"] == "T2"
        assert claim["status"] in {"implemented", "published"}
        assert claim_id not in release["claim_ids"]

    for test_id, path in OPTIONAL_TEST_IDS.items():
        row = tests[test_id]
        assert row["status"] == "passing"
        assert row["path"] == path
        assert row["claim_ids"]
        assert row["feature_ids"]
        assert len(row["evidence_ids"]) == 3
        for evidence_id in row["evidence_ids"]:
            assert evidence[evidence_id]["path"].startswith("docs/review/performance/")
            assert evidence_id not in release["evidence_ids"]


def test_optional_performance_features_do_not_enter_strict_boundaries() -> None:
    registry = _registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    excluded_boundaries = {
        "bnd:authoritative-0-3-9",
        "bnd:certification-explicit-surfaces",
        "bnd:category-http11",
        "bnd:category-http2",
        "bnd:category-http3",
        "bnd:category-websockets",
        "bnd:category-quic",
    }

    for boundary_id in excluded_boundaries:
        assert OPTIONAL_FEATURE_IDS.isdisjoint(boundaries[boundary_id]["feature_ids"]), boundary_id


def test_committed_registry_tracks_optional_performance_comparison_rows() -> None:
    registry = _registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    assert "bnd:performance-comparison-optional" in boundaries
