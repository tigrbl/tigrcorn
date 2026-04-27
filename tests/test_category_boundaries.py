from __future__ import annotations

from tools.ssot_sync import build_registry


CATEGORY_BOUNDARY_IDS = {
    "bnd:category-asgi3",
    "bnd:category-tigr-asgi-contract",
    "bnd:category-http11",
    "bnd:category-http2",
    "bnd:category-http3",
    "bnd:category-quic",
    "bnd:category-mtls",
    "bnd:category-websockets",
    "bnd:category-webtransport",
}


def test_category_boundaries_exist_with_explicit_feature_scope() -> None:
    registry = build_registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    features = {row["id"] for row in registry["features"]}

    assert CATEGORY_BOUNDARY_IDS <= set(boundaries)
    for boundary_id in CATEGORY_BOUNDARY_IDS:
        boundary = boundaries[boundary_id]
        assert boundary["status"] == "draft"
        assert boundary["frozen"] is False
        assert boundary["canonical_registry_source"] == ".ssot/registry.json"
        assert boundary["feature_ids"], boundary_id
        assert set(boundary["feature_ids"]) <= features
