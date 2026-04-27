from __future__ import annotations

import json
from pathlib import Path

from tigrcorn_certification import (
    certification_explicit_surface_catalog,
    certification_explicit_surface_ids,
    validate_explicit_surface_manifest,
)
from tools.ssot_sync import build_registry

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/review/conformance/certification_explicit_surfaces.json"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_explicit_surface_manifest_matches_packaged_catalog() -> None:
    manifest = _manifest()
    failures = validate_explicit_surface_manifest(manifest)

    assert failures == []
    assert tuple(manifest["feature_ids"]) == certification_explicit_surface_ids()
    assert len(certification_explicit_surface_catalog()) == 25


def test_explicit_surface_artifacts_exist() -> None:
    manifest = _manifest()

    assert (ROOT / manifest["release_evidence_root"]).is_dir()
    for key in ("required_docs", "release_evidence_files", "closure_tests"):
        for path in manifest[key]:
            assert (ROOT / path).is_file(), path


def test_explicit_surface_boundary_is_frozen_and_implemented() -> None:
    manifest = _manifest()
    registry = build_registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    features = {row["id"]: row for row in registry["features"]}

    boundary = boundaries["bnd:certification-explicit-surfaces"]
    assert boundary["status"] == "frozen"
    assert boundary["frozen"] is True
    assert tuple(boundary["feature_ids"]) == tuple(manifest["feature_ids"])

    for feature_id in certification_explicit_surface_ids():
        feature = features[feature_id]
        assert feature["implementation_status"] == "implemented", feature_id
        assert feature["plan"]["horizon"] == "explicit", feature_id
        assert "tst:certification-explicit-surfaces-boundary" in feature["test_ids"]


def test_explicit_surface_closure_test_links_every_feature() -> None:
    registry = build_registry()
    tests = {row["id"]: row for row in registry["tests"]}
    closure = tests["tst:certification-explicit-surfaces-boundary"]

    assert closure["status"] == "passing"
    assert closure["path"] == "tests/test_certification_explicit_surfaces_boundary.py"
    assert tuple(closure["feature_ids"]) == certification_explicit_surface_ids()
