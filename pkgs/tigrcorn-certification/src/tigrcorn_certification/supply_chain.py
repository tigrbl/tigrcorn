from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .artifacts import canonical_json


class SupplyChainEvidenceError(ValueError):
    """Raised when supply-chain evidence is not release eligible."""


RELEASE_BUNDLE_FILES: dict[str, str] = {
    "manifest": "supply-chain-manifest.json",
    "package_hashes": "package-hashes.json",
    "packages": "packages.json",
    "provenance": "slsa-provenance.json",
    "sbom": "sbom.json",
}


@dataclass(frozen=True, slots=True)
class PackageRecord:
    name: str
    version: str
    files: tuple[str, ...]
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "files": list(self.files),
            "name": self.name,
            "version": self.version,
        }


def package_record(name: str, version: str, files: list[str] | tuple[str, ...]) -> PackageRecord:
    normalized_files = tuple(sorted(str(path).replace("\\", "/") for path in files))
    payload = {"files": list(normalized_files), "name": name, "version": version}
    return PackageRecord(name=name, version=version, files=normalized_files, digest=_sha256(canonical_json(payload)))


def package_list(packages: list[PackageRecord] | tuple[PackageRecord, ...]) -> list[dict[str, Any]]:
    return [package.as_dict() for package in sorted(packages, key=lambda item: (item.name, item.version))]


def supply_chain_manifest(
    packages: list[PackageRecord] | tuple[PackageRecord, ...],
    *,
    sbom: Mapping[str, Any] | None,
    provenance: Mapping[str, Any] | None,
    certification_artifacts: Mapping[str, str] | None = None,
    release_train: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "certification_artifacts": _stable_mapping(certification_artifacts or {}),
        "manifest_version": 1,
        "packages": package_list(packages),
        "provenance": _provenance_summary(provenance),
        "release_train": _stable_mapping(release_train or {}),
        "schema": "tigrcorn.supply-chain-provenance",
        "sbom": _sbom_summary(sbom),
    }


def has_spdx_or_cyclonedx(sbom: Mapping[str, Any] | None) -> bool:
    if not sbom:
        return False
    bom_format = str(sbom.get("bomFormat", "")).lower()
    spdx_id = str(sbom.get("SPDXID", ""))
    spdx_version = str(sbom.get("spdxVersion", ""))
    return bom_format == "cyclonedx" or spdx_id.startswith("SPDXRef-") or spdx_version.startswith("SPDX-")


def has_slsa_provenance(provenance: Mapping[str, Any] | None) -> bool:
    if not provenance:
        return False
    predicate_type = str(provenance.get("predicateType", ""))
    builder = provenance.get("builder")
    subject = provenance.get("subject")
    return "slsa" in predicate_type.lower() and isinstance(builder, Mapping) and isinstance(subject, list) and bool(subject)


def validate_package_manifest_integrity(packages: list[PackageRecord] | tuple[PackageRecord, ...]) -> list[str]:
    failures: list[str] = []
    for package in packages:
        if not package.name:
            failures.append("package has no name")
        if not package.version:
            failures.append(f"{package.name or '<unknown>'} has no version")
        if not package.files:
            failures.append(f"{package.name or '<unknown>'} has no files")
        expected = package_record(package.name, package.version, package.files).digest
        if package.digest != expected:
            failures.append(f"{package.name or '<unknown>'} hash mismatch")
    return failures


def release_train_evidence(packages: list[PackageRecord] | tuple[PackageRecord, ...], train_version: str) -> dict[str, Any]:
    versions = {package.name: package.version for package in sorted(packages, key=lambda item: item.name)}
    return {
        "package_family_versions": versions,
        "release_train": train_version,
        "train_package_count": len(versions),
    }


def dependency_drift_report(expected: Mapping[str, str], observed: Mapping[str, str]) -> dict[str, Any]:
    expected_keys = set(expected)
    observed_keys = set(observed)
    changed = {
        name: {"expected": expected[name], "observed": observed[name]}
        for name in sorted(expected_keys & observed_keys)
        if expected[name] != observed[name]
    }
    return {
        "changed": changed,
        "missing": sorted(expected_keys - observed_keys),
        "unexpected": sorted(observed_keys - expected_keys),
        "passed": not changed and not (expected_keys - observed_keys) and not (observed_keys - expected_keys),
    }


