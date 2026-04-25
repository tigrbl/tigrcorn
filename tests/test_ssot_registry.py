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


def test_ssot_declares_webtransport_in_scope_and_rest_jsonrpc_out() -> None:
    registry = json.loads((ROOT / ".ssot" / "registry.json").read_text(encoding="utf-8"))
    features = {row["id"]: row for row in registry["features"]}

    for feature_id in {
        "feat:webtransport-h3-quic-scope",
        "feat:webtransport-h3-quic-session-events",
        "feat:webtransport-h3-quic-stream-events",
        "feat:webtransport-h3-quic-datagram-events",
        "feat:webtransport-h3-quic-completion-events",
        "feat:tigr-asgi-contract-0-1-2-validation",
    }:
        feature = features[feature_id]
        assert feature["implementation_status"] == "implemented"
        assert feature["plan"]["horizon"] == "current"
        assert "spc:2010" in feature["spec_ids"]

    for feature_id in {"feat:rest-runtime-exclusion", "feat:json-rpc-runtime-exclusion"}:
        feature = features[feature_id]
        assert feature["implementation_status"] == "absent"
        assert feature["plan"]["horizon"] == "out_of_bounds"
        assert "spc:2010" in feature["spec_ids"]


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
        assert feature["implementation_status"] == "implemented"
        assert feature["plan"]["horizon"] == "current"
        assert feature["plan"]["slot"] == "app-interface-selection"
        assert "spc:2035" in feature["spec_ids"]


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
