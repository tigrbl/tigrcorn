from __future__ import annotations

import json
from pathlib import Path

from tigrcorn_certification.release_gates import evaluate_contract_registry_release_gate, evaluate_release_gates
from tigrcorn_contract.registry import export_contract_registry


def _certified_contract(**overrides):
    contract = {
        "certified": True,
        "contract_id": "example.contract",
        "implemented": True,
        "owner_module": "tigrcorn_contract.registry",
        "owner_package": "tigrcorn-contract",
        "stability": "certified",
        "title": "Example contract",
        "traceability": {
            "evidence_ids": ["evd:example-contract-pytest"],
            "implementation_refs": ["tigrcorn_contract.registry:export_contract_registry"],
            "negative_test_ids": ["tst:example-contract-negative"],
            "release_certified": True,
            "rfcs": ["RFC 9110"],
            "spec_ids": ["spc:example-contract"],
            "status": "complete",
            "test_ids": ["tst:example-contract-positive", "tst:example-contract-negative"],
        },
        "version": "1.0",
    }
    contract.update(overrides)
    return contract


def _write_registry(root: Path, contracts: list[dict]) -> Path:
    path = root / "contract_registry.json"
    path.write_text(
        json.dumps({"contracts": contracts, "registry": "test.contracts", "schema_version": "1.0"}),
        encoding="utf-8",
    )
    return path


def _write_minimal_boundary(root: Path, registry_path: Path) -> None:
    conformance_root = root / "docs" / "review" / "conformance"
    conformance_root.mkdir(parents=True)
    (conformance_root / "certification_boundary.json").write_text(
        json.dumps(
            {
                "contract_registry": registry_path.name,
                "gates": {
                    "require_contract_registry_traceability": True,
                },
            }
        ),
        encoding="utf-8",
    )


def test_contract_registry_blocks_certified_contract_without_evidence_chain(tmp_path: Path) -> None:
    broken = _certified_contract(
        traceability={
            "evidence_ids": [],
            "implementation_refs": ["tigrcorn_contract.registry:export_contract_registry"],
            "negative_test_ids": [],
            "release_certified": False,
            "rfcs": ["RFC 9110"],
            "spec_ids": ["spc:example-contract"],
            "status": "partial",
            "test_ids": [],
        }
    )
    registry_path = _write_registry(tmp_path, [broken])

    failures = evaluate_contract_registry_release_gate(tmp_path, contract_registry_path=registry_path.name)

    assert "certified contract example.contract must have complete traceability" in failures
    assert "certified contract example.contract must set traceability.release_certified" in failures
    assert "certified contract example.contract is missing traceability.evidence_ids" in failures
    assert "certified contract example.contract is missing traceability.negative_test_ids" in failures


def test_release_gate_reads_contract_registry(tmp_path: Path) -> None:
    registry_path = _write_registry(tmp_path, [_certified_contract(stability="stable")])
    _write_minimal_boundary(tmp_path, registry_path)

    report = evaluate_release_gates(tmp_path, boundary_path="docs/review/conformance/certification_boundary.json")

    assert report.passed is False
    assert "certified contract example.contract must use certified stability" in report.failures
    assert any(path.endswith("contract_registry.json") for path in report.checked_files)
    assert report.artifact_status["contract_registry"]["failed"] is True


def test_contract_registry_traceability_links_actual_ssot_ids(tmp_path: Path) -> None:
    registry_path = _write_registry(tmp_path, [_certified_contract()])
    (tmp_path / ".ssot").mkdir()
    (tmp_path / ".ssot" / "registry.json").write_text(
        json.dumps(
            {
                "evidence": [{"id": "evd:example-contract-pytest"}],
                "specs": [{"id": "spc:example-contract"}],
                "tests": [
                    {"id": "tst:example-contract-positive"},
                    {"id": "tst:example-contract-negative"},
                ],
            }
        ),
        encoding="utf-8",
    )

    failures = evaluate_contract_registry_release_gate(
        tmp_path,
        contract_registry_path=registry_path.name,
        require_ssot_links=True,
    )

    assert failures == []


def test_deprecated_contract_cannot_be_release_certified(tmp_path: Path) -> None:
    deprecated = _certified_contract(
        contract_id="example.contract.v0",
        replacement_contract_id="example.contract",
        retirement_note="Replaced by example.contract.",
        stability="deprecated",
    )
    registry_path = _write_registry(tmp_path, [deprecated])

    failures = evaluate_contract_registry_release_gate(tmp_path, contract_registry_path=registry_path.name)

    assert failures == ["deprecated contract example.contract.v0 cannot be release certified"]


def test_repository_contract_registry_release_gate_passes_current_registry() -> None:
    failures = evaluate_contract_registry_release_gate(Path.cwd())

    assert failures == []
    assert export_contract_registry()["registry"] == "tigrcorn.contracts"
