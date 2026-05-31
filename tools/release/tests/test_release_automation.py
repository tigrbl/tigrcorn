from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.release import release_automation
from tools.release.release_automation import Version, build_plan


def test_python_patch_bump_targets_dev_release() -> None:
    assert str(Version.parse("0.3.15").bump("patch")) == "0.3.16.dev1"
    assert str(Version.parse("0.3.16.dev1").bump("patch")) == "0.3.16.dev2"


def test_python_minor_bump_targets_dev_release() -> None:
    assert str(Version.parse("0.3.15").bump("minor")) == "0.4.0.dev1"


def test_python_finalize_converts_dev_to_release() -> None:
    assert str(Version.parse("0.3.16.dev1").bump("finalize")) == "0.3.16"
    assert str(Version.parse("0.3.16").bump("finalize")) == "0.3.16"


def test_npm_uses_semver_prerelease_syntax() -> None:
    assert str(Version.parse("0.1.6", npm=True).bump("patch")) == "0.1.7-dev.1"
    assert str(Version.parse("0.1.7-dev.1", npm=True).bump("finalize")) == "0.1.7"


def test_release_plan_supports_all_packages() -> None:
    plan = build_plan("patch", write_changes=False, packages="all")
    names = {release["name"] for release in plan["github_releases"]}

    assert "tigrcorn" in names
    assert "tigrcorn-core" in names
    assert "@tigrcorn/wt-peer-probes" in names
    assert plan["prerelease"] is True
    assert any(release["tag"].startswith("tigrcorn==0.3.16.dev") for release in plan["github_releases"])


def test_release_plan_supports_probe_selection() -> None:
    plan = build_plan("minor", write_changes=False, packages="probes")

    assert plan["python"] == []
    assert [release["name"] for release in plan["npm"]] == ["@tigrcorn/wt-peer-probes"]
    assert [release["version"] for release in plan["npm"]] == ["0.2.0-dev.1"]


def test_release_plan_rejects_unknown_selection() -> None:
    with pytest.raises(ValueError, match="unknown package selection"):
        build_plan("patch", write_changes=False, packages="does-not-exist")


def test_release_notes_filename_stays_within_governance_limit() -> None:
    assert release_automation.release_notes_filename("0.3.15") == "RELEASE_NOTES_0.3.15.md"
    assert release_automation.release_notes_filename("0.3.16.dev1") == "REL_0.3.16.dev1.md"
    assert len(release_automation.release_notes_filename("0.3.16.dev1")) <= 24


def test_create_github_tags_pushes_tags_without_creating_releases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = tmp_path / "release-plan.json"
    summary.write_text(
        json.dumps(
            {
                "semver": "patch",
                "prerelease": False,
                "github_releases": [
                    {
                        "name": "tigrcorn",
                        "kind": "pypi",
                        "path": "pyproject.toml",
                        "version": "0.3.16.dev1",
                        "tag": "tigrcorn==0.3.16.dev1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    class _Completed:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode

    def fake_subprocess_run(args: list[str], **kwargs) -> _Completed:
        if args[:2] == ["git", "rev-parse"]:
            return _Completed(1)
        if args[:3] == ["gh", "release", "view"]:
            return _Completed(1)
        return _Completed(0)

    monkeypatch.setattr(release_automation, "run", lambda args, **kwargs: calls.append(args))
    monkeypatch.setattr(release_automation.subprocess, "run", fake_subprocess_run)

    release_automation.create_github_tags(summary)

    assert ["git", "tag", "-a", "tigrcorn==0.3.16.dev1", "-m", "tigrcorn==0.3.16.dev1"] in calls
    assert ["git", "push", "origin", "tigrcorn==0.3.16.dev1"] in calls
    assert not [call for call in calls if call[:3] == ["gh", "release", "create"]]
