from __future__ import annotations

import json

import pytest

from tigrcorn.certification.artifacts import (
    CertificationArtifact,
    CertificationArtifactError,
    build_bundle,
    canonical_json,
    output_directory_contract,
    reject_nondeterministic_fields,
    replay_diff,
    sign_manifest,
    verify_release_evidence,
    write_bundle,
)


def _sections() -> dict[str, dict[str, object]]:
    return {
        "protocol.json": {"http": ["h1", "h2", "h3"], "webtransport": {"enabled": True}},
        "runtime.json": {"listeners": [{"id": "listener-1", "transport": "tcp"}], "workers": 1},
        "security.json": {"tls": {"min": "1.3"}, "negative_corpus": ["replay", "spoof"]},
        "performance.json": {"benchmarks": [{"name": "steady-state", "p95_ms": 10}]},
        "interop.json": {"peers": ["reference-a"], "matrix": {"passed": True}},
    }


def _signed_bundle():
    bundle = build_bundle(_sections())
    return bundle.with_signature(sign_manifest(bundle.manifest, key="release-key"))


def test_cert_artifact_manifest_shape() -> None:
    bundle = build_bundle(_sections())

    assert bundle.manifest["manifest_version"] == 1
    assert bundle.manifest["digest_algorithm"] == "sha256"
    assert [item["name"] for item in bundle.manifest["artifacts"]] == [
        "protocol.json",
        "runtime.json",
        "security.json",
        "performance.json",
        "interop.json",
    ]
    assert all(len(item["digest"]) == 64 for item in bundle.manifest["artifacts"])


def test_cert_artifact_output_directory_contract(tmp_path) -> None:
    contract = output_directory_contract()
    bundle = build_bundle(_sections(), output_directory=tmp_path / "run-123" / "certification-artifacts")
    written = write_bundle(bundle, tmp_path / contract["root_name"])

    assert contract == {
        "artifact_names": [
            "protocol.json",
            "runtime.json",
            "security.json",
            "performance.json",
            "interop.json",
        ],
        "manifest_name": "manifest.json",
        "signature_name": "manifest.sig",
        "root_name": "certification-artifacts",
    }
    assert bundle.output_directory == "certification-artifacts"
    assert [path.name for path in written] == sorted([*contract["artifact_names"], "manifest.json"])


@pytest.mark.parametrize(
    ("artifact_name", "payload"),
    [
        ("protocol.json", {"z": 1, "a": {"protocol": "h3"}}),
        ("runtime.json", {"z": 1, "a": {"workers": 1}}),
        ("security.json", {"z": 1, "a": {"tls": "1.3"}}),
        ("performance.json", {"z": 1, "a": {"p95_ms": 10}}),
        ("interop.json", {"z": 1, "a": {"peer": "reference-a"}}),
    ],
)
def test_cert_artifact_section_json_deterministic(artifact_name: str, payload: dict[str, object]) -> None:
    first = build_bundle({**_sections(), artifact_name: payload}).artifacts[artifact_name]
    second = build_bundle({**_sections(), artifact_name: {"a": payload["a"], "z": 1}}).artifacts[artifact_name]

    assert first.canonical_json == second.canonical_json
    assert first.digest == second.digest
    assert json.loads(first.canonical_json) == {"a": payload["a"], "z": 1}


def test_cert_artifact_signature_required_for_release() -> None:
    unsigned = build_bundle(_sections())
    signed = unsigned.with_signature(sign_manifest(unsigned.manifest, key="release-key"))

    assert verify_release_evidence(unsigned, key="release-key") == {
        "failures": ["missing manifest signature"],
        "release_eligible": False,
    }
    assert verify_release_evidence(signed, key="release-key") == {"failures": [], "release_eligible": True}


def test_cert_artifact_replay_diff_noise_filter() -> None:
    left = {"status": "passed", "generated_at": "2026-06-07T10:00:00Z", "path": "C:/tmp/one"}
    right = {"status": "passed", "generated_at": "2026-06-07T11:00:00Z", "path": "D:/tmp/two"}

    assert replay_diff(left, right)["equal"] is True
    assert replay_diff(left, {**right, "status": "failed"})["equal"] is False


def test_cert_artifact_canonical_json_ordering() -> None:
    rendered = canonical_json({"z": 2, "a": {"d": 4, "b": 3}})

    assert rendered == '{"a":{"b":3,"d":4},"z":2}'


def test_cert_artifact_digest_mismatch_fails() -> None:
    signed = _signed_bundle()
    broken_artifact = CertificationArtifact(
        name="protocol.json",
        payload=signed.artifacts["protocol.json"].payload,
        digest="0" * 64,
        canonical_json=signed.artifacts["protocol.json"].canonical_json,
    )
    broken = signed.with_signature(signed.signature or "")
    artifacts = dict(broken.artifacts)
    artifacts["protocol.json"] = broken_artifact
    tampered = type(broken)(artifacts=artifacts, manifest=broken.manifest, signature=broken.signature, files=broken.files)

    result = verify_release_evidence(tampered, key="release-key")

    assert result["release_eligible"] is False
    assert "manifest artifact digest mismatch" in result["failures"]
    assert "protocol.json digest mismatch" in result["failures"]


def test_cert_artifact_clock_and_path_nondeterminism_filtered() -> None:
    sections = _sections()
    sections["runtime.json"] = {
        "listeners": [{"id": "listener-1"}],
        "generated_at": "2026-06-07T10:00:00Z",
        "working_directory": "E:/swarmauri_github/tigrcorn",
    }
    bundle = build_bundle(sections)

    assert json.loads(bundle.artifacts["runtime.json"].canonical_json) == {"listeners": [{"id": "listener-1"}]}
    with pytest.raises(CertificationArtifactError):
        reject_nondeterministic_fields(sections["runtime.json"])