def validate_certification_artifact_linkage(
    manifest: Mapping[str, Any],
    certification_artifacts: Mapping[str, str],
) -> list[str]:
    failures: list[str] = []
    linked = dict(manifest.get("certification_artifacts", {}))
    for name, digest in sorted(certification_artifacts.items()):
        if linked.get(name) != digest:
            failures.append(f"certification artifact link mismatch: {name}")
    return failures


def validate_release_evidence(
    *,
    packages: list[PackageRecord] | tuple[PackageRecord, ...],
    sbom: Mapping[str, Any] | None,
    provenance: Mapping[str, Any] | None,
    package_hashes: Mapping[str, str],
    sbom_package_names: list[str] | tuple[str, ...],
    provenance_package_names: list[str] | tuple[str, ...],
    certification_artifacts: Mapping[str, str] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    failures = validate_package_manifest_integrity(packages)
    if not has_spdx_or_cyclonedx(sbom):
        failures.append("missing SPDX or CycloneDX SBOM")
    if not has_slsa_provenance(provenance):
        failures.append("missing SLSA provenance")

    sbom_names = set(sbom_package_names)
    provenance_names = set(provenance_package_names)
    for package in sorted(packages, key=lambda item: item.name):
        expected_digest = package_hashes.get(package.name)
        if expected_digest != package.digest:
            failures.append(f"{package.name} hash mismatch")
        if package.name not in sbom_names or package.name not in provenance_names:
            failures.append(f"{package.name} missing SBOM/provenance entry")

    if certification_artifacts is not None:
        if manifest is None:
            failures.append("missing certification artifact manifest linkage")
        else:
            failures.extend(validate_certification_artifact_linkage(manifest, certification_artifacts))

    return {"failures": failures, "release_eligible": not failures}


def generated_certification_artifact_links(artifact_root: str | Path) -> dict[str, str]:
    root = Path(artifact_root)
    links: dict[str, str] = {}
    if not root.exists():
        return links
    for path in sorted(item for item in root.iterdir() if item.is_file()):
        links[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return links


def write_supply_chain_release_bundle(
    output_directory: str | Path,
    *,
    packages: list[PackageRecord] | tuple[PackageRecord, ...],
    sbom: Mapping[str, Any],
    provenance: Mapping[str, Any],
    package_hashes: Mapping[str, str] | None = None,
    certification_artifacts: Mapping[str, str] | None = None,
    certification_artifact_root: str | Path | None = None,
    release_train: Mapping[str, str] | None = None,
) -> dict[str, Path]:
    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    artifact_links = (
        dict(certification_artifacts)
        if certification_artifacts is not None
        else generated_certification_artifact_links(certification_artifact_root)
        if certification_artifact_root is not None
        else {}
    )
    manifest = supply_chain_manifest(
        packages,
        sbom=sbom,
        provenance=provenance,
        certification_artifacts=artifact_links,
        release_train=release_train,
    )
    payloads: dict[str, Mapping[str, Any] | list[dict[str, Any]]] = {
        RELEASE_BUNDLE_FILES["manifest"]: manifest,
        RELEASE_BUNDLE_FILES["package_hashes"]: dict(package_hashes or {package.name: package.digest for package in packages}),
        RELEASE_BUNDLE_FILES["packages"]: package_list(packages),
        RELEASE_BUNDLE_FILES["provenance"]: provenance,
        RELEASE_BUNDLE_FILES["sbom"]: sbom,
    }
    written: dict[str, Path] = {}
    for name, payload in sorted(payloads.items()):
        path = root / name
        rendered = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
        written[name] = path
    return written


def validate_release_bundle(
    bundle_directory: str | Path,
    *,
    workspace_packages: list[str] | tuple[str, ...] = (),
    certification_artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(bundle_directory)
    failures: list[str] = []
    checked_files: list[str] = []
    payloads: dict[str, Any] = {}
    for key, filename in RELEASE_BUNDLE_FILES.items():
        path = root / filename
        checked_files.append(str(path))
        if not path.exists():
            failures.append(f"missing supply-chain release bundle file: {filename}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
            payloads[key] = json.loads(text)
            canonical = json.dumps(payloads[key], ensure_ascii=True, separators=(",", ":"), sort_keys=True)
            if text != canonical:
                failures.append(f"{filename} is not canonical JSON")
        except Exception as exc:
            failures.append(f"{filename} is not readable JSON: {exc}")

    packages = _package_records_from_payload(payloads.get("packages", []), failures=failures)
    package_hashes = _string_mapping(payloads.get("package_hashes", {}), failures=failures, label="package-hashes.json")
    sbom = payloads.get("sbom") if isinstance(payloads.get("sbom"), Mapping) else None
    provenance = payloads.get("provenance") if isinstance(payloads.get("provenance"), Mapping) else None
    manifest = payloads.get("manifest") if isinstance(payloads.get("manifest"), Mapping) else None
    sbom_package_names = _sbom_package_names(sbom)
    provenance_package_names = _provenance_package_names(provenance)
    certification_artifacts = (
        generated_certification_artifact_links(certification_artifact_root)
        if certification_artifact_root is not None
        else None
    )
    failures.extend(
        validate_release_evidence(
            packages=packages,
            sbom=sbom,
            provenance=provenance,
            package_hashes=package_hashes,
            sbom_package_names=tuple(sorted(sbom_package_names)),
            provenance_package_names=tuple(sorted(provenance_package_names)),
            certification_artifacts=certification_artifacts,
            manifest=manifest,
        )["failures"]
    )

    package_names = {package.name for package in packages}
    for package_name in sorted(str(item) for item in workspace_packages):
        if package_name not in package_names:
            failures.append(f"workspace package {package_name} missing release provenance entry")

    return {
        "checked_files": checked_files,
        "failures": failures,
        "package_count": len(packages),
        "release_eligible": not failures,
        "sbom_present": has_spdx_or_cyclonedx(sbom),
        "slsa_present": has_slsa_provenance(provenance),
    }


def _sbom_summary(sbom: Mapping[str, Any] | None) -> dict[str, Any]:
    if not sbom:
        return {"format": None, "present": False}
    if str(sbom.get("bomFormat", "")).lower() == "cyclonedx":
        return {"format": "CycloneDX", "present": True}
    return {"format": "SPDX", "present": has_spdx_or_cyclonedx(sbom)}


def _provenance_summary(provenance: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "predicate_type": str((provenance or {}).get("predicateType", "")) or None,
        "present": has_slsa_provenance(provenance),
    }


def _stable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(canonical_json(value))


def _package_records_from_payload(value: Any, *, failures: list[str]) -> tuple[PackageRecord, ...]:
    if not isinstance(value, list):
        failures.append("packages.json is missing a package list")
        return ()
    records: list[PackageRecord] = []
    for item in value:
        if not isinstance(item, Mapping):
            failures.append("packages.json contains malformed package record")
            continue
        files = item.get("files", [])
        if not isinstance(files, list):
            failures.append(f"{item.get('name', '<unknown>')} package files are malformed")
            files = []
        records.append(
            PackageRecord(
                name=str(item.get("name", "")),
                version=str(item.get("version", "")),
                files=tuple(str(path) for path in files),
                digest=str(item.get("digest", "")),
            )
        )
    return tuple(records)


def _string_mapping(value: Any, *, failures: list[str], label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        failures.append(f"{label} is missing a mapping")
        return {}
    return {str(key): str(child) for key, child in value.items()}


def _sbom_package_names(sbom: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(sbom, Mapping):
        return set()
    names: set[str] = set()
    components = sbom.get("components", [])
    if isinstance(components, list):
        for component in components:
            if isinstance(component, Mapping) and component.get("name") is not None:
                names.add(str(component["name"]))
    packages = sbom.get("packages", [])
    if isinstance(packages, list):
        for package in packages:
            if isinstance(package, Mapping) and package.get("name") is not None:
                names.add(str(package["name"]))
    return names


def _provenance_package_names(provenance: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(provenance, Mapping):
        return set()
    names: set[str] = set()
    subject = provenance.get("subject", [])
    if isinstance(subject, list):
        for item in subject:
            if isinstance(item, Mapping) and item.get("name") is not None:
                names.add(str(item["name"]))
    return names


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
