from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests" / "fixtures_protocol_scope" / "fixture_manifest.json"
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"
SPEC_ID = "spc:2039"


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _fixtures() -> list[dict[str, Any]]:
    fixtures = _manifest()["fixtures"]
    assert isinstance(fixtures, list)
    return fixtures


def _registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _rows_by_id(name: str) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in _registry()[name]}


FIXTURES = _fixtures()


def _fixture_ids() -> list[str]:
    return [fixture["id"] for fixture in FIXTURES]


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_each_protocol_scope_fixture_declares_required_fields(fixture: dict[str, Any]) -> None:
    assert set(fixture) >= {
        "id",
        "feature_id",
        "title",
        "surface_kind",
        "surface",
        "fixture_path",
        "coverage_paths",
        "coverage_terms",
    }


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_each_protocol_scope_fixture_artifact_exists(fixture: dict[str, Any]) -> None:
    assert (ROOT / fixture["fixture_path"]).is_file()


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_each_protocol_scope_fixture_declares_existing_coverage_paths(fixture: dict[str, Any]) -> None:
    coverage_paths = fixture["coverage_paths"]

    assert coverage_paths
    for coverage_path in coverage_paths:
        assert (ROOT / coverage_path).is_file()


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_each_protocol_scope_fixture_coverage_mentions_surface(fixture: dict[str, Any]) -> None:
    coverage_text = "\n".join((ROOT / path).read_text(encoding="utf-8").lower() for path in fixture["coverage_paths"])

    assert any(term.lower() in coverage_text for term in fixture["coverage_terms"])


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_each_protocol_scope_fixture_has_ssot_feature(fixture: dict[str, Any]) -> None:
    features = _rows_by_id("features")
    feature = features[fixture["feature_id"]]

    assert feature["title"] == fixture["title"]
    assert feature["implementation_status"] == "implemented"
    assert feature["plan"]["slot"] == "protocol-scope-fixtures"
    assert SPEC_ID in feature["spec_ids"]


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_each_protocol_scope_fixture_has_ssot_test_link(fixture: dict[str, Any]) -> None:
    tests = _rows_by_id("tests")
    feature = _rows_by_id("features")[fixture["feature_id"]]
    linked_tests = [tests[test_id] for test_id in feature["test_ids"] if test_id in tests]

    assert any(test["path"] == "tests/test_protocol_scope_fixtures.py" for test in linked_tests)


def test_fixture_manifest_spec_and_registry_spec_are_aligned() -> None:
    specs = _rows_by_id("specs")

    assert _manifest()["spec_id"] == SPEC_ID
    assert SPEC_ID in specs
    assert "adr:1033" in specs[SPEC_ID]["adr_ids"]
