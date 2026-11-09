from __future__ import annotations

import json
from pathlib import Path

import pytest

from tigrcorn import capabilities
from tigrcorn.cli import main as cli_main
from tigrcorn_certification.artifacts import canonical_json


def test_certify_static_dispatches_to_certification_package(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    mount = tmp_path / "public"
    output = tmp_path / "artifacts"
    mount.mkdir()
    (mount / "asset.txt").write_text("hello", encoding="utf-8")

    rc = cli_main(
        [
            "certify",
            "static",
            "--mount",
            str(mount),
            "--profile",
            "static-origin",
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["passed"] is True
    assert payload["profile"] == "static-origin"

    static_path = output / "static.json"
    manifest_path = output / "manifest.json"
    assert static_path.exists()
    assert manifest_path.exists()
    static_payload = json.loads(static_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert static_path.read_text(encoding="utf-8") == canonical_json(static_payload)
    assert manifest_path.read_text(encoding="utf-8") == canonical_json(manifest_payload)
    assert static_payload["certification"]["certification_state"] == "certified"
    assert manifest_payload["certification"] == "static"


def test_certify_unknown_surface_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["certify", "unknown"])

    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "unknown certification surface: unknown" in captured.err


def test_certify_static_fails_closed_when_capability_gate_rejects(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount = tmp_path / "public"
    mount.mkdir()

    def reject_static(required: list[str], *, profile: str = "default") -> None:
        raise capabilities.UnsupportedCapabilityError(
            f"capability is not enabled for profile {profile!r}: {required[0]}"
        )

    monkeypatch.setattr(capabilities, "require_supported", reject_static)
    rc = cli_main(
        [
            "certify",
            "static",
            "--mount",
            str(mount),
            "--profile",
            "default",
            "--output",
            str(tmp_path / "artifacts"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "delivery.static" in captured.err
