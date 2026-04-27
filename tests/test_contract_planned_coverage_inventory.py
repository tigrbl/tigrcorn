from __future__ import annotations

from tools.ssot_sync import build_registry


def test_contract_and_asgi3_features_have_test_links() -> None:
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
            "endpoint-metadata",
            "flow-control",
            "governance",
            "http-feature-mapping",
            "identity",
            "metadata",
            "public-api",
            "asgi3-extension-exposure",
            "rejection",
            "release-evidence",
            "security-metadata",
            "streams",
            "transport-identity",
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
    covered_feature_ids = {
        feature_id
        for row in tests
        if row["status"] in {"current", "passing", "planned"}
        for feature_id in row["feature_ids"]
    }

    assert required_feature_ids <= covered_feature_ids


def test_closed_contract_features_have_passing_executable_tests() -> None:
    registry = build_registry()
    tests = registry["tests"]

    closed_feature_ids = {
        "feat:webtransport-h3-quic-scope",
        "feat:webtransport-h3-quic-session-events",
        "feat:webtransport-h3-quic-stream-events",
        "feat:webtransport-h3-quic-datagram-events",
        "feat:webtransport-h3-quic-completion-events",
        "feat:tigr-asgi-contract-0-1-2-validation",
        "feat:generic-stream-runtime",
        "feat:generic-datagram-runtime",
        "feat:stream-backpressure-mapping",
        "feat:datagram-flow-control-mapping",
        "feat:emit-completion-events",
        "feat:emit-completion-asgi-extension",
        "feat:rest-binding-classification",
        "feat:jsonrpc-binding-classification",
        "feat:sse-binding-classification",
        "feat:contract-listener-endpoint-metadata",
        "feat:contract-uds-endpoint-metadata",
        "feat:contract-fd-endpoint-metadata",
        "feat:contract-pipe-endpoint-metadata",
        "feat:contract-inproc-endpoint-metadata",
        "feat:contract-tcp-connection-identity",
        "feat:contract-unix-connection-identity",
        "feat:contract-quic-connection-identity",
        "feat:contract-http2-stream-identity",
        "feat:contract-http3-stream-identity",
        "feat:contract-webtransport-session-identity",
        "feat:contract-webtransport-stream-identity",
        "feat:contract-datagram-unit-identity",
        "feat:contract-tls-endpoint-metadata",
        "feat:contract-mtls-peer-metadata",
        "feat:contract-alpn-metadata",
        "feat:contract-sni-metadata",
        "feat:contract-ocsp-crl-metadata",
        "feat:asgi3-endpoint-metadata-extension",
        "feat:asgi3-transport-identity-extension",
        "feat:asgi3-security-metadata-extension",
        "feat:asgi3-stream-datagram-extension",
        "feat:contract-unsupported-scope-rejection",
        "feat:contract-lossy-metadata-rejection",
        "feat:contract-illegal-event-order-rejection",
        "feat:contract-invalid-endpoint-metadata-rejection",
        "feat:rest-runtime-exclusion",
        "feat:json-rpc-runtime-exclusion",
        "feat:asgi2-compat-exclusion",
        "feat:wsgi-compat-exclusion",
        "feat:rsgi-compat-exclusion",
        "feat:asgi3-compat-layer",
        "feat:asgi-extension-bridge",
        "feat:compat-feature-parity-matrix",
        "feat:alt-svc-contract-map",
        "feat:content-coding-contract-map",
        "feat:early-hints-contract-map",
        "feat:proxy-normalization-contract-map",
        "feat:static-delivery-contract-map",
        "feat:trailers-contract-map",
        "feat:observability-contract-metadata",
        "feat:contract-http-scope",
        "feat:contract-websocket-scope",
        "feat:contract-lifespan-scope",
        "feat:contract-webtransport-scope",
        "feat:contract-http-event-map",
        "feat:contract-websocket-event-map",
        "feat:contract-lifespan-event-map",
        "feat:contract-webtransport-events",
        "feat:unit-id-propagation",
        "feat:transport-metadata-model",
        "feat:tls-metadata-extension",
        "feat:family-capability-declaration",
        "feat:binding-legality-validation",
        "feat:contract-error-semantics",
        "feat:contract-docs-migration",
        "feat:contract-examples",
        "feat:ssot-contract-boundary-sync",
        "feat:contract-release-evidence",
        "feat:asgi3-app-compat-suite",
        "feat:contract-conformance-tests",
    }
    passing_feature_ids = {
        feature_id
        for row in tests
        if row["status"] == "passing" and row["path"].startswith("tests/test_") and not row["id"].startswith("tst:placeholder-")
        for feature_id in row["feature_ids"]
    }

    assert closed_feature_ids <= passing_feature_ids
    assert not any(row["id"].startswith("tst:placeholder-") for row in tests)


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
