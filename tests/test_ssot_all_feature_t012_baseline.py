from __future__ import annotations

from pathlib import Path

from tigrcorn.ssot_baseline import (
    BASELINE_TIERS,
    baseline_claims_have_concrete_proof,
    feature_ids_partial_only_for_baseline,
    iter_feature_baselines,
    load_registry,
    missing_baseline_tiers,
    unlinked_t0_claim_ids,
)


ROOT = Path(__file__).resolve().parents[1]
PROOF_STATUSES = {"evidenced", "certified", "promoted", "published"}


def test_all_features_have_t0_t1_t2_claims() -> None:
    registry = load_registry(ROOT)

    missing = missing_baseline_tiers(registry)

    assert not missing, missing
    assert {baseline.feature_id for baseline in iter_feature_baselines(registry)}
    assert all(set(BASELINE_TIERS).issubset(baseline.claim_tiers) for baseline in iter_feature_baselines(registry))


def test_t0_claims_are_linked_to_features() -> None:
    registry = load_registry(ROOT)

    assert unlinked_t0_claim_ids(registry) == ()


def test_t0_t1_t2_claims_have_concrete_passing_proof() -> None:
    registry = load_registry(ROOT)

    failures = baseline_claims_have_concrete_proof(registry)

    assert not failures, failures


def test_no_feature_is_partial_only_because_baseline_proof_is_missing() -> None:
    registry = load_registry(ROOT)

    assert feature_ids_partial_only_for_baseline(registry) == ()


def test_all_current_features_are_implemented_at_t2_floor() -> None:
    registry = load_registry(ROOT)
    claims = {claim["id"]: claim for claim in registry["claims"]}

    not_implemented = [
        feature["id"]
        for feature in registry["features"]
        if feature["implementation_status"] != "implemented"
    ]
    assert not_implemented == []

    missing_evidenced_tiers: dict[str, set[str]] = {}
    for feature in registry["features"]:
        evidenced_tiers = {
            claims[claim_id]["tier"]
            for claim_id in feature.get("claim_ids", [])
            if claim_id in claims and claims[claim_id].get("status") in PROOF_STATUSES
        }
        for claim in claims.values():
            if feature["id"] in claim.get("feature_ids", []) and claim.get("status") in PROOF_STATUSES:
                evidenced_tiers.add(claim["tier"])
        missing = {"T1", "T2"} - evidenced_tiers
        if missing:
            missing_evidenced_tiers[feature["id"]] = missing

    assert missing_evidenced_tiers == {}


def test_all_feature_t2_release_excludes_asserted_only_higher_tier_claims() -> None:
    registry = load_registry(ROOT)
    claims = {claim["id"]: claim for claim in registry["claims"]}
    releases = {release["id"]: release for release in registry["releases"]}
    release = releases["rel:all-current-features-t2-closure-2026-06-01"]

    assert release["status"] == "published"
    assert release["boundary_id"] == "bnd:all-current-features-t2-closure-2026-06-01"
    assert len(release["claim_ids"]) > 0
    assert len(release["evidence_ids"]) > 0

    asserted_higher_tier_claims = [
        claim_id
        for claim_id in release["claim_ids"]
        if claims[claim_id].get("tier") in {"T3", "T4"}
        and claims[claim_id].get("status") not in PROOF_STATUSES
    ]
    assert asserted_higher_tier_claims == []
