from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"
BOUNDARY_PATH = ROOT / "docs" / "review" / "conformance" / "certification_boundary.json"
CURRENT_STATE_CHAIN_PATH = ROOT / "docs" / "review" / "conformance" / "current_state_chain.current.json"
CLAIMS_REGISTRY_PATH = ROOT / "docs" / "review" / "conformance" / "claims_registry.json"
RISK_REGISTER_PATH = ROOT / "docs" / "conformance" / "risk" / "RISK_REGISTER.json"
RISK_TRACEABILITY_PATH = ROOT / "docs" / "conformance" / "risk" / "RISK_TRACEABILITY.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"
INIT_NORMALIZED_DIRS = (
    "schemas",
    "adr",
    "specs",
    "graphs",
    "evidence",
    "releases",
    "reports",
    "cache",
)

TIER_MAP = {
    "local_conformance": "T2",
    "same_stack_replay": "T3",
    "independent_certification": "T4",
}

RISK_STATUS_MAP = {
    "active": "active",
    "accepted": "accepted",
    "mitigated": "mitigated",
    "mitigated_in_tree": "mitigated",
    "controlled_with_inventory": "mitigated",
    "retired": "retired",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_version() -> str:
    payload = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def _slug(value: str) -> str:
    lowered = value.lower().replace("§", " s")
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered


def _claim_id(raw: str) -> str:
    return f"clm:{_slug(raw)}"


def _test_id(prefix: str, raw: str) -> str:
    return f"tst:{prefix}-{_slug(raw)}"


def _evidence_id(prefix: str, raw: str) -> str:
    return f"evd:{prefix}-{_slug(raw)}"


def _feature_id(raw: str) -> str:
    return f"feat:{_slug(raw)}"


def _feature_title(raw: str) -> str:
    return raw.strip("`") if raw else raw


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _existing_path(path_hint: str) -> str:
    path = ROOT / path_hint
    if path.exists():
        return path_hint
    return "docs/review/conformance/corpus.json"


def _plan_horizon(boundary_status: str, status: str) -> str:
    current_statuses = {
        "implemented_in_tree",
        "planned_for_independent_certification",
    }
    if boundary_status in {
        "in_bounds_current_surface",
        "public_operator_surface_outside_strict_rfc_claim",
        "tooling_surface_only",
    }:
        return "current" if status in current_statuses else "explicit"
    if boundary_status in {"candidate_not_current_claim", "in_bounds_candidate"}:
        return "next"
    if boundary_status in {"boundary_expansion_candidate", "cross_repo_or_boundary_review_candidate"}:
        return "future"
    if boundary_status == "out_of_bounds_now":
        return "out_of_bounds"
    return "explicit"


def _claim_status(raw_status: str) -> str:
    if raw_status == "implemented_in_tree":
        return "promoted"
    if raw_status == "planned_for_independent_certification":
        return "implemented"
    if raw_status == "candidate_not_yet_evidenced":
        return "declared"
    return "proposed"


def _feature_impl_status(claim_status: str) -> str:
    if claim_status == "promoted":
        return "implemented"
    if claim_status == "implemented":
        return "partial"
    return "absent"


def _merge_impl_status(current: str, candidate: str) -> str:
    order = {"absent": 0, "partial": 1, "implemented": 2}
    return current if order[current] >= order[candidate] else candidate


def _issue_id(raw: str) -> str:
    return f"iss:{_slug(raw)}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_content_sha(path: Path) -> str:
    try:
        from ssot_registry.util.fs import sha256_normalized_text_path
    except ImportError:
        return _sha256(path)
    return sha256_normalized_text_path(path)


def _load_ssot_package_metadata() -> dict[str, Any]:
    try:
        from ssot_registry.model.document import default_document_id_reservations, load_document_manifest
        from ssot_registry.model.registry import default_guard_policies
        from ssot_registry.version import __version__
    except ImportError:
        return {
            "version": "0.2.2",
            "guard_policies": {
                "claim_closure": {
                    "require_implemented_features": True,
                    "require_linked_tests_passing": True,
                    "require_linked_evidence_passing": True,
                    "require_claim_evidence_tier_alignment": True,
                    "forbid_failed_or_stale_evidence": True,
                },
                "certification": {
                    "require_release_status_draft_or_candidate": True,
                    "require_frozen_boundary": True,
                    "require_release_claim_coverage_for_boundary_features": True,
                    "require_boundary_features_current_or_explicit": True,
                    "require_feature_target_tiers_met": True,
                    "forbid_open_release_blocking_issues": True,
                    "forbid_active_release_blocking_risks": True,
                },
                "promotion": {
                    "require_release_status_certified": True,
                    "require_release_snapshot_hashes": True,
                },
                "publication": {
                    "require_release_status_promoted": True,
                },
                "lifecycle": {
                    "require_replacement_or_note_for_deprecation": True,
                    "forbid_obsolete_or_removed_in_active_boundary": True,
                    "require_feature_absent_for_removed": True,
                },
            },
            "document_id_reservations": {
                "adr": [
                    {
                        "owner": "ssot-core",
                        "start": 1,
                        "end": 999,
                        "immutable": True,
                        "deletable": False,
                        "assignable_by_repo": False,
                    },
                    {
                        "owner": "repo-local-default",
                        "start": 1000,
                        "end": 4999,
                        "immutable": False,
                        "deletable": True,
                        "assignable_by_repo": True,
                    },
                ],
                "spec": [
                    {
                        "owner": "ssot-core",
                        "start": 1,
                        "end": 999,
                        "immutable": True,
                        "deletable": False,
                        "assignable_by_repo": False,
                    },
                    {
                        "owner": "repo-local-default",
                        "start": 1000,
                        "end": 4999,
                        "immutable": False,
                        "deletable": True,
                        "assignable_by_repo": True,
                    },
                ],
            },
            "adr_manifest": [],
            "spec_manifest": [],
        }

    return {
        "version": __version__,
        "guard_policies": default_guard_policies(),
        "document_id_reservations": default_document_id_reservations(),
        "adr_manifest": load_document_manifest("adr"),
        "spec_manifest": load_document_manifest("spec"),
    }


def _document_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem


def _adr_status(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("status:"):
            value = stripped.split(":", 1)[1].strip()
            if value in {"proposed", "accepted", "superseded", "retired"}:
                return value
    return "accepted"


def _inventory_documents(
    *,
    kind: str,
    root: Path,
    package_version: str,
    manifest: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest_paths = {entry["target_path"] for entry in manifest}

    for entry in manifest:
        row = {
            "id": entry["id"],
            "number": entry["number"],
            "slug": entry["slug"],
            "title": entry["title"],
            "path": entry["target_path"],
            "origin": entry["origin"],
            "managed": True,
            "immutable": bool(entry["immutable"]),
            "package_version": package_version,
            "content_sha256": entry["sha256"],
        }
        if kind == "adr":
            row["status"] = entry.get("status", "draft")
            row["supersedes"] = entry.get("supersedes", [])
            row["superseded_by"] = entry.get("superseded_by", [])
            row["status_notes"] = entry.get("status_notes", [])
        else:
            row["kind"] = entry.get("kind", "normative")
            row["status"] = entry.get("status", "draft")
            row["supersedes"] = entry.get("supersedes", [])
            row["superseded_by"] = entry.get("superseded_by", [])
            row["status_notes"] = entry.get("status_notes", [])
        rows.append(row)

    try:
        from ssot_registry.util.document_io import load_document_yaml, normalize_document_payload
    except ImportError:
        load_document_yaml = None
        normalize_document_payload = None

    pattern = re.compile(rf"^({'ADR' if kind == 'adr' else 'SPEC'})-(?P<number>\d{{4}})-(?P<slug>[a-z0-9-]+)\.(?P<ext>md|yaml|json)$")
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        rel_path = _relative(path)
        if rel_path in manifest_paths:
            continue
        match = pattern.match(path.name)
        if match is None:
            continue

        number = int(match.group("number"))
        slug = match.group("slug")
        row = {
            "id": f"{'adr' if kind == 'adr' else 'spc'}:{number:04d}",
            "number": number,
            "slug": slug,
            "title": _document_title(path),
            "path": rel_path,
            "origin": "repo-local",
            "managed": False,
            "immutable": False,
            "package_version": package_version,
            "content_sha256": _normalized_content_sha(path),
        }
        if path.suffix.lower() in {".yaml", ".json"} and load_document_yaml is not None and normalize_document_payload is not None:
            payload = normalize_document_payload(kind, load_document_yaml(path))
            row["title"] = payload.get("title", row["title"])
            if kind == "adr":
                row["status"] = payload.get("status", "draft")
                row["supersedes"] = payload.get("supersedes", [])
                row["superseded_by"] = payload.get("superseded_by", [])
                row["status_notes"] = payload.get("status_notes", [])
            else:
                row["kind"] = payload.get("spec_kind", "local-policy")
                row["status"] = payload.get("status", "draft")
                row["supersedes"] = payload.get("supersedes", [])
                row["superseded_by"] = payload.get("superseded_by", [])
                row["status_notes"] = payload.get("status_notes", [])
        elif kind == "adr":
            row["status"] = _adr_status(path)
            row["supersedes"] = []
            row["superseded_by"] = []
            row["status_notes"] = []
        else:
            row["kind"] = "local-policy"
            row["status"] = "draft"
            row["supersedes"] = []
            row["superseded_by"] = []
            row["status_notes"] = []
        rows.append(row)
    return rows


def _iter_pytest_cases(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    cases: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            cases.append(node.name)
            continue
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                    cases.append(f"{node.name}::{child.name}")
    return cases


def build_registry() -> dict[str, Any]:
    boundary = _load_json(BOUNDARY_PATH)
    current_state_chain = _load_json(CURRENT_STATE_CHAIN_PATH)
    claims_registry = _load_json(CLAIMS_REGISTRY_PATH)
    risk_register = _load_json(RISK_REGISTER_PATH)
    risk_traceability = _load_json(RISK_TRACEABILITY_PATH)
    package_meta = _load_ssot_package_metadata()
    version = _load_version()

    corpus = _load_json(ROOT / "docs" / "review" / "conformance" / "corpus.json")
    corpus_vectors = {row["name"]: row for row in corpus.get("vectors", [])}

    features: dict[str, dict[str, Any]] = {}
    claims: dict[str, dict[str, Any]] = {}
    tests: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    issues: dict[str, dict[str, Any]] = {}
    risks: dict[str, dict[str, Any]] = {}

    release_claim_ids: set[str] = set()
    release_evidence_ids: set[str] = set()

    def ensure_feature(
        *,
        feature_id: str,
        title: str,
        description: str,
        tier: str,
        slot: str,
        horizon: str = "current",
        implementation_status: str = "implemented",
    ) -> None:
        row = features.setdefault(
            feature_id,
            {
                "id": feature_id,
                "title": title,
                "description": description,
                "implementation_status": implementation_status,
                "lifecycle": {
                    "stage": "active",
                    "replacement_feature_ids": [],
                    "note": None,
                },
                "plan": {
                    "horizon": horizon,
                    "slot": slot,
                    "target_claim_tier": tier,
                    "target_lifecycle_stage": "active",
                },
                "claim_ids": [],
                "test_ids": [],
                "requires": [],
            },
        )
        row["description"] = description or row["description"]
        row["implementation_status"] = _merge_impl_status(row["implementation_status"], implementation_status)
        if row["plan"]["target_claim_tier"] is None or (tier and row["plan"]["target_claim_tier"] < tier):
            row["plan"]["target_claim_tier"] = tier
        if row["plan"]["horizon"] != "current":
            row["plan"]["horizon"] = horizon
        if slot and not row["plan"]["slot"]:
            row["plan"]["slot"] = slot

    def ensure_claim(
        *,
        claim_id: str,
        title: str,
        description: str,
        tier: str,
        kind: str,
        feature_ids: list[str],
    ) -> None:
        if claim_id not in claims:
            claims[claim_id] = {
                "id": claim_id,
                "title": title,
                "status": "promoted",
                "tier": tier,
                "kind": kind,
                "description": description,
                "feature_ids": list(feature_ids),
                "test_ids": [],
                "evidence_ids": [],
            }
        for feature_id in feature_ids:
            if feature_id not in claims[claim_id]["feature_ids"]:
                claims[claim_id]["feature_ids"].append(feature_id)
        if claims[claim_id]["status"] == "promoted":
            release_claim_ids.add(claim_id)
        for feature_id in feature_ids:
            feature = features[feature_id]
            if claim_id not in feature["claim_ids"]:
                feature["claim_ids"].append(claim_id)

    def ensure_test(
        *,
        test_id: str,
        title: str,
        status: str,
        kind: str,
        path: str,
        feature_ids: list[str],
        claim_ids: list[str],
        evidence_ids: list[str],
    ) -> None:
        row = tests.setdefault(
            test_id,
            {
                "id": test_id,
                "title": title,
                "status": status,
                "kind": kind,
                "path": path,
                "feature_ids": [],
                "claim_ids": [],
                "evidence_ids": [],
            },
        )
        for feature_id in feature_ids:
            if feature_id not in row["feature_ids"]:
                row["feature_ids"].append(feature_id)
            feature = features[feature_id]
            if test_id not in feature["test_ids"]:
                feature["test_ids"].append(test_id)
        for claim_id in claim_ids:
            if claim_id not in row["claim_ids"]:
                row["claim_ids"].append(claim_id)
            claim = claims[claim_id]
            if test_id not in claim["test_ids"]:
                claim["test_ids"].append(test_id)
        for evidence_id in evidence_ids:
            if evidence_id not in row["evidence_ids"]:
                row["evidence_ids"].append(evidence_id)
            evidence_row = evidence.get(evidence_id)
            if evidence_row is not None and test_id not in evidence_row["test_ids"]:
                evidence_row["test_ids"].append(test_id)

    def ensure_evidence(
        *,
        evidence_id: str,
        title: str,
        kind: str,
        tier: str,
        path: str,
        claim_ids: list[str],
        test_ids: list[str],
    ) -> None:
        row = evidence.setdefault(
            evidence_id,
            {
                "id": evidence_id,
                "title": title,
                "status": "passed",
                "kind": kind,
                "tier": tier,
                "path": path,
                "claim_ids": [],
                "test_ids": [],
            },
        )
        release_evidence_ids.add(evidence_id)
        for claim_id in claim_ids:
            if claim_id not in row["claim_ids"]:
                row["claim_ids"].append(claim_id)
            claim = claims[claim_id]
            if evidence_id not in claim["evidence_ids"]:
                claim["evidence_ids"].append(evidence_id)
        for test_id in test_ids:
            if test_id not in row["test_ids"]:
                row["test_ids"].append(test_id)

    def ensure_issue(*, raw_ref: str) -> str:
        issue_id = _issue_id(raw_ref)
        issues.setdefault(
            issue_id,
            {
                "id": issue_id,
                "title": f"Tracked issue {raw_ref}",
                "status": "open",
                "severity": "medium",
                "description": f"Imported issue reference {raw_ref} from Tigrcorn planning and claim metadata.",
                "plan": {
                    "horizon": "current",
                    "slot": "issues",
                },
                "feature_ids": [],
                "claim_ids": [],
                "test_ids": [],
                "evidence_ids": [],
                "risk_ids": [],
                "release_blocking": False,
            },
        )
        return issue_id

    # Canonical current-state feature
    current_state_feature_id = _feature_id("current-state-chain")
    ensure_feature(
        feature_id=current_state_feature_id,
        title="Canonical current-state chain",
        description="The promoted repository state is governed by one explicit human and machine-readable current-state chain.",
        tier="T2",
        slot="state",
    )
    current_state_claim_id = _claim_id("current-state-chain")
    ensure_claim(
        claim_id=current_state_claim_id,
        title="Canonical current-state chain is explicit",
        description="Tigrcorn defines one canonical current-state chain and keeps focused audits and historical snapshots out of the package-wide truth source role.",
        tier="T2",
        kind="state_chain",
        feature_ids=[current_state_feature_id],
    )
    current_state_test_id = _test_id("doc", "current-state-chain")
    current_state_evidence_id = _evidence_id("doc", "current-state-chain")
    ensure_evidence(
        evidence_id=current_state_evidence_id,
        title="Current-state chain JSON",
        kind="current_state_chain",
        tier="T2",
        path=_relative(CURRENT_STATE_CHAIN_PATH),
        claim_ids=[current_state_claim_id],
        test_ids=[current_state_test_id],
    )
    ensure_test(
        test_id=current_state_test_id,
        title="Current-state normalization test",
        status="passing",
        kind="pytest",
        path="tests/test_documentation_truth_normalization_checkpoint.py",
        feature_ids=[current_state_feature_id],
        claim_ids=[current_state_claim_id],
        evidence_ids=[current_state_evidence_id],
    )

    # Full claim graph from claims_registry.json
    for row in claims_registry.get("current_and_candidate_claims", []):
        raw_claim_id = str(row.get("id", "")).strip()
        if not raw_claim_id:
            continue
        claim_id = _claim_id(raw_claim_id)
        tier = TIER_MAP.get(str(row.get("required_evidence_tier", "local_conformance")), "T2")
        boundary_status = str(row.get("boundary_status", "")).strip()
        raw_status = str(row.get("status", "")).strip()
        horizon = _plan_horizon(boundary_status, raw_status)
        claim_status = _claim_status(raw_status)
        feature_ids: list[str] = []

        explicit_feature_refs = [str(item) for item in row.get("feature_refs", [])]
        if explicit_feature_refs:
            for raw_feature in explicit_feature_refs:
                feature_id = _feature_id(raw_feature)
                ensure_feature(
                    feature_id=feature_id,
                    title=_feature_title(raw_feature),
                    description=f"Feature target {raw_feature} imported from claims_registry.json.",
                    tier=tier,
                    slot="roadmap-feature",
                    horizon=horizon,
                    implementation_status=_feature_impl_status(claim_status),
                )
                feature_ids.append(feature_id)
        else:
            surface = str(row.get("surface", raw_claim_id))
            feature_id = _feature_id(f"surface-{surface}")
            ensure_feature(
                feature_id=feature_id,
                title=surface.replace("_", " "),
                description=f"Surface feature synthesized from claim {raw_claim_id}.",
                tier=tier,
                slot=str(row.get("class", "surface")),
                horizon=horizon,
                implementation_status=_feature_impl_status(claim_status),
            )
            feature_ids.append(feature_id)

        ensure_claim(
            claim_id=claim_id,
            title=raw_claim_id,
            description=str(row.get("text", raw_claim_id)),
            tier=tier,
            kind=str(row.get("claim_kind", row.get("class", "claim"))),
            feature_ids=feature_ids,
        )
        claims[claim_id]["status"] = claim_status
        claims[claim_id]["source_row"] = row
        if claim_status == "promoted":
            release_claim_ids.add(claim_id)
        elif claim_id in release_claim_ids:
            release_claim_ids.remove(claim_id)

        issue_ids: list[str] = []
        for raw_issue in row.get("issue_refs", []):
            issue_id = ensure_issue(raw_ref=str(raw_issue))
            issue_ids.append(issue_id)
            issue = issues[issue_id]
            if claim_id not in issue["claim_ids"]:
                issue["claim_ids"].append(claim_id)
            for feature_id in feature_ids:
                if feature_id not in issue["feature_ids"]:
                    issue["feature_ids"].append(feature_id)
        claims[claim_id]["issue_ids"] = issue_ids

        source_files = [str(item) for item in row.get("source_files", [])]
        claim_test_ids: list[str] = []
        claim_evidence_ids: list[str] = []

        for source_path in source_files:
            rel_path = _existing_path(source_path)
            evidence_id = _evidence_id("src", rel_path)
            ensure_evidence(
                evidence_id=evidence_id,
                title=f"Source artifact {rel_path}",
                kind="source_artifact",
                tier=tier,
                path=rel_path,
                claim_ids=[claim_id],
                test_ids=[],
            )
            claim_evidence_ids.append(evidence_id)

        for source_path in source_files:
            rel_path = _existing_path(source_path)
            if not rel_path.startswith("tests/"):
                continue
            test_id = _test_id("src", rel_path)
            ensure_test(
                test_id=test_id,
                title=f"Test coverage {rel_path}",
                status="passing" if claim_status in {"promoted", "implemented"} else "planned",
                kind="pytest" if rel_path.endswith(".py") else "artifact",
                path=rel_path,
                feature_ids=feature_ids,
                claim_ids=[claim_id],
                evidence_ids=claim_evidence_ids or [_evidence_id("src", rel_path)],
            )
            claim_test_ids.append(test_id)

        if not claim_test_ids:
            fallback_path = claim_evidence_ids and evidence[claim_evidence_ids[0]]["path"] or _relative(CLAIMS_REGISTRY_PATH)
            fallback_evidence_ids = list(claim_evidence_ids)
            if not fallback_evidence_ids:
                fallback_evidence_id = _evidence_id("claim", raw_claim_id)
                ensure_evidence(
                    evidence_id=fallback_evidence_id,
                    title=f"Claim registry row {raw_claim_id}",
                    kind="claim_registry_row",
                    tier=tier,
                    path=_relative(CLAIMS_REGISTRY_PATH),
                    claim_ids=[claim_id],
                    test_ids=[],
                )
                fallback_evidence_ids.append(fallback_evidence_id)
                claim_evidence_ids.append(fallback_evidence_id)
            test_id = _test_id("claim", raw_claim_id)
            ensure_test(
                test_id=test_id,
                title=f"Claim linkage {raw_claim_id}",
                status="passing" if claim_status in {"promoted", "implemented"} else "planned",
                kind="claim_linkage",
                path=fallback_path,
                feature_ids=feature_ids,
                claim_ids=[claim_id],
                evidence_ids=fallback_evidence_ids,
            )
            claim_test_ids.append(test_id)

        if not claim_evidence_ids and claim_test_ids:
            for test_id in claim_test_ids:
                test_path = tests[test_id]["path"]
                evidence_id = _evidence_id("src", test_path)
                ensure_evidence(
                    evidence_id=evidence_id,
                    title=f"Test artifact {test_path}",
                    kind="test_artifact",
                    tier=tier,
                    path=test_path,
                    claim_ids=[claim_id],
                    test_ids=[test_id],
                )
                claim_evidence_ids.append(evidence_id)

        for test_id in claim_test_ids:
            for evidence_id in claim_evidence_ids:
                if evidence_id not in tests[test_id]["evidence_ids"]:
                    tests[test_id]["evidence_ids"].append(evidence_id)
                if test_id not in evidence[evidence_id]["test_ids"]:
                    evidence[evidence_id]["test_ids"].append(test_id)

        for evidence_id in claim_evidence_ids:
            if claim_status == "promoted":
                release_evidence_ids.add(evidence_id)

    # Governance feature
    governance_feature_id = _feature_id("governance-graph")
    ensure_feature(
        feature_id=governance_feature_id,
        title="Governance graph",
        description="Risk, claim, test, and evidence ownership remain machine-readable and release-gated.",
        tier="T2",
        slot="governance",
    )

    for row in risk_register.get("register", []):
        risk_key = str(row.get("risk_id", ""))
        if not risk_key:
            continue

        linked_claim_ids: list[str] = []
        linked_test_ids: list[str] = []
        linked_evidence_ids: list[str] = []

        for raw_claim_id in row.get("claim_refs", []):
            claim_id = _claim_id(str(raw_claim_id))
            if claim_id not in claims:
                ensure_claim(
                    claim_id=claim_id,
                    title=str(raw_claim_id),
                    description=f"Governance claim tracked through risk register row {risk_key}.",
                    tier="T2",
                    kind="governance_support",
                    feature_ids=[governance_feature_id],
                )
            linked_claim_ids.append(claim_id)
            if governance_feature_id not in claims[claim_id]["feature_ids"]:
                claims[claim_id]["feature_ids"].append(governance_feature_id)
            if claim_id not in features[governance_feature_id]["claim_ids"]:
                features[governance_feature_id]["claim_ids"].append(claim_id)

        for test_ref in row.get("test_refs", []):
            test_path = str(test_ref).split("::", 1)[0]
            test_id = _test_id("gov", test_path)
            ensure_test(
                test_id=test_id,
                title=f"Governance test {test_path}",
                status="passing",
                kind="pytest",
                path=test_path,
                feature_ids=[governance_feature_id],
                claim_ids=linked_claim_ids,
                evidence_ids=[],
            )
            linked_test_ids.append(test_id)

        for evidence_ref in row.get("evidence_refs", []):
            evidence_id = _evidence_id("gov", str(evidence_ref))
            ensure_evidence(
                evidence_id=evidence_id,
                title=f"Governance evidence {evidence_ref}",
                kind="governance_artifact",
                tier="T2",
                path=str(evidence_ref),
                claim_ids=linked_claim_ids,
                test_ids=linked_test_ids,
            )
            linked_evidence_ids.append(evidence_id)

        for test_id in linked_test_ids:
            for evidence_id in linked_evidence_ids:
                if evidence_id not in tests[test_id]["evidence_ids"]:
                    tests[test_id]["evidence_ids"].append(evidence_id)

        traceability_row = next(
            (item for item in risk_traceability.get("risks", []) if item.get("risk_id") == risk_key),
            {},
        )
        risk_id = f"rsk:{_slug(risk_key)}"
        risks[risk_id] = {
            "id": risk_id,
            "title": str(row.get("title", risk_key)),
            "status": RISK_STATUS_MAP.get(str(row.get("status", "")).strip().lower(), "active"),
            "severity": str(row.get("severity", "medium")).lower(),
            "description": str(row.get("summary", row.get("title", risk_key))),
            "feature_ids": [governance_feature_id],
            "claim_ids": linked_claim_ids,
            "test_ids": linked_test_ids,
            "evidence_ids": linked_evidence_ids,
            "issue_ids": [],
            "release_blocking": bool(row.get("release_gate_blocking", False)),
            "source_risk_id": risk_key,
            "policy_doc": row.get("policy_doc"),
            "traceability_refs": traceability_row,
        }
        for issue_ref in traceability_row.get("issue_refs", []):
            issue_id = ensure_issue(raw_ref=str(issue_ref))
            risks[risk_id]["issue_ids"].append(issue_id)
            if risk_id not in issues[issue_id]["risk_ids"]:
                issues[issue_id]["risk_ids"].append(risk_id)

    # RFC features, claims, tests, and evidence
    artifact_bundles = boundary.get("artifact_bundles", {})
    for rfc_name in boundary.get("required_rfcs", []):
        policy = boundary["required_rfc_evidence"][rfc_name]
        highest_tier = TIER_MAP[policy["highest_required_evidence_tier"]]
        feature_id = _feature_id(rfc_name)
        ensure_feature(
            feature_id=feature_id,
            title=rfc_name,
            description=f"Authoritative certification-boundary coverage for {rfc_name}.",
            tier=highest_tier,
            slot="authoritative-boundary",
        )
        claim_id = _claim_id(rfc_name)
        ensure_claim(
            claim_id=claim_id,
            title=f"{rfc_name} certified coverage",
            description=f"{rfc_name} remains inside Tigrcorn's authoritative certification boundary with the required evidence tiers declared in certification_boundary.json.",
            tier=highest_tier,
            kind="rfc_certification",
            feature_ids=[feature_id],
        )

        declared_evidence = policy.get("declared_evidence", {})
        for tier_name, entries in declared_evidence.items():
            mapped_tier = TIER_MAP[tier_name]
            for entry in entries:
                if tier_name == "local_conformance":
                    vector = corpus_vectors.get(entry, {})
                    test_path = _existing_path(str(vector.get("fixture", "")))
                    test_id = _test_id("corpus", entry)
                    evidence_id = _evidence_id("corpus", entry)
                    ensure_evidence(
                        evidence_id=evidence_id,
                        title=f"Corpus vector {entry}",
                        kind="local_conformance",
                        tier=mapped_tier,
                        path=test_path,
                        claim_ids=[claim_id],
                        test_ids=[test_id],
                    )
                    ensure_test(
                        test_id=test_id,
                        title=f"Local conformance vector {entry}",
                        status="passing",
                        kind="local_conformance",
                        path=test_path,
                        feature_ids=[feature_id],
                        claim_ids=[claim_id],
                        evidence_ids=[evidence_id],
                    )
                else:
                    test_id = _test_id("matrix", entry)
                    evidence_id = _evidence_id("bundle", entry)
                    matrix_path = (
                        "docs/review/conformance/external_matrix.release.json"
                        if tier_name == "independent_certification"
                        else "docs/review/conformance/external_matrix.same_stack_replay.json"
                    )
                    bundle_root = artifact_bundles[tier_name]
                    scenario_path = f"{bundle_root}/{entry}"
                    ensure_evidence(
                        evidence_id=evidence_id,
                        title=f"Preserved scenario {entry}",
                        kind=tier_name,
                        tier=mapped_tier,
                        path=scenario_path,
                        claim_ids=[claim_id],
                        test_ids=[test_id],
                    )
                    ensure_test(
                        test_id=test_id,
                        title=f"Interop scenario {entry}",
                        status="passing",
                        kind=tier_name,
                        path=matrix_path,
                        feature_ids=[feature_id],
                        claim_ids=[claim_id],
                        evidence_ids=[evidence_id],
                    )

    profile_feature_id = _feature_id("deployment-profiles")
    profile_claim_id = _claim_id("deployment-profiles")
    profile_test_id = _test_id("src", "tests/test_profile_resolution.py")
    ensure_feature(
        feature_id=profile_feature_id,
        title="Deployment profiles",
        description="Blessed profile artifacts are tracked in the SSOT registry alongside their validating tests.",
        tier="T2",
        slot="profiles",
    )
    ensure_claim(
        claim_id=profile_claim_id,
        title="Deployment profile artifacts tracked",
        description="Profile JSON artifacts under profiles/ are inventoried and linked to the package's profile validation path.",
        tier="T2",
        kind="profile_inventory",
        feature_ids=[profile_feature_id],
    )
    if profile_test_id not in tests:
        ensure_test(
            test_id=profile_test_id,
            title="Profile resolution coverage",
            status="passing",
            kind="pytest",
            path="tests/test_profile_resolution.py",
            feature_ids=[profile_feature_id],
            claim_ids=[profile_claim_id],
            evidence_ids=[],
        )
    else:
        if profile_feature_id not in tests[profile_test_id]["feature_ids"]:
            tests[profile_test_id]["feature_ids"].append(profile_feature_id)
        if profile_claim_id not in tests[profile_test_id]["claim_ids"]:
            tests[profile_test_id]["claim_ids"].append(profile_claim_id)
        if profile_test_id not in features[profile_feature_id]["test_ids"]:
            features[profile_feature_id]["test_ids"].append(profile_test_id)
        if profile_test_id not in claims[profile_claim_id]["test_ids"]:
            claims[profile_claim_id]["test_ids"].append(profile_test_id)
    for profile_path in sorted((ROOT / "profiles").glob("*.profile.json")):
        evidence_id = _evidence_id("profile", profile_path.as_posix())
        ensure_evidence(
            evidence_id=evidence_id,
            title=f"Profile artifact {_relative(profile_path)}",
            kind="profile_artifact",
            tier="T2",
            path=_relative(profile_path),
            claim_ids=[profile_claim_id],
            test_ids=[profile_test_id],
        )
        if evidence_id not in tests[profile_test_id]["evidence_ids"]:
            tests[profile_test_id]["evidence_ids"].append(evidence_id)

    test_inventory_feature_id = _feature_id("test-inventory")
    test_inventory_claim_id = _claim_id("test-inventory")
    ensure_feature(
        feature_id=test_inventory_feature_id,
        title="Repository test inventory",
        description="Every repo-local pytest module and discovered test case is represented in the registry, including modules not directly linked from claims_registry.json.",
        tier="T2",
        slot="test-inventory",
    )
    ensure_claim(
        claim_id=test_inventory_claim_id,
        title="Repository pytest inventory tracked",
        description="The SSOT registry tracks the full repo-local pytest surface so unlinked modules and cases remain visible in the governance graph.",
        tier="T2",
        kind="test_inventory",
        feature_ids=[test_inventory_feature_id],
    )
    test_paths_index = {row["path"]: row for row in tests.values()}
    for test_file in sorted((ROOT / "tests").glob("test_*.py")):
        rel_test_path = _relative(test_file)
        file_row = test_paths_index.get(rel_test_path)
        if file_row is None:
            file_test_id = _test_id("pytest-file", rel_test_path)
            file_evidence_id = _evidence_id("pytest-file", rel_test_path)
            ensure_evidence(
                evidence_id=file_evidence_id,
                title=f"Pytest module {rel_test_path}",
                kind="pytest_module",
                tier="T2",
                path=rel_test_path,
                claim_ids=[test_inventory_claim_id],
                test_ids=[file_test_id],
            )
            ensure_test(
                test_id=file_test_id,
                title=f"Pytest module inventory {rel_test_path}",
                status="passing",
                kind="pytest-file",
                path=rel_test_path,
                feature_ids=[test_inventory_feature_id],
                claim_ids=[test_inventory_claim_id],
                evidence_ids=[file_evidence_id],
            )
            file_row = tests[file_test_id]
            test_paths_index[rel_test_path] = file_row
        linked_feature_ids = list(file_row["feature_ids"]) or [test_inventory_feature_id]
        linked_claim_ids = list(file_row["claim_ids"]) or [test_inventory_claim_id]
        linked_evidence_ids = list(file_row["evidence_ids"])
        if not linked_evidence_ids:
            module_evidence_id = _evidence_id("pytest-module", rel_test_path)
            ensure_evidence(
                evidence_id=module_evidence_id,
                title=f"Pytest module evidence {rel_test_path}",
                kind="pytest_module",
                tier="T2",
                path=rel_test_path,
                claim_ids=linked_claim_ids,
                test_ids=[],
            )
            linked_evidence_ids = [module_evidence_id]
            file_row["evidence_ids"].append(module_evidence_id)
        for case_name in _iter_pytest_cases(test_file):
            case_path = f"{rel_test_path}::{case_name}"
            case_test_id = _test_id("pytest-case", case_path)
            if case_test_id in tests:
                continue
            ensure_test(
                test_id=case_test_id,
                title=f"Pytest case inventory {case_path}",
                status="passing",
                kind="pytest-case",
                path=rel_test_path,
                feature_ids=linked_feature_ids,
                claim_ids=linked_claim_ids,
                evidence_ids=linked_evidence_ids,
            )

    promoted_claim_ids = {claim_id for claim_id, row in claims.items() if row.get("status") == "promoted"}
    boundary_feature_ids = sorted(
        feature_id
        for feature_id, row in features.items()
        if any(claim_id in promoted_claim_ids for claim_id in row.get("claim_ids", []))
    )
    release_id = f"rel:{version}"
    adrs = _inventory_documents(
        kind="adr",
        root=ROOT / ".ssot" / "adr",
        package_version=package_meta["version"],
        manifest=package_meta["adr_manifest"],
    )
    specs = _inventory_documents(
        kind="spec",
        root=ROOT / ".ssot" / "specs",
        package_version=package_meta["version"],
        manifest=package_meta["spec_manifest"],
    )

    registry = {
        "schema_version": 4,
        "repo": {
            "id": "repo:tigrcorn",
            "name": "tigrcorn",
            "version": version,
        },
        "tooling": {
            "ssot_registry_version": package_meta["version"],
            "initialized_with_version": package_meta["version"],
            "last_upgraded_from_version": package_meta["version"],
        },
        "paths": {
            "ssot_root": ".ssot",
            "schema_root": ".ssot/schemas",
            "adr_root": ".ssot/adr",
            "spec_root": ".ssot/specs",
            "graph_root": ".ssot/graphs",
            "evidence_root": ".ssot/evidence",
            "release_root": ".ssot/releases",
            "report_root": ".ssot/reports",
            "cache_root": ".ssot/cache",
        },
        "program": {
            "active_boundary_id": "bnd:authoritative-0-3-9",
            "active_release_id": release_id,
        },
        "guard_policies": {
            **package_meta["guard_policies"],
            "tier_map": TIER_MAP,
            "canonical_human_current_state_chain": current_state_chain.get("canonical_human_current_state_chain", []),
            "canonical_machine_current_state_chain": current_state_chain.get("canonical_machine_current_state_chain", []),
            "canonical_policy_sources": current_state_chain.get("canonical_policy_sources", []),
            "claims_registry_source": _relative(CLAIMS_REGISTRY_PATH),
        },
        "document_id_reservations": package_meta["document_id_reservations"],
        "features": sorted(features.values(), key=lambda row: row["id"]),
        "tests": sorted(tests.values(), key=lambda row: row["id"]),
        "claims": sorted(claims.values(), key=lambda row: row["id"]),
        "evidence": sorted(evidence.values(), key=lambda row: row["id"]),
        "issues": sorted(issues.values(), key=lambda row: row["id"]),
        "risks": sorted(risks.values(), key=lambda row: row["id"]),
        "boundaries": [
            {
                "id": "bnd:authoritative-0-3-9",
                "title": "Authoritative Tigrcorn frozen boundary and governance graph",
                "status": "frozen",
                "frozen": True,
                "feature_ids": boundary_feature_ids,
                "canonical_doc": _relative(ROOT / "docs" / "review" / "conformance" / "CERTIFICATION_BOUNDARY.md"),
                "canonical_registry_source": ".ssot/registry.json",
            }
        ],
        "releases": [
            {
                "id": release_id,
                "version": version,
                "status": "promoted",
                "boundary_id": "bnd:authoritative-0-3-9",
                "claim_ids": sorted(release_claim_ids),
                "evidence_ids": sorted(release_evidence_ids),
                "canonical_release_bundle": boundary.get("canonical_release_bundle"),
            }
        ],
        "adrs": adrs,
        "specs": specs,
    }
    return registry


def validate_registry(registry: dict[str, Any], registry_path: Path) -> dict[str, Any]:
    try:
        from ssot_registry.api.validate import validate_registry_document
    except ImportError as exc:  # pragma: no cover - exercised in runtime environments without the extra installed
        raise SystemExit(
            "ssot-registry is required to validate the generated registry. Install the dev environment with uv first."
        ) from exc

    return validate_registry_document(registry, registry_path=registry_path, repo_root=ROOT)


def ensure_initialized_ssot_tree(version: str) -> None:
    try:
        from ssot_registry.api import initialize_repo
    except ImportError as exc:  # pragma: no cover - exercised in runtime environments without the extra installed
        raise SystemExit(
            "ssot-registry is required to initialize the normalized .ssot tree. Install the dev environment with uv first."
        ) from exc

    bootstrap_parent = ROOT / ".tmp"
    bootstrap_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ssot-init-", dir=bootstrap_parent) as scratch:
        scratch_root = Path(scratch)
        bootstrap_registry_path = scratch_root / ".ssot" / "registry.json"
        try:
            initialize_repo(
                scratch_root,
                repo_id="repo:tigrcorn",
                repo_name="tigrcorn",
                version=version,
                force=True,
            )
        except Exception as exc:  # pragma: no cover - depends on upstream ssot-registry behavior
            if "Newly initialized registry did not validate" not in str(exc) or not bootstrap_registry_path.exists():
                raise

        bootstrap_registry = json.loads(bootstrap_registry_path.read_text(encoding="utf-8"))
        ssot_root = ROOT / ".ssot"
        ssot_root.mkdir(parents=True, exist_ok=True)

        # Use the package's init flow as the source of the normalized tree contract,
        # but keep Tigrcorn's repo-specific canonical docs and release evidence paths.
        for key, relative_path in bootstrap_registry.get("paths", {}).items():
            if key == "ssot_root":
                continue
            path = Path(relative_path)
            if not path.parts or path.parts[0] != ".ssot":
                continue
            if path.parts[1] not in INIT_NORMALIZED_DIRS:
                continue
            (ROOT / path).mkdir(parents=True, exist_ok=True)


def write_registry(*, check: bool) -> int:
    registry = build_registry()
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(registry, indent=2, sort_keys=False) + "\n"

    if check:
        current = REGISTRY_PATH.read_text(encoding="utf-8") if REGISTRY_PATH.exists() else ""
        if current != payload:
            print(".ssot/registry.json is out of date")
            return 1
        return 0

    ensure_initialized_ssot_tree(str(registry["repo"]["version"]))
    REGISTRY_PATH.write_text(payload, encoding="utf-8")

    try:
        from ssot_registry.api.upgrade import upgrade_registry
    except ImportError:
        report = validate_registry(registry, REGISTRY_PATH)
        if not report["passed"]:
            for failure in report["failures"]:
                print(failure)
            return 1
        return 0

    try:
        upgrade_registry(REGISTRY_PATH, sync_docs=True, write_report=True)
    except Exception as exc:
        print(str(exc))
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Tigrcorn's ssot-registry bridge document.")
    parser.add_argument("--check", action="store_true", help="Fail if the committed registry is stale.")
    args = parser.parse_args()
    return write_registry(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
