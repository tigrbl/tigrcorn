from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

from tools.ssot_sync import build_registry

ROOT = Path(__file__).resolve().parents[1]
PROOF_MANIFEST = ROOT / "docs/review/conformance/contract_proof_boundary.json"
PROOF_FEATURE_IDS = {
    "feat:contract-docs-migration",
    "feat:contract-examples",
    "feat:ssot-contract-boundary-sync",
    "feat:contract-release-evidence",
    "feat:asgi3-app-compat-suite",
    "feat:contract-conformance-tests",
}


def _load_manifest() -> dict[str, object]:
    return json.loads(PROOF_MANIFEST.read_text(encoding="utf-8"))


def test_contract_proof_manifest_references_existing_artifacts() -> None:
    manifest = _load_manifest()

    assert manifest["boundary_id"] == "bnd:contract-proof-next"
    assert manifest["status"] == "closed"
    assert set(manifest["feature_ids"]) == PROOF_FEATURE_IDS
    assert manifest["canonical_registry_source"] == ".ssot/registry.json"

    for key in ("canonical_docs", "examples", "release_evidence_files", "conformance_tests"):
        for path in manifest[key]:
            assert (ROOT / path).is_file(), path

    assert (ROOT / manifest["release_evidence_root"]).is_dir()


def test_contract_proof_boundary_and_upstreams_are_frozen_in_registry() -> None:
    manifest = _load_manifest()
    registry = build_registry()
    boundaries = {row["id"]: row for row in registry["boundaries"]}
    features = {row["id"]: row for row in registry["features"]}

    boundary = boundaries["bnd:contract-proof-next"]
    assert boundary["status"] == "frozen"
    assert boundary["frozen"] is True
    assert set(boundary["feature_ids"]) == PROOF_FEATURE_IDS

    for boundary_id in manifest["upstream_boundaries"]:
        upstream = boundaries[boundary_id]
        assert upstream["status"] == "frozen"
        assert upstream["frozen"] is True

    for feature_id in PROOF_FEATURE_IDS:
        assert features[feature_id]["implementation_status"] == "implemented"


def test_contract_proof_features_have_passing_executable_rows() -> None:
    registry = build_registry()
    passing_feature_ids = {
        feature_id
        for row in registry["tests"]
        if row["status"] == "passing" and row["path"] == "tests/test_contract_proof_boundary.py"
        for feature_id in row["feature_ids"]
    }

    assert PROOF_FEATURE_IDS <= passing_feature_ids


def test_contract_examples_are_importable_and_executable() -> None:
    native = importlib.import_module("examples.contract.native_contract_app")
    asgi3 = importlib.import_module("examples.contract.asgi3_compat_app")

    contract = native.build_response_contract("/proof")
    assert contract["scope"]["path"] == "/proof"
    assert contract["unit"].unit_id == "example-request"
    assert contract["feature_map"]["feature"] == "alt-svc"
    assert [event["type"] for event in contract["events"]] == [
        "http.response.start",
        "http.response.body",
    ]

    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    asyncio.run(asgi3.app({"type": "http", "method": "GET", "path": "/compat"}, receive, send))

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["extensions"]["tigrcorn.unit"]["unit_id"] == "asgi3-example-request"
    assert sent[1]["body"] == b"asgi3 compatibility example"
