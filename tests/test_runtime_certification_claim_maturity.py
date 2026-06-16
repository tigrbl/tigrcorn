import json
from collections import defaultdict
from pathlib import Path


TARGET_FEATURES = {
    "feat:runtime-capability-registry",
    "feat:runtime-describe-contract",
    "feat:embedded-resource-ownership",
    "feat:contract-registry-and-traceability",
    "feat:transport-certification-domains",
    "feat:quic-operational-security-certification",
    "feat:webtransport-resource-governance",
    "feat:static-delivery-security-certification",
    "feat:http-entity-range-content-coding-certification",
    "feat:protocol-aware-observability",
    "feat:reproducible-signed-certification-artifacts",
    "feat:supply-chain-evidence-release-provenance",
}

PUBLIC_SURFACE_TESTS = {
    "feat:runtime-capability-registry": {
        "tst:runtime-capability-registry-export",
        "tst:runtime-capability-state-taxonomy",
    },
    "feat:runtime-describe-contract": {
        "tst:runtime-describe-public-api-shape",
        "tst:runtime-describe-empty-server-state",
    },
    "feat:embedded-resource-ownership": {
        "tst:embedded-resource-ownership-model-shape",
        "tst:embedded-resource-owner-ids-deterministic",
    },
    "feat:contract-registry-and-traceability": {
        "tst:contract-registry-record-shape",
        "tst:contract-registry-deterministic-export",
    },
    "feat:transport-certification-domains": {
        "tst:transport-domain-registry-shape",
        "tst:transport-domain-deterministic-export",
    },
    "feat:quic-operational-security-certification": {
        "tst:quic-security-certification-artifact-shape",
        "tst:quic-security-profile-discovery",
    },
    "feat:webtransport-resource-governance": {
        "tst:webtransport-budget-model-shape",
        "tst:webtransport-governance-config-export",
    },
    "feat:static-delivery-security-certification": {
        "tst:static-security-policy-shape",
        "tst:static-delivery-certification-artifact-shape",
    },
    "feat:http-entity-range-content-coding-certification": {
        "tst:http-certification-surface-shape",
        "tst:http-certification-artifact-deterministic",
    },
    "feat:protocol-aware-observability": {
        "tst:observability-protocol-label-schema",
        "tst:observability-deterministic-event-shape",
    },
    "feat:reproducible-signed-certification-artifacts": {
        "tst:cert-artifact-manifest-shape",
        "tst:cert-artifact-output-directory-contract",
    },
    "feat:supply-chain-evidence-release-provenance": {
        "tst:supply-chain-evidence-manifest-shape",
        "tst:supply-chain-package-list-deterministic",
    },
}

RUNTIME_INTEGRATION_TESTS = {
    "feat:runtime-capability-registry": {
        "tst:runtime-capability-profile-validation",
        "tst:runtime-capability-unsupported-fail-closed",
    },
    "feat:runtime-describe-contract": {
        "tst:runtime-describe-active-listeners",
        "tst:runtime-describe-protocol-transport-tls-state",
    },
    "feat:embedded-resource-ownership": {
        "tst:embedded-resource-shutdown-ownership",
        "tst:embedded-resource-restart-reload-ownership",
    },
    "feat:contract-registry-and-traceability": {
        "tst:contract-registry-owning-package-links",
        "tst:contract-registry-certified-vs-implemented",
    },
    "feat:transport-certification-domains": {
        "tst:transport-domain-capability-discovery",
        "tst:transport-domain-diagnostics-output",
    },
    "feat:quic-operational-security-certification": {
        "tst:quic-retry-token-accept-reject",
        "tst:quic-loss-recovery-evidence",
    },
    "feat:webtransport-resource-governance": {
        "tst:webtransport-max-streams-enforced",
        "tst:webtransport-max-datagrams-enforced",
    },
    "feat:static-delivery-security-certification": {
        "tst:static-traversal-dotdot-rejected",
        "tst:static-symlink-escape-rejected",
    },
    "feat:http-entity-range-content-coding-certification": {
        "tst:http-etag-weak-validator",
        "tst:http-content-coding-policy",
    },
    "feat:protocol-aware-observability": {
        "tst:observability-protocol-transport-labels",
        "tst:observability-tls-alpn-labels",
    },
    "feat:reproducible-signed-certification-artifacts": {
        "tst:cert-artifact-protocol-json-deterministic",
        "tst:cert-artifact-runtime-json-deterministic",
    },
    "feat:supply-chain-evidence-release-provenance": {
        "tst:supply-chain-spdx-or-cyclonedx-present",
        "tst:supply-chain-slsa-provenance-present",
    },
}


