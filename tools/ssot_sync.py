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
MAX_NORMALIZED_ID_LENGTH = 128

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


def _bounded_id(prefix: str, slug: str) -> str:
    candidate = f"{prefix}:{slug}"
    if len(candidate) <= MAX_NORMALIZED_ID_LENGTH:
        return candidate
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:10]
    keep = MAX_NORMALIZED_ID_LENGTH - len(prefix) - len(digest) - 2
    return f"{prefix}:{slug[:keep].rstrip('-')}-{digest}"


def _claim_id(raw: str) -> str:
    return _bounded_id("clm", _slug(raw))


def _test_id(prefix: str, raw: str) -> str:
    return _bounded_id("tst", f"{prefix}-{_slug(raw)}")


def _evidence_id(prefix: str, raw: str) -> str:
    return _bounded_id("evd", f"{prefix}-{_slug(raw)}")


def _feature_id(raw: str) -> str:
    return _bounded_id("feat", _slug(raw))


def _profile_id(raw: str) -> str:
    return _bounded_id("prf", _slug(raw))


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
    return _bounded_id("iss", _slug(raw))


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
        from ssot_registry.model.enums import SCHEMA_VERSION
        from ssot_registry.model.registry import default_guard_policies
        from ssot_registry.version import __version__
    except ImportError:
        return {
            "schema_version": "0.1.0",
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
        "schema_version": SCHEMA_VERSION,
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
        if not (ROOT / entry["target_path"]).exists():
            continue
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
            row["adr_ids"] = entry.get("adr_ids", [])
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
                row["adr_ids"] = payload.get("adr_ids", [])
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
            row["adr_ids"] = []
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
    profiles: dict[str, dict[str, Any]] = {}

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
                "spec_ids": [],
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

    def link_feature_specs(feature_ids: list[str], spec_ids: list[str]) -> None:
        for feature_id in feature_ids:
            feature = features[feature_id]
            for spec_id in spec_ids:
                if spec_id not in feature["spec_ids"]:
                    feature["spec_ids"].append(spec_id)

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

    def ensure_profile(
        *,
        profile_id: str,
        title: str,
        description: str,
        kind: str,
        feature_ids: list[str],
        profile_ids: list[str],
        claim_tier: str,
    ) -> None:
        profiles[profile_id] = {
            "id": profile_id,
            "title": title,
            "description": description,
            "status": "active",
            "kind": kind,
            "feature_ids": sorted(dict.fromkeys(feature_ids)),
            "profile_ids": sorted(dict.fromkeys(profile_ids)),
            "claim_tier": claim_tier,
            "evaluation": {
                "mode": "all_features_must_pass",
                "allow_feature_override_tier": True,
            },
        }

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

    # SSOT authority and tigr-asgi-contract scope decisions
    ssot_authority_feature_id = _feature_id("ssot-authoritative-product-boundary")
    ensure_feature(
        feature_id=ssot_authority_feature_id,
        title="SSOT authoritative product boundary",
        description=(
            ".ssot/registry.json is the authoritative product boundary; docs are projections "
            "and do not win conflicts."
        ),
        tier="T2",
        slot="product-boundary",
        horizon="current",
        implementation_status="implemented",
    )
    ssot_authority_claim_id = _claim_id("ssot-authoritative-product-boundary")
    ssot_authority_test_id = _test_id("pytest", "tests/test_ssot_registry.py::test_ssot_declares_webtransport_in_scope_and_rest_jsonrpc_out")
    ssot_authority_evidence_id = _evidence_id("pytest", "tests/test_ssot_registry.py")
    ensure_claim(
        claim_id=ssot_authority_claim_id,
        title="SSOT authoritative product boundary",
        description=".ssot/registry.json is authoritative for product boundary decisions; docs are non-authoritative projections.",
        tier="T2",
        kind="product_boundary",
        feature_ids=[ssot_authority_feature_id],
    )
    ensure_evidence(
        evidence_id=ssot_authority_evidence_id,
        title="SSOT registry product-boundary test evidence",
        kind="pytest",
        tier="T2",
        path="tests/test_ssot_registry.py",
        claim_ids=[ssot_authority_claim_id],
        test_ids=[ssot_authority_test_id],
    )
    ensure_test(
        test_id=ssot_authority_test_id,
        title="SSOT WebTransport and exclusion boundary coverage",
        status="passing",
        kind="pytest",
        path="tests/test_ssot_registry.py",
        feature_ids=[ssot_authority_feature_id],
        claim_ids=[ssot_authority_claim_id],
        evidence_ids=[ssot_authority_evidence_id],
    )

    package_boundary_feature_ids = [
        _feature_id("package-workspace-boundaries"),
        _feature_id("package-boundary-dependency-dag"),
        _feature_id("tigrcorn-core-extraction-shims"),
    ]
    package_boundary_rows = [
        (
            package_boundary_feature_ids[0],
            "Package workspace boundaries",
            "Declare the publishable monorepo package set while preserving tigrcorn as the umbrella public install.",
        ),
        (
            package_boundary_feature_ids[1],
            "Package boundary dependency DAG",
            "Enforce one-way dependency direction from core toward runtime, compatibility, certification, and the umbrella facade.",
        ),
        (
            package_boundary_feature_ids[2],
            "tigrcorn-core extraction shims",
            "Extract dependency-light constants, errors, and type aliases to tigrcorn-core while preserving legacy tigrcorn.* imports.",
        ),
    ]
    for feature_id, title, description in package_boundary_rows:
        ensure_feature(
            feature_id=feature_id,
            title=title,
            description=description,
            tier="T2",
            slot="package-boundaries",
            horizon="current",
            implementation_status="implemented",
        )
    link_feature_specs(package_boundary_feature_ids, ["spc:2038"])
    for feature_id in package_boundary_feature_ids[1:]:
        if package_boundary_feature_ids[0] not in features[feature_id]["requires"]:
            features[feature_id]["requires"].append(package_boundary_feature_ids[0])
    package_boundary_claim_id = _claim_id("package-workspace-boundaries-implemented")
    package_boundary_test_id = _test_id("pytest", "tests/test_package_boundaries.py")
    package_boundary_evidence_id = _evidence_id("pytest", "tests/test_package_boundaries.py")
    ensure_claim(
        claim_id=package_boundary_claim_id,
        title="Package workspace boundaries implemented",
        description="The workspace package set, dependency DAG, and first core extraction shims are executable and tested.",
        tier="T2",
        kind="architecture_boundary",
        feature_ids=package_boundary_feature_ids,
    )
    ensure_evidence(
        evidence_id=package_boundary_evidence_id,
        title="Package boundary pytest evidence",
        kind="pytest",
        tier="T2",
        path="tests/test_package_boundaries.py",
        claim_ids=[package_boundary_claim_id],
        test_ids=[package_boundary_test_id],
    )
    ensure_test(
        test_id=package_boundary_test_id,
        title="Package boundary workspace and shim coverage",
        status="passing",
        kind="pytest",
        path="tests/test_package_boundaries.py",
        feature_ids=package_boundary_feature_ids,
        claim_ids=[package_boundary_claim_id],
        evidence_ids=[package_boundary_evidence_id],
    )

    webtransport_feature_ids = [
        _feature_id("webtransport-h3-quic-scope"),
        _feature_id("webtransport-h3-quic-session-events"),
        _feature_id("webtransport-h3-quic-stream-events"),
        _feature_id("webtransport-h3-quic-datagram-events"),
        _feature_id("webtransport-h3-quic-completion-events"),
        _feature_id("tigr-asgi-contract-0-1-2-validation"),
    ]
    webtransport_specs = ["spc:2010", "spc:2003", "spc:2004", "spc:2037"]
    webtransport_rows = [
        (
            webtransport_feature_ids[0],
            "WebTransport H3/QUIC scope",
            "Implement first-class contract webtransport scope support over the package-owned HTTP/3 and QUIC stack.",
        ),
        (
            webtransport_feature_ids[1],
            "WebTransport session events",
            "Implement webtransport.connect, webtransport.accept, webtransport.disconnect, and webtransport.close event handling.",
        ),
        (
            webtransport_feature_ids[2],
            "WebTransport stream events",
            "Implement WebTransport stream receive/send handling on HTTP/3 request streams.",
        ),
        (
            webtransport_feature_ids[3],
            "WebTransport datagram events",
            "Implement WebTransport datagram receive/send handling over QUIC DATAGRAM where enabled.",
        ),
        (
            webtransport_feature_ids[4],
            "WebTransport completion events",
            "Emit and validate transport.emit.complete semantics for WebTransport stream, datagram, message, and session operations.",
        ),
        (
            webtransport_feature_ids[5],
            "tigr-asgi-contract 0.1.2 validation",
            "Validate Tigrcorn's supported native contract and ASGI/3 compatibility surface against tigr-asgi-contract 0.1.2 without adopting product-layer REST or JSON-RPC runtimes.",
        ),
    ]
    for feature_id, title, description in webtransport_rows:
        ensure_feature(
            feature_id=feature_id,
            title=title,
            description=description,
            tier="T3",
            slot="webtransport-contract",
            horizon="current",
            implementation_status="implemented",
        )
    link_feature_specs(webtransport_feature_ids, webtransport_specs)

    webtransport_operator_rows = [
        (
            "webtransport-protocol-cli-flag",
            "WebTransport protocol CLI flag",
            "Expose webtransport as a public --protocol value for WebTransport-over-H3/QUIC listeners.",
            ["spc:2008", "spc:2010", "spc:2003", "spc:2004"],
            ["webtransport-h3-quic-scope"],
        ),
        (
            "webtransport-carrier-normalization",
            "WebTransport carrier normalization",
            "Normalize valid WebTransport protocol selection to the required HTTP/3 and QUIC carrier state.",
            ["spc:2008", "spc:2010", "spc:2003", "spc:2004"],
            ["webtransport-protocol-cli-flag"],
        ),
        (
            "webtransport-carrier-fail-closed",
            "WebTransport carrier fail-closed validation",
            "Fail closed when WebTransport is selected on non-UDP listeners or without required H3/QUIC carrier semantics.",
            ["spc:2008", "spc:2010", "spc:2003", "spc:2004", "spc:2029"],
            ["webtransport-protocol-cli-flag"],
        ),
        (
            "webtransport-config-toml",
            "WebTransport config TOML",
            "Expose WebTransport protocol and tuning through config-file listener protocol lists and the [webtransport] block.",
            ["spc:2007", "spc:2010"],
            ["webtransport-protocol-cli-flag"],
        ),
        (
            "webtransport-env-var",
            "WebTransport environment variables",
            "Expose WebTransport protocol and tuning through the configured environment prefix mechanism.",
            ["spc:2008", "spc:2010"],
            ["webtransport-config-toml"],
        ),
        (
            "webtransport-public-api",
            "WebTransport public API",
            "Expose WebTransport protocol and tuning through public config construction APIs.",
            ["spc:2028", "spc:2010"],
            ["webtransport-config-toml"],
        ),
        (
            "webtransport-max-sessions-flag",
            "WebTransport max sessions flag",
            "Expose --webtransport-max-sessions and map it to webtransport.max_sessions.",
            ["spc:2008", "spc:2010"],
            ["webtransport-protocol-cli-flag"],
        ),
        (
            "webtransport-max-streams-flag",
            "WebTransport max streams flag",
            "Expose --webtransport-max-streams and map it to webtransport.max_streams.",
            ["spc:2008", "spc:2010"],
            ["webtransport-protocol-cli-flag"],
        ),
        (
            "webtransport-max-datagram-size-flag",
            "WebTransport max datagram size flag",
            "Expose --webtransport-max-datagram-size and map it to webtransport.max_datagram_size.",
            ["spc:2008", "spc:2010"],
            ["webtransport-protocol-cli-flag"],
        ),
        (
            "webtransport-origin-flag",
            "WebTransport origin flag",
            "Expose repeatable --webtransport-origin and map it to webtransport.origins.",
            ["spc:2008", "spc:2010"],
            ["webtransport-protocol-cli-flag"],
        ),
        (
            "webtransport-path-flag",
            "WebTransport path flag",
            "Expose --webtransport-path and map it to webtransport.path.",
            ["spc:2008", "spc:2010"],
            ["webtransport-protocol-cli-flag"],
        ),
    ]
    webtransport_operator_feature_ids = []
    for raw_feature_id, title, description, spec_ids, requires in webtransport_operator_rows:
        feature_id = _feature_id(raw_feature_id)
        webtransport_operator_feature_ids.append(feature_id)
        ensure_feature(
            feature_id=feature_id,
            title=title,
            description=description,
            tier="T3",
            slot="webtransport-operator-surface",
            horizon="current",
            implementation_status="implemented",
        )
        link_feature_specs([feature_id], spec_ids)
        for required_raw in requires:
            required_id = _feature_id(required_raw)
            if required_id not in features[feature_id]["requires"]:
                features[feature_id]["requires"].append(required_id)

    rest_jsonrpc_exclusion_ids = [
        _feature_id("rest-runtime-exclusion"),
        _feature_id("json-rpc-runtime-exclusion"),
    ]
    for feature_id, title, description in [
        (
            rest_jsonrpc_exclusion_ids[0],
            "REST runtime exclusion",
            "Tigrcorn does not implement a REST product runtime; REST remains an application/framework responsibility above ASGI HTTP.",
        ),
        (
            rest_jsonrpc_exclusion_ids[1],
            "JSON-RPC runtime exclusion",
            "Tigrcorn does not implement a JSON-RPC product runtime; JSON-RPC remains an application/framework responsibility above ASGI HTTP.",
        ),
    ]:
        ensure_feature(
            feature_id=feature_id,
            title=title,
            description=description,
            tier="T0",
            slot="product-boundary-exclusion",
            horizon="out_of_bounds",
            implementation_status="absent",
        )
    link_feature_specs(rest_jsonrpc_exclusion_ids, ["spc:2010", "spc:2024", "spc:2037"])

    contract_feature_rows = [
        (
            "contract-native-runtime",
            "Contract-native runtime",
            "Serve native tigr-asgi-contract applications without ASGI/3 translation in the application hot path.",
            ["spc:2011", "spc:2028"],
            "contract-runtime",
        ),
        (
            "contract-app-dispatch",
            "Contract app dispatch",
            "Dispatch contract-native applications through the native contract dispatcher.",
            ["spc:2011", "spc:2013", "spc:2028"],
            "contract-runtime",
        ),
        (
            "asgi3-compat-layer",
            "ASGI/3 compatibility layer",
            "Run ASGI/3 applications through an explicit first-class compatibility layer.",
            ["spc:2012", "spc:2034"],
            "asgi3-compatibility",
        ),
        (
            "compat-dispatch-selection",
            "Compatibility dispatch selection",
            "Select native contract or ASGI/3 compatibility dispatch before application traffic enters the hot path.",
            ["spc:2013", "spc:2025"],
            "dispatch-selection",
        ),
        (
            "asgi3-hot-path-isolation",
            "ASGI/3 hot-path isolation",
            "Keep ASGI/3 adapter code out of the native contract hot path unless ASGI/3 compatibility is selected.",
            ["spc:2012", "spc:2013"],
            "dispatch-selection",
        ),
        (
            "asgi-extension-bridge",
            "ASGI/3 extension bridge",
            "Expose contract-native metadata and capabilities to ASGI/3 applications through documented extensions.",
            ["spc:2014", "spc:2034"],
            "asgi3-compatibility",
        ),
        (
            "contract-http-scope",
            "Contract HTTP scope",
            "Validate and dispatch contract HTTP scopes with ASGI/3 scope compatibility where applicable.",
            ["spc:2015", "spc:2001", "spc:2002", "spc:2003"],
            "contract-scopes",
        ),
        (
            "contract-websocket-scope",
            "Contract WebSocket scope",
            "Validate and dispatch contract WebSocket scopes with ASGI/3 scope compatibility where applicable.",
            ["spc:2015", "spc:2005"],
            "contract-scopes",
        ),
        (
            "contract-lifespan-scope",
            "Contract lifespan scope",
            "Validate and dispatch contract lifespan scopes with ASGI/3 lifespan compatibility.",
            ["spc:2015", "spc:2012"],
            "contract-scopes",
        ),
        (
            "contract-webtransport-scope",
            "Contract WebTransport scope",
            "Validate and dispatch contract WebTransport scopes on the native contract path.",
            ["spc:2010", "spc:2015"],
            "contract-scopes",
        ),
        (
            "contract-http-event-map",
            "Contract HTTP event map",
            "Map HTTP events between tigr-asgi-contract and ASGI/3 compatibility events.",
            ["spc:2016", "spc:2001", "spc:2002", "spc:2003"],
            "contract-events",
        ),
        (
            "contract-websocket-event-map",
            "Contract WebSocket event map",
            "Map WebSocket events between tigr-asgi-contract and ASGI/3 compatibility events.",
            ["spc:2016", "spc:2005"],
            "contract-events",
        ),
        (
            "contract-lifespan-event-map",
            "Contract lifespan event map",
            "Map lifespan events between tigr-asgi-contract and ASGI/3 compatibility events.",
            ["spc:2016", "spc:2012"],
            "contract-events",
        ),
        (
            "contract-webtransport-events",
            "Contract WebTransport events",
            "Implement WebTransport session, stream, datagram, and completion event handling on the native contract path.",
            ["spc:2010", "spc:2016", "spc:2022"],
            "contract-events",
        ),
        (
            "emit-completion-events",
            "Emit completion events",
            "Represent emit completion semantics using tigr-asgi-contract completion levels.",
            ["spc:2017", "spc:2031", "spc:2037"],
            "completion",
        ),
        (
            "emit-completion-asgi-extension",
            "Emit completion ASGI/3 extension",
            "Expose completion metadata to ASGI/3 applications through documented extensions.",
            ["spc:2014", "spc:2017", "spc:2034", "spc:2037"],
            "completion",
        ),
        (
            "unit-id-propagation",
            "Unit ID propagation",
            "Propagate contract unit identifiers through dispatch, events, observability, and ASGI/3 extensions.",
            ["spc:2018", "spc:2030"],
            "identity",
        ),
        (
            "transport-metadata-model",
            "Transport metadata model",
            "Expose transport metadata through the contract metadata model and ASGI/3 extensions.",
            ["spc:2019", "spc:2030"],
            "metadata",
        ),
        (
            "tls-metadata-extension",
            "TLS metadata extension",
            "Expose TLS and security metadata through contract metadata and ASGI/3 extensions.",
            ["spc:2033", "spc:2014"],
            "metadata",
        ),
        (
            "family-capability-declaration",
            "Family capability declaration",
            "Declare request, session, message, stream, and datagram family capabilities through the contract model.",
            ["spc:2020"],
            "capabilities",
        ),
        (
            "binding-legality-validation",
            "Binding legality validation",
            "Validate binding, exchange, family, and subevent combinations against tigr-asgi-contract.",
            ["spc:2021"],
            "validation",
        ),
        (
            "contract-error-semantics",
            "Contract error semantics",
            "Reject invalid contract scopes, events, bindings, and compatibility mappings with deterministic errors.",
            ["spc:2029", "spc:2021"],
            "validation",
        ),
        (
            "generic-stream-runtime",
            "Generic stream runtime",
            "Model stream behavior as a contract-native runtime family.",
            ["spc:2022", "spc:2031", "spc:2037"],
            "streams",
        ),
        (
            "generic-datagram-runtime",
            "Generic datagram runtime",
            "Model datagram behavior as a contract-native runtime family.",
            ["spc:2022", "spc:2031", "spc:2037"],
            "datagrams",
        ),
        (
            "stream-backpressure-mapping",
            "Stream backpressure mapping",
            "Map stream backpressure and flow-control behavior into contract completion semantics.",
            ["spc:2031", "spc:2022", "spc:2037"],
            "flow-control",
        ),
        (
            "datagram-flow-control-mapping",
            "Datagram flow-control mapping",
            "Map datagram send behavior and carrier guarantees into contract completion semantics.",
            ["spc:2031", "spc:2022", "spc:2037"],
            "flow-control",
        ),
        (
            "contract-listener-endpoint-metadata",
            "Contract listener endpoint metadata",
            "Expose listener endpoint metadata for TCP, UDS, fd, pipe, and in-process listeners without inventing new application scope types.",
            ["spc:2036", "spc:2015", "spc:2030"],
            "endpoint-metadata",
        ),
        (
            "contract-uds-endpoint-metadata",
            "Contract UDS endpoint metadata",
            "Expose Unix domain socket listener metadata as endpoint metadata rather than a contract scope.",
            ["spc:2036", "spc:2015"],
            "endpoint-metadata",
        ),
        (
            "contract-fd-endpoint-metadata",
            "Contract fd endpoint metadata",
            "Expose inherited file descriptor listener identity through endpoint metadata.",
            ["spc:2036"],
            "endpoint-metadata",
        ),
        (
            "contract-pipe-endpoint-metadata",
            "Contract pipe endpoint metadata",
            "Expose pipe listener identity through endpoint metadata.",
            ["spc:2036"],
            "endpoint-metadata",
        ),
        (
            "contract-inproc-endpoint-metadata",
            "Contract in-process endpoint metadata",
            "Expose in-process listener identity through endpoint metadata.",
            ["spc:2036"],
            "endpoint-metadata",
        ),
        (
            "contract-tcp-connection-identity",
            "Contract TCP connection identity",
            "Propagate stable TCP connection identity through contract metadata and evidence.",
            ["spc:2036", "spc:2018", "spc:2030"],
            "transport-identity",
        ),
        (
            "contract-unix-connection-identity",
            "Contract Unix connection identity",
            "Propagate Unix listener connection identity through contract metadata and evidence.",
            ["spc:2036", "spc:2018", "spc:2030"],
            "transport-identity",
        ),
        (
            "contract-quic-connection-identity",
            "Contract QUIC connection identity",
            "Propagate QUIC connection identity through contract metadata and evidence.",
            ["spc:2036", "spc:2004", "spc:2018", "spc:2030"],
            "transport-identity",
        ),
        (
            "contract-http2-stream-identity",
            "Contract HTTP/2 stream identity",
            "Propagate HTTP/2 stream identity through contract metadata and event handling.",
            ["spc:2036", "spc:2002", "spc:2018"],
            "transport-identity",
        ),
        (
            "contract-http3-stream-identity",
            "Contract HTTP/3 stream identity",
            "Propagate HTTP/3 stream identity through contract metadata and event handling.",
            ["spc:2036", "spc:2003", "spc:2018"],
            "transport-identity",
        ),
        (
            "contract-webtransport-session-identity",
            "Contract WebTransport session identity",
            "Propagate WebTransport session identity through native contract metadata.",
            ["spc:2036", "spc:2010", "spc:2018", "spc:2022"],
            "transport-identity",
        ),
        (
            "contract-webtransport-stream-identity",
            "Contract WebTransport stream identity",
            "Propagate WebTransport stream identity through native contract metadata and stream events.",
            ["spc:2036", "spc:2010", "spc:2018", "spc:2022"],
            "transport-identity",
        ),
        (
            "contract-datagram-unit-identity",
            "Contract datagram unit identity",
            "Propagate datagram unit identity through native contract metadata and datagram events.",
            ["spc:2036", "spc:2018", "spc:2022"],
            "transport-identity",
        ),
        (
            "contract-tls-endpoint-metadata",
            "Contract TLS endpoint metadata",
            "Expose TLS endpoint state through contract metadata.",
            ["spc:2036", "spc:2033"],
            "security-metadata",
        ),
        (
            "contract-mtls-peer-metadata",
            "Contract mTLS peer metadata",
            "Expose mTLS peer certificate and verification metadata through contract metadata.",
            ["spc:2036", "spc:2033"],
            "security-metadata",
        ),
        (
            "contract-alpn-metadata",
            "Contract ALPN metadata",
            "Expose negotiated ALPN metadata through contract metadata and ASGI/3 extensions.",
            ["spc:2036", "spc:2033"],
            "security-metadata",
        ),
        (
            "contract-sni-metadata",
            "Contract SNI metadata",
            "Expose SNI metadata through contract metadata where available.",
            ["spc:2036", "spc:2033"],
            "security-metadata",
        ),
        (
            "contract-ocsp-crl-metadata",
            "Contract OCSP/CRL metadata",
            "Expose OCSP and CRL validation metadata through contract metadata where available.",
            ["spc:2036", "spc:2033"],
            "security-metadata",
        ),
        (
            "asgi3-endpoint-metadata-extension",
            "ASGI/3 endpoint metadata extension",
            "Expose endpoint metadata to ASGI/3 applications through documented Tigrcorn extension keys.",
            ["spc:2036", "spc:2014", "spc:2034"],
            "asgi3-extension-exposure",
        ),
        (
            "asgi3-transport-identity-extension",
            "ASGI/3 transport identity extension",
            "Expose transport identity metadata to ASGI/3 applications through documented Tigrcorn extension keys.",
            ["spc:2036", "spc:2014", "spc:2034"],
            "asgi3-extension-exposure",
        ),
        (
            "asgi3-security-metadata-extension",
            "ASGI/3 security metadata extension",
            "Expose security metadata to ASGI/3 applications through documented Tigrcorn extension keys.",
            ["spc:2036", "spc:2014", "spc:2034"],
            "asgi3-extension-exposure",
        ),
        (
            "asgi3-stream-datagram-extension",
            "ASGI/3 stream and datagram extension",
            "Expose stream and datagram metadata to ASGI/3 applications through documented Tigrcorn extension keys.",
            ["spc:2036", "spc:2014", "spc:2022", "spc:2034"],
            "asgi3-extension-exposure",
        ),
        (
            "contract-unsupported-scope-rejection",
            "Contract unsupported scope rejection",
            "Reject unsupported contract scope types before application dispatch.",
            ["spc:2036", "spc:2029", "spc:2015"],
            "rejection",
        ),
        (
            "contract-lossy-metadata-rejection",
            "Contract lossy metadata rejection",
            "Reject required metadata mappings that would lose correctness-critical endpoint or transport identity.",
            ["spc:2036", "spc:2029"],
            "rejection",
        ),
        (
            "contract-illegal-event-order-rejection",
            "Contract illegal event order rejection",
            "Reject illegal event ordering across contract-native and ASGI/3 compatibility paths.",
            ["spc:2036", "spc:2016", "spc:2029"],
            "rejection",
        ),
        (
            "contract-invalid-endpoint-metadata-rejection",
            "Contract invalid endpoint metadata rejection",
            "Reject malformed endpoint metadata before runtime dispatch or evidence promotion.",
            ["spc:2036", "spc:2029"],
            "rejection",
        ),
        (
            "sse-binding-classification",
            "SSE binding classification",
            "Classify SSE traffic through contract binding metadata without owning application-level SSE framework behavior.",
            ["spc:2023", "spc:2037"],
            "binding-classification",
        ),
        (
            "rest-binding-classification",
            "REST binding classification",
            "Classify REST metadata without implementing REST as a server-owned application runtime.",
            ["spc:2024", "spc:2037"],
            "binding-classification",
        ),
        (
            "jsonrpc-binding-classification",
            "JSON-RPC binding classification",
            "Classify JSON-RPC metadata without implementing JSON-RPC as a server-owned application runtime.",
            ["spc:2024", "spc:2037"],
            "binding-classification",
        ),
        (
            "contract-native-public-api",
            "Contract-native public API",
            "Provide a public API for registering and serving contract-native applications.",
            ["spc:2028"],
            "public-api",
        ),
        (
            "app-interface-cli-flag",
            "Application interface CLI flag",
            "Expose --app-interface with auto, tigr-asgi-contract, and asgi3 values for global app interface selection.",
            ["spc:2035", "spc:2008", "spc:2013"],
            "app-interface-selection",
        ),
        (
            "app-interface-config-toml",
            "Application interface config TOML",
            "Expose [app].interface in config files with auto, tigr-asgi-contract, and asgi3 values.",
            ["spc:2035", "spc:2007", "spc:2013", "spc:2025"],
            "app-interface-selection",
        ),
        (
            "app-interface-env-var",
            "Application interface environment variable",
            "Expose TIGRCORN_APP_INTERFACE through the configured environment prefix mechanism.",
            ["spc:2035", "spc:2008", "spc:2025"],
            "app-interface-selection",
        ),
        (
            "app-interface-public-api",
            "Application interface public API",
            "Expose app-interface selection through public programmatic startup and config construction APIs.",
            ["spc:2035", "spc:2028"],
            "app-interface-selection",
        ),
        (
            "app-interface-detection-precedence",
            "Application interface detection precedence",
            "Apply CLI greater-than env greater-than config file greater-than defaults precedence and explicit selection before introspection.",
            ["spc:2035", "spc:2013", "spc:2025"],
            "app-interface-selection",
        ),
        (
            "app-interface-fail-closed-ambiguity",
            "Application interface fail-closed ambiguity",
            "Fail closed for ambiguous or unsupported app interfaces unless an operator explicitly selects a supported app interface.",
            ["spc:2035", "spc:2012", "spc:2013", "spc:2025"],
            "app-interface-selection",
        ),
        (
            "static-delivery-contract-map",
            "Static delivery contract map",
            "Map static delivery and file-send behavior into contract metadata and ASGI/3 compatibility extensions.",
            ["spc:2032"],
            "http-feature-mapping",
        ),
        (
            "early-hints-contract-map",
            "Early Hints contract map",
            "Map HTTP 103 Early Hints behavior into contract metadata and ASGI/3 compatibility behavior.",
            ["spc:2032", "spc:2001", "spc:2002", "spc:2003"],
            "http-feature-mapping",
        ),
        (
            "alt-svc-contract-map",
            "Alt-Svc contract map",
            "Map Alt-Svc behavior into contract metadata and ASGI/3 compatibility behavior.",
            ["spc:2032", "spc:2001", "spc:2002", "spc:2003"],
            "http-feature-mapping",
        ),
        (
            "trailers-contract-map",
            "Trailers contract map",
            "Map HTTP trailers into contract events and ASGI/3 compatibility extensions.",
            ["spc:2032", "spc:2016", "spc:2001", "spc:2002", "spc:2003"],
            "http-feature-mapping",
        ),
        (
            "content-coding-contract-map",
            "Content coding contract map",
            "Map HTTP content-coding behavior into contract metadata and ASGI/3 compatibility behavior.",
            ["spc:2032", "spc:2001", "spc:2002", "spc:2003"],
            "http-feature-mapping",
        ),
        (
            "proxy-normalization-contract-map",
            "Proxy normalization contract map",
            "Map proxy and intermediary normalization behavior into contract metadata and ASGI/3 compatibility behavior.",
            ["spc:2032", "spc:2001", "spc:2002", "spc:2003"],
            "http-feature-mapping",
        ),
        (
            "observability-contract-metadata",
            "Observability contract metadata",
            "Expose contract metadata in logs, metrics, traces, and SSOT evidence.",
            ["spc:2030", "spc:2018", "spc:2019"],
            "observability",
        ),
        (
            "contract-conformance-tests",
            "Contract conformance tests",
            "Test contract conformance across native and ASGI/3 compatibility paths.",
            ["spc:2026"],
            "verification",
        ),
        (
            "asgi3-app-compat-suite",
            "ASGI/3 app compatibility suite",
            "Verify ASGI/3 framework applications continue to run through the compatibility layer.",
            ["spc:2012", "spc:2026", "spc:2034"],
            "verification",
        ),
        (
            "compat-feature-parity-matrix",
            "Compatibility feature parity matrix",
            "Maintain native contract versus ASGI/3 compatibility feature parity status.",
            ["spc:2034"],
            "compatibility-reporting",
        ),
        (
            "contract-release-evidence",
            "Contract release evidence",
            "Record release evidence for contract-native and ASGI/3 compatibility support claims.",
            ["spc:2026", "spc:2030"],
            "release-evidence",
        ),
        (
            "contract-docs-migration",
            "Contract docs migration",
            "Document the contract-native migration path and ASGI/3 compatibility policy.",
            ["spc:2027"],
            "documentation",
        ),
        (
            "contract-examples",
            "Contract examples",
            "Provide examples for native contract apps and ASGI/3 compatibility apps.",
            ["spc:2027", "spc:2028"],
            "documentation",
        ),
        (
            "ssot-contract-boundary-sync",
            "SSOT contract boundary sync",
            "Keep ADR, SPEC, feature, test, claim, evidence, and boundary records aligned for the contract-native support model.",
            ["spc:2026", "spc:2027", "spc:2034"],
            "governance",
        ),
    ]
    implemented_contract_app_interface_features = {
        "contract-native-runtime",
        "contract-app-dispatch",
        "contract-native-public-api",
        "compat-dispatch-selection",
        "asgi3-hot-path-isolation",
        "contract-listener-endpoint-metadata",
        "contract-uds-endpoint-metadata",
        "contract-fd-endpoint-metadata",
        "contract-pipe-endpoint-metadata",
        "contract-inproc-endpoint-metadata",
        "contract-tcp-connection-identity",
        "contract-unix-connection-identity",
        "contract-quic-connection-identity",
        "contract-http2-stream-identity",
        "contract-http3-stream-identity",
        "contract-webtransport-session-identity",
        "contract-webtransport-stream-identity",
        "contract-datagram-unit-identity",
        "contract-tls-endpoint-metadata",
        "contract-mtls-peer-metadata",
        "contract-alpn-metadata",
        "contract-sni-metadata",
        "contract-ocsp-crl-metadata",
        "asgi3-endpoint-metadata-extension",
        "asgi3-transport-identity-extension",
        "asgi3-security-metadata-extension",
        "asgi3-stream-datagram-extension",
        "contract-unsupported-scope-rejection",
        "contract-lossy-metadata-rejection",
        "contract-illegal-event-order-rejection",
        "contract-invalid-endpoint-metadata-rejection",
        "generic-stream-runtime",
        "generic-datagram-runtime",
        "stream-backpressure-mapping",
        "datagram-flow-control-mapping",
        "emit-completion-events",
        "emit-completion-asgi-extension",
        "rest-binding-classification",
        "jsonrpc-binding-classification",
        "sse-binding-classification",
        "app-interface-cli-flag",
        "app-interface-config-toml",
        "app-interface-env-var",
        "app-interface-public-api",
        "app-interface-detection-precedence",
        "app-interface-fail-closed-ambiguity",
    }
    contract_feature_ids = []
    for raw_feature_id, title, description, spec_ids, slot in contract_feature_rows:
        feature_id = _feature_id(raw_feature_id)
        implemented = raw_feature_id in implemented_contract_app_interface_features
        contract_feature_ids.append(feature_id)
        ensure_feature(
            feature_id=feature_id,
            title=title,
            description=description,
            tier="T3",
            slot=slot,
            horizon="current" if implemented else "next",
            implementation_status="implemented" if implemented else "absent",
        )
        link_feature_specs([feature_id], spec_ids)

    unsupported_compatibility_rows = [
        (
            "asgi2-compat-exclusion",
            "ASGI2 compatibility exclusion",
            "Tigrcorn does not support ASGI2 as a product interface; ASGI/3 is the only supported ASGI compatibility layer.",
        ),
        (
            "wsgi-compat-exclusion",
            "WSGI compatibility exclusion",
            "Tigrcorn does not support WSGI as a product interface; ASGI/3 is the only supported compatibility layer.",
        ),
        (
            "rsgi-compat-exclusion",
            "RSGI compatibility exclusion",
            "Tigrcorn does not support RSGI as a product interface; native tigr-asgi-contract and ASGI/3 compatibility are the supported app interfaces.",
        ),
    ]
    unsupported_compatibility_ids = []
    for raw_feature_id, title, description in unsupported_compatibility_rows:
        feature_id = _feature_id(raw_feature_id)
        unsupported_compatibility_ids.append(feature_id)
        ensure_feature(
            feature_id=feature_id,
            title=title,
            description=description,
            tier="T0",
            slot="compatibility-exclusion",
            horizon="out_of_bounds",
            implementation_status="absent",
        )
        link_feature_specs([feature_id], ["spc:2012", "spc:2026", "spc:2027", "spc:2034", "spc:2037"])

    closed_test_feature_ids = set(implemented_contract_app_interface_features) | {
        "webtransport-h3-quic-scope",
        "webtransport-h3-quic-session-events",
        "webtransport-h3-quic-stream-events",
        "webtransport-h3-quic-datagram-events",
        "webtransport-h3-quic-completion-events",
        "tigr-asgi-contract-0-1-2-validation",
        "webtransport-protocol-cli-flag",
        "webtransport-carrier-normalization",
        "webtransport-carrier-fail-closed",
        "webtransport-config-toml",
        "webtransport-env-var",
        "webtransport-public-api",
        "webtransport-max-sessions-flag",
        "webtransport-max-streams-flag",
        "webtransport-max-datagram-size-flag",
        "webtransport-origin-flag",
        "webtransport-path-flag",
        "rest-runtime-exclusion",
        "json-rpc-runtime-exclusion",
        "asgi2-compat-exclusion",
        "wsgi-compat-exclusion",
        "rsgi-compat-exclusion",
    }

    planned_test_inventory_path = "tests/test_contract_planned_coverage_inventory.py"

    def ensure_planned_feature_test(raw_feature_id: str, title: str) -> None:
        if raw_feature_id in closed_test_feature_ids:
            return
        feature_id = _feature_id(raw_feature_id)
        target_tier = str(features[feature_id]["plan"].get("target_claim_tier") or "T1")
        claim_id = _claim_id(f"planned-test-coverage-{raw_feature_id}")
        test_id = _test_id("planned", raw_feature_id)
        evidence_id = _evidence_id("planned", raw_feature_id)
        ensure_claim(
            claim_id=claim_id,
            title=f"Planned test coverage for {title}",
            description=f"Planned test coverage is recorded for feature {feature_id}.",
            tier=target_tier,
            kind="planned_test_coverage",
            feature_ids=[feature_id],
        )
        claims[claim_id]["status"] = "proposed"
        release_claim_ids.discard(claim_id)
        ensure_evidence(
            evidence_id=evidence_id,
            title=f"Planned test evidence anchor for {title}",
            kind="planned_test_inventory",
            tier="T1",
            path=planned_test_inventory_path,
            claim_ids=[claim_id],
            test_ids=[test_id],
        )
        release_evidence_ids.discard(evidence_id)
        ensure_test(
            test_id=test_id,
            title=f"Planned coverage: {title}",
            status="planned",
            kind="pytest",
            path=planned_test_inventory_path,
            feature_ids=[feature_id],
            claim_ids=[claim_id],
            evidence_ids=[evidence_id],
        )

    planned_feature_tests = [
        ("webtransport-h3-quic-scope", "WebTransport H3/QUIC scope"),
        ("webtransport-h3-quic-session-events", "WebTransport session events"),
        ("webtransport-h3-quic-stream-events", "WebTransport stream events"),
        ("webtransport-h3-quic-datagram-events", "WebTransport datagram events"),
        ("webtransport-h3-quic-completion-events", "WebTransport completion events"),
        ("tigr-asgi-contract-0-1-2-validation", "tigr-asgi-contract 0.1.2 validation"),
        ("rest-runtime-exclusion", "REST runtime exclusion"),
        ("json-rpc-runtime-exclusion", "JSON-RPC runtime exclusion"),
        ("asgi2-compat-exclusion", "ASGI2 compatibility exclusion"),
        ("wsgi-compat-exclusion", "WSGI compatibility exclusion"),
        ("rsgi-compat-exclusion", "RSGI compatibility exclusion"),
        ("governance-graph", "Governance graph"),
    ]
    for raw_feature_id, title in planned_feature_tests:
        ensure_planned_feature_test(raw_feature_id, title)

    for raw_feature_id, title, _description, _spec_ids, _slot in contract_feature_rows:
        ensure_planned_feature_test(raw_feature_id, title)

    concrete_closure_feature_tests = [
        ("webtransport-h3-quic-scope", "WebTransport H3/QUIC scope", "tests/test_webtransport_h3_quic_scope.py"),
        ("webtransport-h3-quic-session-events", "WebTransport H3/QUIC session events", "tests/test_webtransport_h3_quic_session_events.py"),
        ("webtransport-h3-quic-stream-events", "WebTransport H3/QUIC stream events", "tests/test_webtransport_h3_quic_stream_events.py"),
        ("webtransport-h3-quic-datagram-events", "WebTransport H3/QUIC datagram events", "tests/test_webtransport_h3_quic_datagram_events.py"),
        ("webtransport-h3-quic-completion-events", "WebTransport H3/QUIC completion events", "tests/test_webtransport_h3_quic_completion_events.py"),
        ("tigr-asgi-contract-0-1-2-validation", "tigr-asgi-contract 0.1.2 validation", "tests/test_tigr_asgi_contract_0_1_2_validation.py"),
        ("webtransport-protocol-cli-flag", "WebTransport protocol CLI flag", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-carrier-normalization", "WebTransport carrier normalization", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-carrier-fail-closed", "WebTransport carrier fail-closed validation", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-config-toml", "WebTransport config TOML", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-env-var", "WebTransport environment variables", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-public-api", "WebTransport public API", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-max-sessions-flag", "WebTransport max sessions flag", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-max-streams-flag", "WebTransport max streams flag", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-max-datagram-size-flag", "WebTransport max datagram size flag", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-origin-flag", "WebTransport origin flag", "tests/test_webtransport_operator_surface.py"),
        ("webtransport-path-flag", "WebTransport path flag", "tests/test_webtransport_operator_surface.py"),
        ("generic-stream-runtime", "Generic stream runtime", "tests/test_contract_generic_stream_runtime.py"),
        ("generic-datagram-runtime", "Generic datagram runtime", "tests/test_contract_generic_datagram_runtime.py"),
        ("stream-backpressure-mapping", "Stream backpressure mapping", "tests/test_contract_stream_backpressure_mapping.py"),
        ("datagram-flow-control-mapping", "Datagram flow-control mapping", "tests/test_contract_datagram_flow_control_mapping.py"),
        ("emit-completion-events", "Emit completion events", "tests/test_contract_emit_completion_events.py"),
        ("emit-completion-asgi-extension", "Emit completion ASGI/3 extension", "tests/test_contract_emit_completion_asgi_extension.py"),
        ("rest-binding-classification", "REST binding classification", "tests/test_contract_rest_binding_classification.py"),
        ("jsonrpc-binding-classification", "JSON-RPC binding classification", "tests/test_contract_jsonrpc_binding_classification.py"),
        ("sse-binding-classification", "SSE binding classification", "tests/test_contract_sse_binding_classification.py"),
        ("rest-runtime-exclusion", "REST runtime exclusion", "tests/test_rest_runtime_exclusion.py"),
        ("json-rpc-runtime-exclusion", "JSON-RPC runtime exclusion", "tests/test_json_rpc_runtime_exclusion.py"),
        ("asgi2-compat-exclusion", "ASGI2 compatibility exclusion", "tests/test_asgi2_compat_exclusion.py"),
        ("wsgi-compat-exclusion", "WSGI compatibility exclusion", "tests/test_wsgi_compat_exclusion.py"),
        ("rsgi-compat-exclusion", "RSGI compatibility exclusion", "tests/test_rsgi_compat_exclusion.py"),
        ("contract-listener-endpoint-metadata", "Contract listener endpoint metadata", "tests/test_contract_listener_endpoint_metadata.py"),
        ("contract-uds-endpoint-metadata", "Contract UDS endpoint metadata", "tests/test_contract_uds_endpoint_metadata.py"),
        ("contract-fd-endpoint-metadata", "Contract fd endpoint metadata", "tests/test_contract_fd_endpoint_metadata.py"),
        ("contract-pipe-endpoint-metadata", "Contract pipe endpoint metadata", "tests/test_contract_pipe_endpoint_metadata.py"),
        ("contract-inproc-endpoint-metadata", "Contract in-process endpoint metadata", "tests/test_contract_inproc_endpoint_metadata.py"),
        ("contract-tcp-connection-identity", "Contract TCP connection identity", "tests/test_contract_tcp_connection_identity.py"),
        ("contract-unix-connection-identity", "Contract Unix connection identity", "tests/test_contract_unix_connection_identity.py"),
        ("contract-quic-connection-identity", "Contract QUIC connection identity", "tests/test_contract_quic_connection_identity.py"),
        ("contract-http2-stream-identity", "Contract HTTP/2 stream identity", "tests/test_contract_http2_stream_identity.py"),
        ("contract-http3-stream-identity", "Contract HTTP/3 stream identity", "tests/test_contract_http3_stream_identity.py"),
        ("contract-webtransport-session-identity", "Contract WebTransport session identity", "tests/test_contract_webtransport_session_identity.py"),
        ("contract-webtransport-stream-identity", "Contract WebTransport stream identity", "tests/test_contract_webtransport_stream_identity.py"),
        ("contract-datagram-unit-identity", "Contract datagram unit identity", "tests/test_contract_datagram_unit_identity.py"),
        ("contract-tls-endpoint-metadata", "Contract TLS endpoint metadata", "tests/test_contract_tls_endpoint_metadata.py"),
        ("contract-mtls-peer-metadata", "Contract mTLS peer metadata", "tests/test_contract_mtls_peer_metadata.py"),
        ("contract-alpn-metadata", "Contract ALPN metadata", "tests/test_contract_alpn_metadata.py"),
        ("contract-sni-metadata", "Contract SNI metadata", "tests/test_contract_sni_metadata.py"),
        ("contract-ocsp-crl-metadata", "Contract OCSP/CRL metadata", "tests/test_contract_ocsp_crl_metadata.py"),
        ("asgi3-endpoint-metadata-extension", "ASGI/3 endpoint metadata extension", "tests/test_asgi3_endpoint_metadata_extension.py"),
        ("asgi3-transport-identity-extension", "ASGI/3 transport identity extension", "tests/test_asgi3_transport_identity_extension.py"),
        ("asgi3-security-metadata-extension", "ASGI/3 security metadata extension", "tests/test_asgi3_security_metadata_extension.py"),
        ("asgi3-stream-datagram-extension", "ASGI/3 stream and datagram extension", "tests/test_asgi3_stream_datagram_extension.py"),
        ("contract-unsupported-scope-rejection", "Contract unsupported scope rejection", "tests/test_contract_unsupported_scope_rejection.py"),
        ("contract-lossy-metadata-rejection", "Contract lossy metadata rejection", "tests/test_contract_lossy_metadata_rejection.py"),
        ("contract-illegal-event-order-rejection", "Contract illegal event order rejection", "tests/test_contract_illegal_event_order_rejection.py"),
        ("contract-invalid-endpoint-metadata-rejection", "Contract invalid endpoint metadata rejection", "tests/test_contract_invalid_endpoint_metadata_rejection.py"),
    ]
    concrete_feature_tests = [
        (
            "contract-native-runtime",
            "Contract-native runtime",
            "tests/test_contract_native_runtime.py",
            "tst:contract-native-runtime",
            "clm:contract-native-runtime-implemented",
            "evd:contract-native-runtime-pytest",
        ),
        (
            "contract-app-dispatch",
            "Contract app dispatch",
            "tests/test_contract_app_dispatch.py",
            "tst:contract-app-dispatch",
            "clm:contract-app-dispatch-implemented",
            "evd:contract-app-dispatch-pytest",
        ),
        (
            "contract-native-public-api",
            "Contract-native public API",
            "tests/test_contract_native_public_api.py",
            "tst:contract-native-public-api",
            "clm:contract-native-public-api-implemented",
            "evd:contract-native-public-api-pytest",
        ),
        (
            "compat-dispatch-selection",
            "Compatibility dispatch selection",
            "tests/test_compat_dispatch_selection.py",
            "tst:compat-dispatch-selection",
            "clm:compat-dispatch-selection-implemented",
            "evd:compat-dispatch-selection-pytest",
        ),
        (
            "asgi3-hot-path-isolation",
            "ASGI3 hot path isolation",
            "tests/test_asgi3_hot_path_isolation.py",
            "tst:asgi3-hot-path-isolation",
            "clm:asgi3-hot-path-isolation-implemented",
            "evd:asgi3-hot-path-isolation-pytest",
        ),
        (
            "app-interface-cli-flag",
            "Application interface CLI flag",
            "tests/test_app_interface_cli_flag.py",
            "tst:app-interface-cli-flag",
            "clm:app-interface-cli-flag-implemented",
            "evd:app-interface-cli-flag-pytest",
        ),
        (
            "app-interface-config-toml",
            "Application interface config TOML",
            "tests/test_app_interface_config_toml.py",
            "tst:app-interface-config-toml",
            "clm:app-interface-config-toml-implemented",
            "evd:app-interface-config-toml-pytest",
        ),
        (
            "app-interface-env-var",
            "Application interface environment variable",
            "tests/test_app_interface_env_var.py",
            "tst:app-interface-env-var",
            "clm:app-interface-env-var-implemented",
            "evd:app-interface-env-var-pytest",
        ),
        (
            "app-interface-public-api",
            "Application interface public API",
            "tests/test_app_interface_public_api.py",
            "tst:app-interface-public-api",
            "clm:app-interface-public-api-implemented",
            "evd:app-interface-public-api-pytest",
        ),
        (
            "app-interface-detection-precedence",
            "Application interface detection precedence",
            "tests/test_app_interface_detection_precedence.py",
            "tst:app-interface-detection-precedence",
            "clm:app-interface-detection-precedence-implemented",
            "evd:app-interface-detection-precedence-pytest",
        ),
        (
            "app-interface-fail-closed-ambiguity",
            "Application interface fail-closed ambiguity",
            "tests/test_app_interface_fail_closed_ambiguity.py",
            "tst:app-interface-fail-closed-ambiguity",
            "clm:app-interface-fail-closed-ambiguity-implemented",
            "evd:app-interface-fail-closed-ambiguity-pytest",
        ),
    ]
    for raw_feature_id, title, path in concrete_closure_feature_tests:
        slug = _slug(raw_feature_id)
        concrete_feature_tests.append(
            (
                raw_feature_id,
                title,
                path,
                f"tst:{slug}",
                f"clm:{slug}-implemented",
                f"evd:{slug}-pytest",
            )
        )
    for raw_feature_id, title, path, test_id, claim_id, evidence_id in concrete_feature_tests:
        feature_id = _feature_id(raw_feature_id)
        out_of_bounds = features[feature_id]["plan"]["horizon"] == "out_of_bounds"
        ensure_claim(
            claim_id=claim_id,
            title=f"{title} {'exclusion verified' if out_of_bounds else 'implemented'}",
            description=(
                f"Executable negative tests verify product-boundary exclusion for {feature_id}."
                if out_of_bounds
                else f"Executable tests verify feature {feature_id}."
            ),
            tier="T3",
            kind="boundary_exclusion" if out_of_bounds else "implementation",
            feature_ids=[feature_id],
        )
        ensure_evidence(
            evidence_id=evidence_id,
            title=f"Pytest evidence for {title}",
            kind="pytest",
            tier="T3",
            path=path,
            claim_ids=[claim_id],
            test_ids=[test_id],
        )
        ensure_test(
            test_id=test_id,
            title=title,
            status="passing",
            kind="pytest",
            path=path,
            feature_ids=[feature_id],
            claim_ids=[claim_id],
            evidence_ids=[evidence_id],
        )

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
        description="Packaged profile JSON artifacts under src/tigrcorn/profiles/ are inventoried and linked to the package's profile validation path.",
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
    deployment_profile_rows = [
        (
            "default",
            "Default deployment profile",
            "Safe zero-config TCP HTTP/1.1 baseline with deny-by-default transport posture.",
            "default-baseline-profile",
            [],
        ),
        (
            "strict-h1-origin",
            "Strict HTTP/1.1 origin deployment profile",
            "Conservative HTTP/1.1 origin posture with explicit host validation and no proxy trust by default.",
            "strict-h1-origin-profile",
            ["default"],
        ),
        (
            "strict-h2-origin",
            "Strict HTTP/2 origin deployment profile",
            "TLS-backed HTTP/2 origin posture with explicit ALPN and h2-only protocol selection.",
            "strict-h2-origin-profile",
            ["strict-h1-origin"],
        ),
        (
            "strict-h3-edge",
            "Strict HTTP/3 edge deployment profile",
            "Dual TCP and UDP edge posture with explicit HTTP/3 and QUIC listeners, Retry, Alt-Svc, and default 0-RTT denial.",
            "strict-h3-edge-profile",
            ["strict-h2-origin"],
        ),
        (
            "strict-mtls-origin",
            "Strict mTLS origin deployment profile",
            "HTTP/2 TLS origin posture with mandatory client certificates and explicit trust-store requirements.",
            "strict-mtls-origin-profile",
            ["strict-h2-origin"],
        ),
        (
            "static-origin",
            "Static origin deployment profile",
            "Static origin posture with explicit mounted delivery, validators, ranges, and no proxy trust by default.",
            "static-origin-profile",
            ["strict-h1-origin"],
        ),
    ]
    for raw_profile_id, title, description, raw_feature_id, parent_profiles in deployment_profile_rows:
        ensure_profile(
            profile_id=_profile_id(raw_profile_id),
            title=title,
            description=description,
            kind="deployment",
            feature_ids=[profile_feature_id, _feature_id(raw_feature_id)],
            profile_ids=[_profile_id(parent) for parent in parent_profiles],
            claim_tier="T2",
        )

    for profile_path in sorted((ROOT / "src" / "tigrcorn" / "profiles").glob("*.profile.json")):
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
        "schema_version": package_meta["schema_version"],
        "repo": {
            "id": "repo:tigrcorn",
            "name": "tigrcorn",
            "version": version,
            "kind": "repo-local",
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
        "profiles": sorted(profiles.values(), key=lambda row: row["id"]),
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
                "profile_ids": sorted(profiles),
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
