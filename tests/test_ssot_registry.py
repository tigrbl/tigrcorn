from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tigrcorn.ssot_baseline import iter_feature_baselines


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
    assert len(committed["features"]) == 340
    assert not any(
        baseline.missing_tiers
        for baseline in iter_feature_baselines(committed)
    )


def _has_t012_baseline(registry: dict, feature_id: str) -> bool:
    baselines = {baseline.feature_id: baseline for baseline in iter_feature_baselines(registry)}
    return set(baselines[feature_id].claim_tiers) >= {"T0", "T1", "T2"}


def test_normalized_ssot_tree_exists() -> None:
    for name in INIT_DIRS:
        assert (ROOT / ".ssot" / name).is_dir(), name


def test_ssot_registry_imports_all_claim_rows_and_freezes_active_boundary() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    source = json.loads((ROOT / "docs/review/conformance/claims_registry.json").read_text(encoding="utf-8"))
    ssot_claim_titles = {row["title"] for row in registry["claims"]}
    source_claim_ids = {row["id"] for row in source["current_and_candidate_claims"]}

    assert source_claim_ids <= ssot_claim_titles
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    authoritative = boundaries["bnd:authoritative-0-3-9"]
    assert authoritative["status"] == "frozen"
    assert authoritative["frozen"] is True
    assert authoritative["canonical_registry_source"] == ".ssot/registry.json"


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


def test_ssot_pytest_inventory_uses_capability_scoped_references() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    lifecycle_label = re.compile(r"phase[0-9][a-z0-9]*|step[0-9]*", re.IGNORECASE)

    scoped_rows = [
        row
        for family in ("tests", "evidence")
        for row in registry[family]
        if str(row.get("kind", "")).startswith("pytest")
    ]

    offenders = [
        (row["id"], row.get("title", ""), row.get("path", ""))
        for row in scoped_rows
        if lifecycle_label.search(" ".join(str(row.get(key, "")) for key in ("id", "title", "path")))
    ]
    assert offenders == []


def test_ssot_current_entities_avoid_lifecycle_label_references() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    lifecycle_label = re.compile(r"\b(phase|step)[-_ ]?\d*\w*\b", re.IGNORECASE)
    families = (
        "features",
        "profiles",
        "claims",
        "tests",
        "evidence",
        "issues",
        "risks",
        "boundaries",
        "releases",
    )
    fields = ("id", "title", "path", "description", "summary", "name")

    offenders = [
        (family, row.get("id"), field, str(row.get(field, "")))
        for family in families
        for row in registry[family]
        for field in fields
        if lifecycle_label.search(str(row.get(field, "")))
    ]
    assert offenders == []


def test_committed_ssot_registry_validates_with_ssot_registry() -> None:
    ssot = pytest.importorskip("ssot_registry.api.validate")
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    report = ssot.validate_registry_document(
        registry,
        registry_path=ROOT / ".ssot" / "registry.json",
        repo_root=ROOT,
    )
    assert report["passed"], report["failures"]


def test_ssot_declares_webtransport_in_scope_and_rest_jsonrpc_out() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    features = {row["id"]: row for row in registry["features"]}

    for feature_id in {
        "feat:webtransport-h3-quic-scope",
        "feat:webtransport-h3-quic-session-events",
        "feat:webtransport-h3-quic-stream-events",
        "feat:webtransport-h3-quic-datagram-events",
        "feat:webtransport-h3-quic-completion-events",
        "feat:contract-webtransport-stream-identity",
        "feat:tigr-asgi-contract-peer-validation",
    }:
        feature = features[feature_id]
        assert _has_t012_baseline(registry, feature_id)
        assert feature["plan"]["horizon"] == "current"
        assert "spc:2010" in feature["spec_ids"]

    for feature_id in {"feat:rest-runtime-exclusion", "feat:json-rpc-runtime-exclusion"}:
        feature = features[feature_id]
        assert _has_t012_baseline(registry, feature_id)
        assert feature["implementation_status"] == "implemented"
        assert feature["plan"]["horizon"] == "explicit"
        assert feature["lifecycle"]["note"].startswith("Explicit product-boundary exclusion")
        assert "spc:2010" in feature["spec_ids"]


