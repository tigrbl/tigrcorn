from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"


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
    "bnd:category-tigr-asgi-contract": ("T4", "clm:tigr-asgi-contract-category-t4-support"),
    "bnd:category-quic": ("T4", "clm:quic-category-t4-support"),
    "bnd:category-webtransport": ("T3", "clm:webtransport-category-t3-floor"),
}

TIER_RANK = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_category_boundaries_exist_with_explicit_feature_scope() -> None:
    registry = _registry()
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
    registry = _registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    features = {row["id"]: row for row in registry["features"]}
    claims = {row["id"]: row for row in registry["claims"]}

    for boundary_id, (expected_tier, expected_claim_id) in CATEGORY_TIER_RULES.items():
        boundary_feature_ids = set(boundaries[boundary_id]["feature_ids"])
        assert boundary_feature_ids

        category_claim = claims[expected_claim_id]
        assert category_claim["tier"] == expected_tier
        category_claim_feature_ids = set(category_claim["feature_ids"])
        assert category_claim_feature_ids
        assert category_claim_feature_ids <= boundary_feature_ids

        for feature_id in boundary_feature_ids:
            feature = features[feature_id]
            assert TIER_RANK[feature["plan"]["target_claim_tier"]] <= TIER_RANK[expected_tier]
