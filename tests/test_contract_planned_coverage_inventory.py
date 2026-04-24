from __future__ import annotations

from tools.ssot_sync import build_registry


def test_contract_and_asgi3_features_have_planned_test_links() -> None:
    registry = build_registry()
    features = {row["id"]: row for row in registry["features"]}

    required_feature_ids = {
        feature_id
        for feature_id, row in features.items()
        if row["plan"]["slot"]
        in {
            "asgi3-compatibility",
            "app-interface-selection",
            "binding-classification",
            "capabilities",
            "compatibility-exclusion",
            "compatibility-reporting",
            "completion",
            "contract-events",
            "contract-runtime",
            "contract-scopes",
            "datagrams",
            "dispatch-selection",
            "documentation",
            "flow-control",
            "governance",
            "http-feature-mapping",
            "identity",
            "metadata",
            "public-api",
            "release-evidence",
            "streams",
            "validation",
            "verification",
            "webtransport-contract",
        }
    }
    required_feature_ids.update(
        {
            "feat:rest-runtime-exclusion",
            "feat:json-rpc-runtime-exclusion",
        }
    )

    tests = registry["tests"]
    planned_test_feature_ids = {
        feature_id
        for row in tests
        if row["id"].startswith("tst:planned-")
        for feature_id in row["feature_ids"]
    }

    assert required_feature_ids <= planned_test_feature_ids


def test_unsupported_compatibility_surfaces_are_exclusion_features_only() -> None:
    registry = build_registry()
    features = {row["id"]: row for row in registry["features"]}

    unsupported_ids = {
        "feat:asgi2-compat-exclusion",
        "feat:wsgi-compat-exclusion",
        "feat:rsgi-compat-exclusion",
    }
    unsupported_adapter_ids = {
        "feat:asgi2-compat-adapter",
        "feat:wsgi-compat-adapter",
        "feat:rsgi-like-adapter",
    }

    assert unsupported_adapter_ids.isdisjoint(features)
    for feature_id in unsupported_ids:
        feature = features[feature_id]
        assert feature["implementation_status"] == "absent"
        assert feature["plan"]["horizon"] == "out_of_bounds"
        assert feature["plan"]["slot"] == "compatibility-exclusion"
