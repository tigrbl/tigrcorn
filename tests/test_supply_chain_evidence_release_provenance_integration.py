from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tigrcorn.certification.artifacts import write_certification_artifacts
from tigrcorn.certification.release_gates import evaluate_release_gates
from tigrcorn.certification.supply_chain import (
    package_record,
    write_supply_chain_release_bundle,
)


SIGNING_KEY = "supply-chain-release-key"


def _packages():
    return (
        package_record("tigrcorn-certification", "0.3.16", ["src/tigrcorn_certification/__init__.py", "pyproject.toml"]),
        package_record("tigrcorn-runtime", "0.3.16", ["src/tigrcorn_runtime/__init__.py", "pyproject.toml"]),
    )


def _sbom():
    return {
        "bomFormat": "CycloneDX",
        "components": [
            {"name": "tigrcorn-certification", "version": "0.3.16"},
            {"name": "tigrcorn-runtime", "version": "0.3.16"},
        ],
        "specVersion": "1.5",
    }


def _provenance():
    return {
        "builder": {"id": "github-actions"},
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": [
            {"name": "tigrcorn-certification"},
            {"name": "tigrcorn-runtime"},
        ],
    }


def _artifact_sections() -> dict[str, dict[str, object]]:
    return {
        "protocol.json": {"http": ["h1", "h2", "h3"]},
        "runtime.json": {"listeners": [{"id": "listener-1", "transport": "tcp"}]},
        "security.json": {"tls": {"min": "1.3"}},
        "performance.json": {"benchmarks": [{"name": "steady-state", "p95_ms": 10}]},
        "interop.json": {"peers": ["reference-a"]},
    }


def _hashes(packages=None) -> dict[str, str]:
    return {package.name: package.digest for package in (packages or _packages())}


def _write_boundary(root: Path, *, certification_artifact_root: str | None = None) -> Path:
    supply_chain = {
        "bundle_root": "release-evidence/supply-chain",
        "workspace_packages": ["tigrcorn-certification", "tigrcorn-runtime"],
    }
    if certification_artifact_root is not None:
        supply_chain["certification_artifact_root"] = certification_artifact_root
    boundary = root / "boundary.json"
    boundary.write_text(
        json.dumps(
            {
                "gates": {"require_supply_chain_release_provenance": True},
                "supply_chain": supply_chain,
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return boundary


def _write_bundle(root: Path, *, certification_artifact_root: Path | None = None, packages=None) -> Path:
    bundle_root = root / "release-evidence" / "supply-chain"
    write_supply_chain_release_bundle(
        bundle_root,
        packages=packages or _packages(),
        sbom=_sbom(),
        provenance=_provenance(),
        package_hashes=_hashes(packages),
        certification_artifact_root=certification_artifact_root,
        release_train={"tigrcorn": "0.3.16"},
    )
    return bundle_root


def test_release_gate_loads_sbom_and_slsa_from_release_bundle(tmp_path: Path) -> None:
    boundary = _write_boundary(tmp_path)
    _write_bundle(tmp_path)

    report = evaluate_release_gates(tmp_path, boundary_path=boundary)

    assert report.passed is True
    assert report.artifact_status["supply_chain"]["sbom_present"] is True
    assert report.artifact_status["supply_chain"]["slsa_present"] is True
    assert report.artifact_status["supply_chain"]["release_eligible"] is True


def test_release_gate_fails_when_sbom_file_missing(tmp_path: Path) -> None:
    boundary = _write_boundary(tmp_path)
    bundle_root = _write_bundle(tmp_path)
    (bundle_root / "sbom.json").unlink()

    report = evaluate_release_gates(tmp_path, boundary_path=boundary)

    assert report.passed is False
    assert "supply chain: missing supply-chain release bundle file: sbom.json" in report.failures
    assert report.artifact_status["supply_chain"]["release_eligible"] is False


def test_release_gate_fails_when_slsa_file_missing(tmp_path: Path) -> None:
    boundary = _write_boundary(tmp_path)
    bundle_root = _write_bundle(tmp_path)
    (bundle_root / "slsa-provenance.json").unlink()

    report = evaluate_release_gates(tmp_path, boundary_path=boundary)

    assert report.passed is False
    assert "supply chain: missing supply-chain release bundle file: slsa-provenance.json" in report.failures
    assert report.artifact_status["supply_chain"]["release_eligible"] is False


def test_release_gate_fails_on_package_hash_mismatch(tmp_path: Path) -> None:
    boundary = _write_boundary(tmp_path)
    bundle_root = _write_bundle(tmp_path)
    hashes = json.loads((bundle_root / "package-hashes.json").read_text(encoding="utf-8"))
    hashes["tigrcorn-runtime"] = "0" * 64
    (bundle_root / "package-hashes.json").write_text(
        json.dumps(hashes, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )

    report = evaluate_release_gates(tmp_path, boundary_path=boundary)

    assert report.passed is False
    assert "supply chain: tigrcorn-runtime hash mismatch" in report.failures


def test_release_gate_fails_on_untracked_workspace_package(tmp_path: Path) -> None:
    boundary = _write_boundary(tmp_path)
    _write_bundle(tmp_path, packages=(_packages()[0],))

    report = evaluate_release_gates(tmp_path, boundary_path=boundary)

    assert report.passed is False
    assert "supply chain: workspace package tigrcorn-runtime missing release provenance entry" in report.failures


def test_supply_chain_manifest_links_generated_certification_artifacts(tmp_path: Path) -> None:
    artifact_root = tmp_path / "certification-artifacts"
    write_certification_artifacts(_artifact_sections(), artifact_root, signing_key=SIGNING_KEY)
    boundary = _write_boundary(tmp_path, certification_artifact_root="certification-artifacts")
    bundle_root = _write_bundle(tmp_path, certification_artifact_root=artifact_root)

    report = evaluate_release_gates(tmp_path, boundary_path=boundary)
    manifest = json.loads((bundle_root / "supply-chain-manifest.json").read_text(encoding="utf-8"))

    assert report.passed is True
    assert manifest["certification_artifacts"]["manifest.json"] == hashlib.sha256(
        (artifact_root / "manifest.json").read_bytes()
    ).hexdigest()
    assert report.artifact_status["supply_chain"]["release_eligible"] is True
