from __future__ import annotations

from tools.ssot_sync import (
    QUIC_CATEGORY_FEATURE_IDS,
    TIGR_ASGI_CONTRACT_CATEGORY_FEATURE_IDS,
    WEBTRANSPORT_CATEGORY_FEATURE_IDS,
    build_registry,
)


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

CATEGORY_TIER_RULES = {
    "bnd:category-tigr-asgi-contract": (
        set(TIGR_ASGI_CONTRACT_CATEGORY_FEATURE_IDS),
        "T4",
        "clm:tigr-asgi-contract-category-t4-support",
    ),
    "bnd:category-quic": (
        set(QUIC_CATEGORY_FEATURE_IDS),
        "T4",
        "clm:quic-category-t4-support",
    ),
    "bnd:category-webtransport": (
        set(WEBTRANSPORT_CATEGORY_FEATURE_IDS),
        "T3",
        "clm:webtransport-category-t3-floor",
    ),
}


def test_category_boundaries_exist_with_explicit_feature_scope() -> None:
    registry = build_registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    features = {row["id"] for row in registry["features"]}

    assert CATEGORY_BOUNDARY_IDS <= set(boundaries)
    for boundary_id in CATEGORY_BOUNDARY_IDS:
        boundary = boundaries[boundary_id]
        assert boundary["status"] == "frozen"
        assert boundary["frozen"] is True
        assert boundary["canonical_registry_source"] == ".ssot/registry.json"
        assert boundary["feature_ids"], boundary_id
        assert set(boundary["feature_ids"]) <= features


def test_category_boundaries_enforce_governed_claim_tiers() -> None:
    registry = build_registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    features = {row["id"]: row for row in registry["features"]}
    claims = {row["id"]: row for row in registry["claims"]}

    for boundary_id, (expected_feature_ids, expected_tier, expected_claim_id) in CATEGORY_TIER_RULES.items():
        boundary_feature_ids = set(boundaries[boundary_id]["feature_ids"])
        assert boundary_feature_ids == expected_feature_ids

        category_claim = claims[expected_claim_id]
        assert category_claim["tier"] == expected_tier
        assert set(category_claim["feature_ids"]) == expected_feature_ids

        for feature_id in expected_feature_ids:
            feature = features[feature_id]
            assert feature["plan"]["target_claim_tier"] == expected_tier
            linked_claims = [claims[claim_id] for claim_id in feature["claim_ids"]]
            assert any(claim["tier"] == expected_tier for claim in linked_claims), feature_id