def _registry() -> dict:
    return json.loads(Path(".ssot/registry.json").read_text(encoding="utf-8"))


def _feature_claims(registry: dict) -> dict[str, list[dict]]:
    claims_by_feature: dict[str, list[dict]] = defaultdict(list)
    claim_by_id = {claim["id"]: claim for claim in registry["claims"]}

    for feature in registry["features"]:
        for claim_id in feature.get("claim_ids", []):
            claims_by_feature[feature["id"]].append(claim_by_id[claim_id])

    for claim in registry["claims"]:
        for feature_id in claim.get("feature_ids", []):
            if claim not in claims_by_feature[feature_id]:
                claims_by_feature[feature_id].append(claim)

    return claims_by_feature


def test_runtime_certification_features_have_certified_t2_without_lower_caps() -> None:
    registry = _registry()
    features = {feature["id"]: feature for feature in registry["features"]}
    claims_by_id = {claim["id"]: claim for claim in registry["claims"]}
    claims_by_feature = _feature_claims(registry)
    tier_order = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}

    def lineage_ids(claim: dict) -> set[str]:
        lineage: set[str] = {claim["id"]}
        pending = list(claim.get("depends_on_claim_ids", []))
        while pending:
            claim_id = pending.pop()
            if claim_id in lineage:
                continue
            lineage.add(claim_id)
            pending.extend(claims_by_id[claim_id].get("depends_on_claim_ids", []))
        return lineage

    for feature_id in sorted(TARGET_FEATURES):
        feature = features[feature_id]
        target_tier = feature["plan"]["target_claim_tier"]
        claims = claims_by_feature[feature_id]
        satisfying_claims = [
            claim
            for claim in claims
            if claim["tier"] == target_tier
            and claim["status"] in {"certified", "published"}
        ]
        satisfying_lineage = set().union(
            *(lineage_ids(claim) for claim in satisfying_claims)
        )

        assert satisfying_claims, feature_id
        lower_claims_outside_lineage = [
            claim["id"]
            for claim in claims
            if tier_order[claim["tier"]] < tier_order[target_tier]
            and claim["id"] not in satisfying_lineage
        ]
        assert not lower_claims_outside_lineage, (
            feature_id,
            lower_claims_outside_lineage,
        )


def test_runtime_certification_features_have_passing_t0_t1_runtime_proof() -> None:
    registry = _registry()
    tests = {test["id"]: test for test in registry["tests"]}

    for feature_id in sorted(TARGET_FEATURES):
        for test_id in sorted(PUBLIC_SURFACE_TESTS[feature_id]):
            test = tests[test_id]
            assert feature_id in test["feature_ids"], test_id
            assert test["status"] == "passing", test_id

        for test_id in sorted(RUNTIME_INTEGRATION_TESTS[feature_id]):
            test = tests[test_id]
            assert feature_id in test["feature_ids"], test_id
            assert test["status"] == "passing", test_id


def test_webtransport_live_transcript_has_certified_runtime_claims() -> None:
    registry = _registry()
    tests = {test["id"]: test for test in registry["tests"]}
    claims = _feature_claims(registry)[
        "feat:webtransport-live-quic-h3-connect-transcript"
    ]

    transcript_test = tests["tst:webtransport-live-quic-h3-connect-transcript-proof"]
    assert transcript_test["status"] == "passing"
    assert (
        "feat:webtransport-live-quic-h3-connect-transcript"
        in transcript_test["feature_ids"]
    )
    assert any(
        claim["tier"] == "T1" and claim["status"] in {"certified", "published"}
        for claim in claims
    )
    assert any(
        claim["tier"] == "T2" and claim["status"] in {"certified", "published"}
        for claim in claims
    )


def test_contract_registry_placeholder_tests_are_real_pytest_rows() -> None:
    registry = _registry()
    tests = {test["id"]: test for test in registry["tests"]}

    for test_id in (
        "tst:contract-registry-certified-vs-implemented",
        "tst:contract-registry-owning-package-links",
    ):
        test = tests[test_id]
        assert test["kind"] == "pytest"
        assert test["status"] == "passing"
        assert test["path"] == "tests/test_contract_registry_traceability.py"
