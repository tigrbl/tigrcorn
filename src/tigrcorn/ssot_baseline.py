from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable


BASELINE_TIERS = ("T0", "T1", "T2")
BASELINE_TEST_PATH = "tests/test_ssot_all_feature_t012_baseline.py"


@dataclass(frozen=True)
class FeatureBaseline:
    feature_id: str
    implementation_status: str
    claim_tiers: frozenset[str]
    claim_ids: tuple[str, ...]
    test_ids: tuple[str, ...]

    @property
    def missing_tiers(self) -> tuple[str, ...]:
        return tuple(tier for tier in BASELINE_TIERS if tier not in self.claim_tiers)


def load_registry(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / ".ssot" / "registry.json").read_text(encoding="utf-8"))


def _claims_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {claim["id"]: claim for claim in registry.get("claims", [])}


def _tests_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {test["id"]: test for test in registry.get("tests", [])}


def _evidence_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {evidence["id"]: evidence for evidence in registry.get("evidence", [])}


def iter_feature_baselines(registry: dict[str, Any]) -> Iterable[FeatureBaseline]:
    claims = _claims_by_id(registry)
    feature_claims: dict[str, set[str]] = {
        feature["id"]: set(feature.get("claim_ids", []))
        for feature in registry.get("features", [])
    }
    for claim in registry.get("claims", []):
        for feature_id in claim.get("feature_ids", []):
            feature_claims.setdefault(feature_id, set()).add(claim["id"])
    for feature in registry.get("features", []):
        claim_ids = tuple(sorted(feature_claims.get(feature["id"], set())))
        tiers = frozenset(
            claims[claim_id]["tier"]
            for claim_id in claim_ids
            if claim_id in claims and claims[claim_id].get("tier") in BASELINE_TIERS
        )
        yield FeatureBaseline(
            feature_id=feature["id"],
            implementation_status=feature["implementation_status"],
            claim_tiers=tiers,
            claim_ids=claim_ids,
            test_ids=tuple(feature.get("test_ids", [])),
        )


def missing_baseline_tiers(registry: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    return {
        baseline.feature_id: baseline.missing_tiers
        for baseline in iter_feature_baselines(registry)
        if baseline.missing_tiers
    }


def unlinked_t0_claim_ids(registry: dict[str, Any]) -> tuple[str, ...]:
    linked_claim_ids = {
        claim_id
        for feature in registry.get("features", [])
        for claim_id in feature.get("claim_ids", [])
    }
    linked_claim_ids.update(
        claim["id"]
        for claim in registry.get("claims", [])
        if claim.get("feature_ids")
    )
    return tuple(
        claim["id"]
        for claim in registry.get("claims", [])
        if claim.get("tier") == "T0" and claim["id"] not in linked_claim_ids
    )


def baseline_claims_have_concrete_proof(registry: dict[str, Any]) -> dict[str, str]:
    tests = _tests_by_id(registry)
    evidence = _evidence_by_id(registry)
    failures: dict[str, str] = {}
    for claim in registry.get("claims", []):
        if claim.get("tier") not in BASELINE_TIERS:
            continue
        claim_id = claim["id"]
        test_ids = claim.get("test_ids", [])
        evidence_ids = claim.get("evidence_ids", [])
        if not test_ids:
            failures[claim_id] = "missing tests"
            continue
        if not evidence_ids:
            failures[claim_id] = "missing evidence"
            continue
        missing_tests = [test_id for test_id in test_ids if test_id not in tests]
        if missing_tests:
            failures[claim_id] = f"unknown tests: {missing_tests}"
            continue
        missing_evidence = [evidence_id for evidence_id in evidence_ids if evidence_id not in evidence]
        if missing_evidence:
            failures[claim_id] = f"unknown evidence: {missing_evidence}"
            continue
        placeholder_paths = [
            tests[test_id]["path"]
            for test_id in test_ids
            if "test-placeholders" in tests[test_id].get("path", "")
        ]
        placeholder_paths.extend(
            evidence[evidence_id]["path"]
            for evidence_id in evidence_ids
            if "test-placeholders" in evidence[evidence_id].get("path", "")
        )
        if placeholder_paths:
            failures[claim_id] = f"placeholder proof paths: {placeholder_paths}"
            continue
        if not all(tests[test_id].get("status") == "passing" for test_id in test_ids):
            failures[claim_id] = "non-passing linked test"
            continue
        if not all(evidence[evidence_id].get("status") == "passed" for evidence_id in evidence_ids):
            failures[claim_id] = "non-passed linked evidence"
            continue
        if claim.get("tier") == "T2":
            t2_evidence = [evidence[evidence_id] for evidence_id in evidence_ids if evidence[evidence_id].get("tier") == "T2"]
            if not any(item.get("robustness_dimensions") for item in t2_evidence):
                failures[claim_id] = "missing T2 robustness dimensions"
                continue
            if not any(item.get("source_evidence_ids") for item in t2_evidence):
                failures[claim_id] = "missing T2 source evidence links"
    return failures


def feature_ids_partial_only_for_baseline(registry: dict[str, Any]) -> tuple[str, ...]:
    missing = missing_baseline_tiers(registry)
    return tuple(
        feature["id"]
        for feature in registry.get("features", [])
        if feature["implementation_status"] == "partial" and feature["id"] in missing
    )
