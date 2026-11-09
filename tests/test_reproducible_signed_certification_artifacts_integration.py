from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tigrcorn.certification.artifacts import (
    REQUIRED_ARTIFACTS,
    write_certification_artifacts,
)
from tigrcorn.certification.release_gates import evaluate_release_gates


SIGNING_KEY = "release-artifact-key"


def _sections() -> dict[str, dict[str, object]]:
    return {
        "protocol.json": {"http": ["h1", "h2", "h3"], "webtransport": {"enabled": True}},
        "runtime.json": {"listeners": [{"id": "listener-1", "transport": "tcp"}], "workers": 1},
        "security.json": {"negative_corpus": ["replay", "spoof"], "tls": {"min": "1.3"}},
        "performance.json": {"benchmarks": [{"name": "steady-state", "p95_ms": 10}]},
        "interop.json": {"matrix": {"passed": True}, "peers": ["reference-a"]},
    }


def _write_boundary(root: Path, artifact_root: str = "certification-artifacts") -> Path:
    boundary_path = root / "boundary.json"
    boundary_path.write_text(
        json.dumps(
            {
                "certification_artifacts": {
                    "artifact_root": artifact_root,
                    "manifest_signature_key": SIGNING_KEY,
                },
                "gates": {"require_signed_certification_artifacts": True},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return boundary_path


def _evaluate(root: Path, boundary_path: Path):
    return evaluate_release_gates(root, boundary_path=boundary_path)


def test_certification_artifact_writer_creates_required_output_tree(tmp_path: Path) -> None:
    artifact_root = tmp_path / "certification-artifacts"
    bundle = write_certification_artifacts(_sections(), artifact_root, signing_key=SIGNING_KEY)

    expected = {*REQUIRED_ARTIFACTS, "manifest.json", "manifest.sig"}

    assert bundle.signature
    assert {path.name for path in artifact_root.iterdir()} == expected
    assert all((artifact_root / name).is_file() for name in expected)


def test_release_artifact_manifest_contains_actual_generated_files(tmp_path: Path) -> None:
    artifact_root = tmp_path / "certification-artifacts"
    write_certification_artifacts(_sections(), artifact_root, signing_key=SIGNING_KEY)

    manifest = json.loads((artifact_root / "manifest.json").read_text(encoding="utf-8"))
    manifest_digests = {entry["name"]: entry["digest"] for entry in manifest["artifacts"]}

    assert set(manifest_digests) == set(REQUIRED_ARTIFACTS)
    for name in REQUIRED_ARTIFACTS:
        actual_digest = hashlib.sha256((artifact_root / name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        assert manifest_digests[name] == actual_digest


def test_release_gate_requires_manifest_signature(tmp_path: Path) -> None:
    artifact_root = tmp_path / "certification-artifacts"
    boundary = _write_boundary(tmp_path)
    write_certification_artifacts(_sections(), artifact_root)

    report = _evaluate(tmp_path, boundary)

    assert report.passed is False
    assert "certification artifacts: missing manifest signature" in report.failures
    assert report.artifact_status["certification_artifacts"]["release_eligible"] is False


def test_replay_generated_artifacts_are_byte_stable(tmp_path: Path) -> None:
    first_root = tmp_path / "first" / "certification-artifacts"
    second_root = tmp_path / "second" / "certification-artifacts"

    write_certification_artifacts(_sections(), first_root, signing_key=SIGNING_KEY)
    write_certification_artifacts(_sections(), second_root, signing_key=SIGNING_KEY)

    for name in (*REQUIRED_ARTIFACTS, "manifest.json", "manifest.sig"):
        assert (first_root / name).read_bytes() == (second_root / name).read_bytes()


def test_digest_mismatch_in_output_tree_blocks_release_gate(tmp_path: Path) -> None:
    artifact_root = tmp_path / "certification-artifacts"
    boundary = _write_boundary(tmp_path)
    write_certification_artifacts(_sections(), artifact_root, signing_key=SIGNING_KEY)
    protocol = json.loads((artifact_root / "protocol.json").read_text(encoding="utf-8"))
    protocol["tampered"] = True
    (artifact_root / "protocol.json").write_text(json.dumps(protocol, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    report = _evaluate(tmp_path, boundary)

    assert report.passed is False
    assert "certification artifacts: protocol.json digest mismatch" in report.failures
    assert "certification artifacts: manifest artifact digest mismatch" in report.failures
    assert report.artifact_status["certification_artifacts"]["release_eligible"] is False
