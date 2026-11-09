from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "protocol.json",
    "runtime.json",
    "security.json",
    "performance.json",
    "interop.json",
)
OUTPUT_DIRECTORY_CONTRACT: dict[str, Any] = {
    "artifact_names": REQUIRED_ARTIFACTS,
    "manifest_name": "manifest.json",
    "signature_name": "manifest.sig",
    "root_name": "certification-artifacts",
}
NOISE_KEYS = frozenset(
    {
        "absolute_path",
        "clock",
        "created_at",
        "cwd",
        "duration_ms",
        "elapsed_ms",
        "generated_at",
        "hostname",
        "path",
        "pid",
        "timestamp",
        "wall_clock",
        "working_directory",
    }
)


class CertificationArtifactError(ValueError):
    """Raised when certification artifacts are not release eligible."""


@dataclass(frozen=True, slots=True)
class CertificationArtifact:
    name: str
    payload: dict[str, Any]
    digest: str
    canonical_json: str

    def as_manifest_entry(self) -> dict[str, str]:
        return {"digest": self.digest, "name": self.name}


@dataclass(frozen=True, slots=True)
class CertificationBundle:
    artifacts: dict[str, CertificationArtifact]
    manifest: dict[str, Any]
    signature: str | None = None
    output_directory: str = OUTPUT_DIRECTORY_CONTRACT["root_name"]
    files: dict[str, str] = field(default_factory=dict)

    def with_signature(self, signature: str) -> "CertificationBundle":
        files = dict(self.files)
        files[OUTPUT_DIRECTORY_CONTRACT["signature_name"]] = signature
        return CertificationBundle(
            artifacts=self.artifacts,
            manifest=self.manifest,
            signature=signature,
            output_directory=self.output_directory,
            files=files,
        )


def output_directory_contract() -> dict[str, Any]:
    return {
        "artifact_names": list(REQUIRED_ARTIFACTS),
        "manifest_name": OUTPUT_DIRECTORY_CONTRACT["manifest_name"],
        "signature_name": OUTPUT_DIRECTORY_CONTRACT["signature_name"],
        "root_name": OUTPUT_DIRECTORY_CONTRACT["root_name"],
    }


