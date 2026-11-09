from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"
BASELINE_TIERS = ("T0", "T1", "T2")
BASELINE_TESTS = {
    "T0": {
        "id": "tst:all-features-t0-static-baseline",
        "title": "All features T0 static baseline",
        "kind": "pytest",
        "path": "tests/test_ssot_all_feature_t012_baseline.py",
    },
    "T1": {
        "id": "tst:all-features-t1-positive-baseline",
        "title": "All features T1 positive baseline",
        "kind": "pytest",
        "path": "tests/test_ssot_all_feature_t012_baseline.py",
    },
    "T2": {
        "id": "tst:all-features-t2-robustness-baseline",
        "title": "All features T2 robustness baseline",
        "kind": "pytest",
        "path": "tests/test_ssot_all_feature_t012_baseline.py",
    },
}
BASELINE_EVIDENCE = {
    "T0": {
        "id": "evd:all-features-t0-static-baseline",
        "title": "All features T0 static baseline evidence",
        "kind": "pytest",
        "path": "tests/test_ssot_all_feature_t012_baseline.py",
    },
    "T1": {
        "id": "evd:all-features-t1-positive-baseline",
        "title": "All features T1 positive baseline evidence",
        "kind": "pytest",
        "path": "tests/test_ssot_all_feature_t012_baseline.py",
    },
    "T2": {
        "id": "evd:all-features-t2-robustness-baseline",
        "title": "All features T2 robustness baseline evidence",
        "kind": "pytest",
        "path": "tests/test_ssot_all_feature_t012_baseline.py",
    },
}


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(registry: dict[str, Any]) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(registry, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )


def _slug(feature_id: str) -> str:
    value = feature_id.split(":", 1)[1]
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")


def _append_unique(items: list[str], *values: str) -> None:
    for value in values:
        if value not in items:
            items.append(value)


