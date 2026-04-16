from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ssot_sync import build_registry


ROOT = Path(__file__).resolve().parents[1]
INIT_DIRS = (
    "adr",
    "cache",
    "evidence",
    "graphs",
    "reports",
    "releases",
    "schemas",
    "specs",
)


def test_committed_ssot_registry_is_current() -> None:
    committed = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    generated = build_registry()
    assert committed == generated


def test_normalized_ssot_tree_exists() -> None:
    for name in INIT_DIRS:
        assert (ROOT / ".ssot" / name).is_dir(), name


def test_ssot_registry_imports_all_claim_rows_and_freezes_active_boundary() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    source = json.loads((ROOT / "docs/review/conformance/claims_registry.json").read_text(encoding="utf-8"))
    ssot_claim_titles = {row["title"] for row in registry["claims"]}
    source_claim_ids = {row["id"] for row in source["current_and_candidate_claims"]}

    assert source_claim_ids <= ssot_claim_titles
    assert registry["boundaries"][0]["status"] == "frozen"
    assert registry["boundaries"][0]["frozen"] is True
    assert registry["boundaries"][0]["canonical_registry_source"] == ".ssot/registry.json"


def test_ssot_registry_tracks_all_repo_local_adrs_specs_profiles_and_test_modules() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))

    adr_paths = {row["path"] for row in registry["adrs"]}
    for path in (ROOT / ".ssot" / "adr").glob("ADR-*.md"):
        assert path.relative_to(ROOT).as_posix() in adr_paths

    spec_paths = {row["path"] for row in registry["specs"]}
    for path in (ROOT / ".ssot" / "specs").glob("SPEC-*.md"):
        assert path.relative_to(ROOT).as_posix() in spec_paths

    evidence_paths = {row["path"] for row in registry["evidence"]}
    for path in (ROOT / "profiles").glob("*.profile.json"):
        assert path.relative_to(ROOT).as_posix() in evidence_paths

    test_paths = {row["path"] for row in registry["tests"]}
    for path in (ROOT / "tests").glob("test_*.py"):
        assert path.relative_to(ROOT).as_posix() in test_paths


def test_committed_ssot_registry_validates_with_ssot_registry() -> None:
    ssot = pytest.importorskip("ssot_registry.api.validate")
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    report = ssot.validate_registry_document(
        registry,
        registry_path=ROOT / ".ssot" / "registry.json",
        repo_root=ROOT,
    )
    assert report["passed"], report["failures"]
