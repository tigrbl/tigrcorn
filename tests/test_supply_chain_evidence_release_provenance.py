from __future__ import annotations

import json

from tigrcorn.certification.supply_chain import (
    dependency_drift_report,
    has_slsa_provenance,
    has_spdx_or_cyclonedx,
    package_list,
    package_record,
    release_train_evidence,
    supply_chain_manifest,
    validate_package_manifest_integrity,
    validate_release_evidence,
)


def _packages():
    return (
        package_record("tigrcorn-runtime", "0.3.16", ["src/tigrcorn_runtime/__init__.py", "pyproject.toml"]),
        package_record("tigrcorn-certification", "0.3.16", ["src/tigrcorn_certification/__init__.py", "pyproject.toml"]),
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


def _hashes(packages=None):
    return {package.name: package.digest for package in (packages or _packages())}


def test_supply_chain_evidence_manifest_shape() -> None:
    manifest = supply_chain_manifest(
        _packages(),
        sbom=_sbom(),
        provenance=_provenance(),
        certification_artifacts={"manifest.json": "abc123"},
        release_train={"tigrcorn": "0.3.16"},
    )

    assert tuple(manifest) == (
        "certification_artifacts",
        "manifest_version",
        "packages",
        "provenance",
        "release_train",
        "schema",
        "sbom",
    )
    assert manifest["schema"] == "tigrcorn.supply-chain-provenance"
    assert manifest["sbom"] == {"format": "CycloneDX", "present": True}
    assert manifest["provenance"]["present"] is True
    assert json.dumps(manifest, sort_keys=True)


def test_supply_chain_package_list_deterministic() -> None:
    packages = tuple(reversed(_packages()))

    first = package_list(packages)
    second = package_list(tuple(reversed(packages)))

    assert [package["name"] for package in first] == ["tigrcorn-certification", "tigrcorn-runtime"]
    assert first == second


def test_supply_chain_spdx_or_cyclonedx_present() -> None:
    assert has_spdx_or_cyclonedx(_sbom()) is True
    assert has_spdx_or_cyclonedx({"SPDXID": "SPDXRef-DOCUMENT", "spdxVersion": "SPDX-2.3"}) is True
    assert has_spdx_or_cyclonedx({"bomFormat": "unknown"}) is False


def test_supply_chain_slsa_provenance_present() -> None:
    assert has_slsa_provenance(_provenance()) is True
    assert has_slsa_provenance({"predicateType": "https://example.invalid", "builder": {}, "subject": []}) is False


def test_supply_chain_package_manifest_integrity() -> None:
    packages = _packages()

    assert validate_package_manifest_integrity(packages) == []
    broken = package_record("tigrcorn-runtime", "0.3.16", [])
    assert validate_package_manifest_integrity((broken,)) == ["tigrcorn-runtime has no files"]


def test_supply_chain_release_train_evidence() -> None:
    evidence = release_train_evidence(_packages(), "0.3.16")

    assert evidence == {
        "package_family_versions": {
            "tigrcorn-certification": "0.3.16",
            "tigrcorn-runtime": "0.3.16",
        },
        "release_train": "0.3.16",
        "train_package_count": 2,
    }


def test_supply_chain_dependency_drift_report() -> None:
    report = dependency_drift_report(
        {"aioquic": "1.3.0", "cryptography": "46.0.0"},
        {"aioquic": "1.3.0", "cryptography": "47.0.0", "unexpected": "1.0"},
    )

    assert report == {
        "changed": {"cryptography": {"expected": "46.0.0", "observed": "47.0.0"}},
        "missing": [],
        "passed": False,
        "unexpected": ["unexpected"],
    }


def test_supply_chain_certification_artifact_linkage() -> None:
    manifest = supply_chain_manifest(
        _packages(),
        sbom=_sbom(),
        provenance=_provenance(),
        certification_artifacts={"manifest.json": "abc123"},
    )

    result = validate_release_evidence(
        packages=_packages(),
        sbom=_sbom(),
        provenance=_provenance(),
        package_hashes=_hashes(),
        sbom_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
        provenance_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
        certification_artifacts={"manifest.json": "abc123"},
        manifest=manifest,
    )

    assert result == {"failures": [], "release_eligible": True}


def test_supply_chain_missing_sbom_fails_release() -> None:
    result = validate_release_evidence(
        packages=_packages(),
        sbom=None,
        provenance=_provenance(),
        package_hashes=_hashes(),
        sbom_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
        provenance_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
    )

    assert result["release_eligible"] is False
    assert "missing SPDX or CycloneDX SBOM" in result["failures"]


def test_supply_chain_missing_provenance_fails_release() -> None:
    result = validate_release_evidence(
        packages=_packages(),
        sbom=_sbom(),
        provenance=None,
        package_hashes=_hashes(),
        sbom_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
        provenance_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
    )

    assert result["release_eligible"] is False
    assert "missing SLSA provenance" in result["failures"]


def test_supply_chain_package_hash_mismatch_fails() -> None:
    result = validate_release_evidence(
        packages=_packages(),
        sbom=_sbom(),
        provenance=_provenance(),
        package_hashes={"tigrcorn-certification": "0" * 64, "tigrcorn-runtime": _packages()[0].digest},
        sbom_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
        provenance_package_names=["tigrcorn-certification", "tigrcorn-runtime"],
    )

    assert result["release_eligible"] is False
    assert "tigrcorn-certification hash mismatch" in result["failures"]


def test_supply_chain_untracked_package_fails() -> None:
    result = validate_release_evidence(
        packages=_packages(),
        sbom=_sbom(),
        provenance=_provenance(),
        package_hashes=_hashes(),
        sbom_package_names=["tigrcorn-runtime"],
        provenance_package_names=["tigrcorn-runtime"],
    )

    assert result["release_eligible"] is False
    assert "tigrcorn-certification missing SBOM/provenance entry" in result["failures"]