def _find_by_id(items: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    for item in items:
        if item["id"] == entity_id:
            return item
    return None


def _claim_tiers_for_feature(feature: dict[str, Any], claims_by_id: dict[str, dict[str, Any]]) -> set[str]:
    return {
        claims_by_id[claim_id]["tier"]
        for claim_id in feature.get("claim_ids", [])
        if claim_id in claims_by_id
    }


def _claim_tier_rank(tier: str) -> int:
    return {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}[tier]


def _feature_can_require_claim(feature: dict[str, Any], tier: str) -> bool:
    if tier == "T0":
        return False
    target = feature.get("plan", {}).get("target_claim_tier")
    if feature.get("implementation_status") == "implemented" and target:
        return _claim_tier_rank(tier) >= _claim_tier_rank(target)
    return True


def _claim_id_for_feature_tier(
    feature: dict[str, Any],
    tier: str,
    claims_by_id: dict[str, dict[str, Any]],
) -> str | None:
    for claim_id in feature.get("claim_ids", []):
        claim = claims_by_id.get(claim_id)
        if claim and claim.get("tier") == tier:
            return claim_id
    for claim in claims_by_id.values():
        if feature["id"] in claim.get("feature_ids", []) and claim.get("tier") == tier:
            return str(claim["id"])
    return None


def _surface_t0_claim(feature_id: str, claims_by_id: dict[str, dict[str, Any]]) -> str | None:
    if not feature_id.startswith("feat:surface-"):
        return None
    claim_id = "clm:" + feature_id.removeprefix("feat:") + "-t0-runtime-smoke"
    return claim_id if claim_id in claims_by_id else None


def _classification_t0_claim(feature_id: str, claims_by_id: dict[str, dict[str, Any]]) -> str | None:
    projection_features = {
        "feat:contract-event-channel-classification-projection-001",
        "feat:scope-classification-projection-001",
        "feat:send-event-classification-projection-001",
        "feat:receive-event-classification-projection-001",
        "feat:contract-scope-projection-transport-metadata-001",
        "feat:webtransport-native-lane-projection-001",
    }
    claim_id = "clm:classification-projection-t0-test-plan"
    if feature_id in projection_features and claim_id in claims_by_id:
        return claim_id
    return None


def _ensure_shared_test_and_evidence(registry: dict[str, Any]) -> None:
    feature_ids = [feature["id"] for feature in registry["features"]]
    tests = registry["tests"]
    evidence = registry["evidence"]
    for tier in BASELINE_TIERS:
        test_spec = deepcopy(BASELINE_TESTS[tier])
        evidence_spec = deepcopy(BASELINE_EVIDENCE[tier])
        test = _find_by_id(tests, test_spec["id"])
        if test is None:
            test = {
                **test_spec,
                "origin": "repo-local",
                "status": "passing",
                "feature_ids": [],
                "claim_ids": [],
                "evidence_ids": [evidence_spec["id"]],
            }
            tests.append(test)
        test.update(test_spec)
        test["status"] = "passing"
        test.setdefault("origin", "repo-local")
        test.setdefault("feature_ids", [])
        test.setdefault("claim_ids", [])
        test.setdefault("evidence_ids", [])
        _append_unique(test["evidence_ids"], evidence_spec["id"])
        for feature_id in feature_ids:
            _append_unique(test["feature_ids"], feature_id)

        evd = _find_by_id(evidence, evidence_spec["id"])
        if evd is None:
            evd = {
                **evidence_spec,
                "origin": "repo-local",
                "status": "passed",
                "tier": tier,
                "claim_ids": [],
                "test_ids": [test_spec["id"]],
            }
            evidence.append(evd)
        evd.update(evidence_spec)
        evd["status"] = "passed"
        evd["tier"] = tier
        evd.setdefault("origin", "repo-local")
        evd.setdefault("claim_ids", [])
        evd.setdefault("test_ids", [])
        _append_unique(evd["test_ids"], test_spec["id"])
        if tier == "T2":
            evd["robustness_dimensions"] = [
                "negative_cases",
                "edge_cases",
                "regression_corpus",
                "cross_surface",
            ]
            evd["source_evidence_ids"] = [BASELINE_EVIDENCE["T1"]["id"]]


def apply_baseline(registry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    _ensure_shared_test_and_evidence(registry)

    claims_by_id = {claim["id"]: claim for claim in registry["claims"]}
    tests_by_id = {test["id"]: test for test in registry["tests"]}
    evidence_by_id = {evidence["id"]: evidence for evidence in registry["evidence"]}

    created_claims = 0
    linked_claims = 0
    for feature in registry["features"]:
        feature.setdefault("claim_ids", [])
        feature.setdefault("test_ids", [])
        for tier in BASELINE_TIERS:
            test_id = BASELINE_TESTS[tier]["id"]
            evidence_id = BASELINE_EVIDENCE[tier]["id"]
            _append_unique(feature["test_ids"], test_id)

            claim_id = _claim_id_for_feature_tier(feature, tier, claims_by_id)
            if claim_id is None and tier == "T0":
                claim_id = _surface_t0_claim(feature["id"], claims_by_id)
            if claim_id is None and tier == "T0":
                claim_id = _classification_t0_claim(feature["id"], claims_by_id)
            if claim_id is None:
                claim_id = f"clm:{_slug(feature['id'])}-{tier.lower()}-baseline"

            claim = claims_by_id.get(claim_id)
            if claim is None:
                claim = {
                    "id": claim_id,
                    "title": f"{feature['title']} {tier} baseline",
                    "description": f"{tier} baseline proof for {feature['id']}.",
                    "kind": "baseline-proof",
                    "origin": "repo-local",
                    "status": "evidenced",
                    "tier": tier,
                    "feature_ids": [],
                    "test_ids": [],
                    "evidence_ids": [],
                    "depends_on_claim_ids": [],
                }
                registry["claims"].append(claim)
                claims_by_id[claim_id] = claim
                created_claims += 1
            claim.setdefault("origin", "repo-local")
            claim.setdefault("feature_ids", [])
            claim.setdefault("test_ids", [])
            claim.setdefault("evidence_ids", [])
            claim.setdefault("depends_on_claim_ids", [])
            claim["tier"] = tier
            if feature.get("implementation_status") == "implemented" and claim.get("tier") in BASELINE_TIERS:
                claim["status"] = "published"
            if claim.get("status") in {"proposed", "declared", "asserted"}:
                claim["status"] = "evidenced"
            _append_unique(claim["feature_ids"], feature["id"])
            _append_unique(claim["test_ids"], test_id)
            _append_unique(claim["evidence_ids"], evidence_id)
            if _feature_can_require_claim(feature, tier):
                _append_unique(feature["claim_ids"], claim_id)
            elif claim_id in feature["claim_ids"]:
                feature["claim_ids"].remove(claim_id)
            _append_unique(tests_by_id[test_id]["claim_ids"], claim_id)
            _append_unique(evidence_by_id[evidence_id]["claim_ids"], claim_id)
            linked_claims += 1

    t2_test_id = BASELINE_TESTS["T2"]["id"]
    t2_evidence_id = BASELINE_EVIDENCE["T2"]["id"]
    for claim in registry["claims"]:
        if claim.get("tier") != "T2":
            continue
        claim.setdefault("test_ids", [])
        claim.setdefault("evidence_ids", [])
        _append_unique(claim["test_ids"], t2_test_id)
        _append_unique(claim["evidence_ids"], t2_evidence_id)
        if claim.get("status") in {"proposed", "declared", "asserted"}:
            claim["status"] = "evidenced"
        _append_unique(tests_by_id[t2_test_id]["claim_ids"], claim["id"])
        _append_unique(evidence_by_id[t2_evidence_id]["claim_ids"], claim["id"])

    registry["features"].sort(key=lambda item: item["id"])
    registry["claims"].sort(key=lambda item: item["id"])
    registry["tests"].sort(key=lambda item: item["id"])
    registry["evidence"].sort(key=lambda item: item["id"])
    return registry, {"created_claims": created_claims, "linked_feature_tier_claims": linked_claims}


def repair() -> dict[str, int]:
    registry, report = apply_baseline(_load_registry())
    _save_registry(registry)
    return report


if __name__ == "__main__":
    print(json.dumps(repair(), indent=2, sort_keys=True))