def test_ssot_declares_client_session_protocol_coverage() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    features = {row["id"]: row for row in registry["features"]}

    for feature_id in {
        "feat:client-session-protocol-coverage-matrix",
        "feat:client-session-topology-schedules",
        "feat:client-session-scope-and-identity-classification",
        "feat:client-session-isolation-properties",
        "feat:client-session-pressure-modes",
        "feat:client-session-fault-cleanup-modes",
    }:
        feature = features[feature_id]
        assert _has_t012_baseline(registry, feature_id)
        assert feature["plan"]["horizon"] == "current"
        assert "spc:2053" in feature["spec_ids"]


def test_ssot_declares_app_interface_selection_surfaces() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    specs = {row["id"]: row for row in registry["specs"]}
    features = {row["id"]: row for row in registry["features"]}

    assert "spc:2035" in specs
    for feature_id in {
        "feat:app-interface-cli-flag",
        "feat:app-interface-config-toml",
        "feat:app-interface-env-var",
        "feat:app-interface-public-api",
        "feat:app-interface-detection-precedence",
        "feat:app-interface-fail-closed-ambiguity",
    }:
        feature = features[feature_id]
        assert _has_t012_baseline(registry, feature_id)
        assert feature["plan"]["horizon"] == "current"
        assert feature["plan"]["slot"] == "app-interface-selection"
        assert "spc:2035" in feature["spec_ids"]


def test_ssot_declares_first_class_http_status_code_set() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    specs = {row["id"]: row for row in registry["specs"]}
    features = {row["id"]: row for row in registry["features"]}
    tests = {row["id"]: row for row in registry["tests"]}

    expected_codes = {
        100,
        101,
        103,
        200,
        201,
        202,
        204,
        206,
        301,
        302,
        304,
        307,
        308,
        400,
        401,
        402,
        403,
        404,
        405,
        406,
        408,
        413,
        416,
        421,
        426,
        431,
        500,
        502,
        503,
        504,
    }
    assert "spc:2043" in specs
    for code in expected_codes:
        matching_features = [
            feature
            for feature in features.values()
            if feature["id"].startswith(f"feat:http-status-{code}-")
        ]
        assert len(matching_features) == 1
        feature = matching_features[0]
        assert feature["plan"]["slot"] == "http-status-code"
        assert feature["plan"]["horizon"] == "current"
        assert "spc:2043" in feature["spec_ids"]
        matching_tests = [
            test
            for test in tests.values()
            if test["id"].startswith(f"tst:http-status-http-status-{code}-")
        ]
        assert len(matching_tests) == 1
        assert feature["id"] in matching_tests[0]["feature_ids"]


def test_ssot_links_concrete_contract_app_interface_tests_to_features() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    tests = {row["id"]: row for row in registry["tests"]}

    expected = {
        "tst:contract-native-runtime": ("feat:contract-native-runtime", "tests/test_contract_native_runtime.py"),
        "tst:contract-app-dispatch": ("feat:contract-app-dispatch", "tests/test_contract_app_dispatch.py"),
        "tst:contract-native-public-api": ("feat:contract-native-public-api", "tests/test_contract_native_public_api.py"),
        "tst:compat-dispatch-selection": ("feat:compat-dispatch-selection", "tests/test_compat_dispatch_selection.py"),
        "tst:asgi3-hot-path-isolation": ("feat:asgi3-hot-path-isolation", "tests/test_asgi3_hot_path_isolation.py"),
        "tst:app-interface-cli-flag": ("feat:app-interface-cli-flag", "tests/test_app_interface_cli_flag.py"),
        "tst:app-interface-config-toml": ("feat:app-interface-config-toml", "tests/test_app_interface_config_toml.py"),
        "tst:app-interface-env-var": ("feat:app-interface-env-var", "tests/test_app_interface_env_var.py"),
        "tst:app-interface-public-api": ("feat:app-interface-public-api", "tests/test_app_interface_public_api.py"),
        "tst:app-interface-detection-precedence": ("feat:app-interface-detection-precedence", "tests/test_app_interface_detection_precedence.py"),
        "tst:app-interface-fail-closed-ambiguity": ("feat:app-interface-fail-closed-ambiguity", "tests/test_app_interface_fail_closed_ambiguity.py"),
    }

    for test_id, (feature_id, path) in expected.items():
        row = tests[test_id]
        assert row["status"] == "passing"
        assert row["path"] == path
        assert feature_id in row["feature_ids"]