def canonical_json(data: Mapping[str, Any]) -> str:
    normalized = normalize_nondeterminism(data)
    return json.dumps(normalized, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def build_artifact(name: str, payload: Mapping[str, Any]) -> CertificationArtifact:
    if name not in REQUIRED_ARTIFACTS:
        raise CertificationArtifactError(f"unsupported certification artifact: {name}")
    canonical = canonical_json(payload)
    return CertificationArtifact(
        name=name,
        payload=json.loads(canonical),
        digest=_sha256(canonical),
        canonical_json=canonical,
    )


def build_manifest(artifacts: Mapping[str, CertificationArtifact]) -> dict[str, Any]:
    missing = [name for name in REQUIRED_ARTIFACTS if name not in artifacts]
    if missing:
        raise CertificationArtifactError(f"missing required certification artifacts: {', '.join(missing)}")
    entries = [artifacts[name].as_manifest_entry() for name in REQUIRED_ARTIFACTS]
    return {
        "artifacts": entries,
        "digest_algorithm": "sha256",
        "manifest_version": 1,
        "output_directory": output_directory_contract(),
    }


def build_bundle(sections: Mapping[str, Mapping[str, Any]], *, output_directory: str | Path | None = None) -> CertificationBundle:
    artifacts = {name: build_artifact(name, sections[name]) for name in REQUIRED_ARTIFACTS}
    manifest = build_manifest(artifacts)
    output_name = _stable_output_directory(output_directory)
    files = {name: artifacts[name].canonical_json for name in REQUIRED_ARTIFACTS}
    files[OUTPUT_DIRECTORY_CONTRACT["manifest_name"]] = canonical_json(manifest)
    return CertificationBundle(artifacts=artifacts, manifest=manifest, output_directory=output_name, files=files)


def write_bundle(bundle: CertificationBundle, output_directory: str | Path) -> list[Path]:
    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in sorted(bundle.files):
        path = root / name
        path.write_text(bundle.files[name], encoding="utf-8", newline="\n")
        written.append(path)
    return written


def write_certification_artifacts(
    sections: Mapping[str, Mapping[str, Any]],
    output_directory: str | Path,
    *,
    signing_key: str | bytes | None = None,
) -> CertificationBundle:
    bundle = build_bundle(sections, output_directory=output_directory)
    if signing_key is not None:
        bundle = bundle.with_signature(sign_manifest(bundle.manifest, key=signing_key))
    write_bundle(bundle, output_directory)
    return bundle


def sign_manifest(manifest: Mapping[str, Any], *, key: str | bytes) -> str:
    key_bytes = key.encode("utf-8") if isinstance(key, str) else key
    return hmac.new(key_bytes, canonical_json(manifest).encode("utf-8"), hashlib.sha256).hexdigest()


def verify_output_tree(
    output_directory: str | Path,
    *,
    key: str | bytes | None = None,
    require_signature: bool = True,
) -> dict[str, Any]:
    root = Path(output_directory)
    failures: list[str] = []
    checked_files: list[str] = []
    files: dict[str, str] = {}
    manifest: dict[str, Any] | None = None
    artifacts: dict[str, CertificationArtifact] = {}

    manifest_path = root / OUTPUT_DIRECTORY_CONTRACT["manifest_name"]
    checked_files.append(str(manifest_path))
    if not manifest_path.exists():
        failures.append(f"missing certification artifact manifest: {manifest_path}")
    else:
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8")
            files[OUTPUT_DIRECTORY_CONTRACT["manifest_name"]] = manifest_text
            manifest = json.loads(manifest_text)
            if manifest_text != canonical_json(manifest):
                failures.append("manifest.json is not canonical JSON")
        except Exception as exc:
            failures.append(f"manifest.json is not readable JSON: {exc}")

    signature_path = root / OUTPUT_DIRECTORY_CONTRACT["signature_name"]
    checked_files.append(str(signature_path))
    signature: str | None = None
    if signature_path.exists():
        signature = signature_path.read_text(encoding="utf-8").strip()
        files[OUTPUT_DIRECTORY_CONTRACT["signature_name"]] = signature
    elif require_signature:
        failures.append("missing manifest signature")

    for name in REQUIRED_ARTIFACTS:
        artifact_path = root / name
        checked_files.append(str(artifact_path))
        if not artifact_path.exists():
            failures.append(f"missing required certification artifact: {name}")
            continue
        try:
            artifact_text = artifact_path.read_text(encoding="utf-8")
            payload = json.loads(artifact_text)
            if artifact_text != canonical_json(payload):
                failures.append(f"{name} is not canonical JSON")
            files[name] = artifact_text
            artifacts[name] = CertificationArtifact(
                name=name,
                payload=json.loads(canonical_json(payload)),
                digest=_sha256(artifact_text),
                canonical_json=artifact_text,
            )
        except Exception as exc:
            failures.append(f"{name} is not readable JSON: {exc}")

    if manifest is not None:
        manifest_entries = manifest.get("artifacts")
        if not isinstance(manifest_entries, list):
            failures.append("manifest.json is missing artifacts list")
        else:
            manifest_by_name: dict[str, str] = {}
            for entry in manifest_entries:
                if not isinstance(entry, Mapping):
                    failures.append("manifest.json contains malformed artifact entry")
                    continue
                name = str(entry.get("name", ""))
                manifest_by_name[name] = str(entry.get("digest", ""))
            for name in REQUIRED_ARTIFACTS:
                if name not in manifest_by_name:
                    failures.append(f"manifest.json is missing entry for {name}")
                    continue
                if name in files and manifest_by_name[name] != _sha256(files[name]):
                    failures.append(f"{name} digest mismatch")
            unexpected = sorted(name for name in manifest_by_name if name not in REQUIRED_ARTIFACTS)
            if unexpected:
                failures.append(f"manifest.json contains unexpected artifact entries: {unexpected}")

        try:
            expected_manifest = build_manifest(artifacts)
            if manifest != expected_manifest:
                failures.append("manifest artifact digest mismatch")
        except CertificationArtifactError as exc:
            failures.append(str(exc))

        if signature is not None and key is not None:
            expected_signature = sign_manifest(manifest, key=key)
            if not hmac.compare_digest(signature, expected_signature):
                failures.append("manifest signature mismatch")

    return {
        "checked_files": checked_files,
        "failures": failures,
        "files": sorted(files),
        "release_eligible": not failures,
    }


def verify_release_evidence(bundle: CertificationBundle, *, key: str | bytes | None = None) -> dict[str, Any]:
    failures: list[str] = []
    if not bundle.signature:
        failures.append("missing manifest signature")
    elif key is not None:
        expected = sign_manifest(bundle.manifest, key=key)
        if not hmac.compare_digest(expected, bundle.signature):
            failures.append("manifest signature mismatch")

    try:
        expected_manifest = build_manifest(bundle.artifacts)
    except CertificationArtifactError as exc:
        failures.append(str(exc))
        expected_manifest = None

    if expected_manifest is not None and bundle.manifest != expected_manifest:
        failures.append("manifest artifact digest mismatch")

    for name, artifact in sorted(bundle.artifacts.items()):
        recomputed = _sha256(canonical_json(artifact.payload))
        if artifact.digest != recomputed:
            failures.append(f"{name} digest mismatch")
        if artifact.canonical_json != canonical_json(artifact.payload):
            failures.append(f"{name} canonical JSON mismatch")

    return {"failures": failures, "release_eligible": not failures}


def replay_diff(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    normalized_left = normalize_nondeterminism(left)
    normalized_right = normalize_nondeterminism(right)
    return {
        "left": normalized_left,
        "right": normalized_right,
        "equal": normalized_left == normalized_right,
    }


def normalize_nondeterminism(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if str(key) in NOISE_KEYS:
                continue
            normalized[str(key)] = normalize_nondeterminism(value[key])
        return normalized
    if isinstance(value, list | tuple):
        return [normalize_nondeterminism(item) for item in value]
    if isinstance(value, Path | PurePosixPath):
        return "<normalized-path>"
    return value


def reject_nondeterministic_fields(value: Mapping[str, Any]) -> None:
    paths = _find_noise_paths(value)
    if paths:
        raise CertificationArtifactError(f"nondeterministic fields are not release eligible: {', '.join(paths)}")


def _find_noise_paths(value: Any, prefix: str = "$") -> list[str]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if str(key) in NOISE_KEYS:
                paths.append(child_path)
            paths.extend(_find_noise_paths(child, child_path))
        return paths
    if isinstance(value, list | tuple):
        paths = []
        for index, child in enumerate(value):
            paths.extend(_find_noise_paths(child, f"{prefix}[{index}]"))
        return paths
    return []


def _stable_output_directory(output_directory: str | Path | None) -> str:
    if output_directory is None:
        return OUTPUT_DIRECTORY_CONTRACT["root_name"]
    return Path(output_directory).name


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
