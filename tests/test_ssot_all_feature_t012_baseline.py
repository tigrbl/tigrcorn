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
