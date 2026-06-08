from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_ROOTS = (ROOT / "tools", ROOT / ".github" / "workflows", ROOT / "tests")
REMOVED_RELEASE_LABEL = "pha" + "se9"


def _active_text_files() -> list[Path]:
    suffixes = {".py", ".yml", ".yaml", ".md", ".json", ".txt"}
    files: list[Path] = []
    for root in ACTIVE_ROOTS:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in suffixes:
                files.append(path)
    return files


def test_tools_python_files_stay_under_400_lines() -> None:
    oversized = []
    for path in (ROOT / "tools").rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 400:
            oversized.append((len(lines), path.relative_to(ROOT).as_posix()))

    assert oversized == []


def test_active_release_surfaces_use_semantic_names() -> None:
    offenders = []
    for path in _active_text_files():
        text = path.read_text(encoding="utf-8")
        if REMOVED_RELEASE_LABEL in text.lower() or REMOVED_RELEASE_LABEL in path.as_posix().lower():
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_release_checkpoint_entrypoints_are_thin_wrappers() -> None:
    wrappers = [
        ROOT / "tools" / "create_release_assembly_checkpoint.py",
        ROOT / "tools" / "create_release_promotion_checkpoint.py",
        ROOT / "tools" / "create_rfc7692_independent_closure_checkpoint.py",
        ROOT / "tools" / "create_ocsp_certification_checkpoint.py",
    ]

    for path in wrappers:
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 20
        assert "tools.release.checkpoints" in text


def test_certification_workflow_uses_current_wrapper_and_checkpoint() -> None:
    workflow = (ROOT / ".github" / "workflows" / "certification-release.yml").read_text(encoding="utf-8")
    wrapper = (ROOT / "tools" / "run_certification_release_workflow.py").read_text(encoding="utf-8")

    assert "tools/run_certification_release_workflow.py" in workflow
    assert "tools/create_release_assembly_checkpoint.py" in workflow
    assert "tools/create_release_assembly_checkpoint.py" in wrapper
