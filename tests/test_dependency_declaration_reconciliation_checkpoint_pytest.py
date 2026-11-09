from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from tigrcorn.config.files import ConfigFileError, load_config_file
from tigrcorn.protocols.content_coding import encode_content

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_optional_install_paths() -> None:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = payload["project"]["optional-dependencies"]

    assert "config-yaml" in extras
    assert any(dep.startswith("PyYAML") for dep in extras["config-yaml"])

    assert "compression" in extras
    assert any(dep.startswith("brotli") for dep in extras["compression"])

    assert "runtime-uvloop" in extras
    assert any(dep.startswith("uvloop") for dep in extras["runtime-uvloop"])

    assert "runtime-trio" in extras
    assert any(dep.startswith("trio") for dep in extras["runtime-trio"])

    assert "full-featured" in extras
    full_featured = extras["full-featured"]
    assert any(dep.startswith("PyYAML") for dep in full_featured)
    assert any(dep.startswith("brotli") for dep in full_featured)
    assert any(dep.startswith("uvloop") for dep in full_featured)
    assert not any(dep.startswith("trio") for dep in full_featured)

    dev = extras["dev"]
    assert any(dep.startswith("pytest") for dep in dev)
    assert any(dep.startswith("PyYAML") for dep in dev)
    assert any(dep.startswith("brotli") for dep in dev)
    assert any(dep.startswith("uvloop") for dep in dev)


def test_docs_reference_declared_optional_surfaces() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    optional_doc = (ROOT / "docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md").read_text(encoding="utf-8")
    docs_readme = (ROOT / "docs/review/conformance/README.md").read_text(encoding="utf-8")
    pairing = (ROOT / "examples/PHASE4_PROTOCOL_PAIRING.md").read_text(encoding="utf-8")

    for token in ("config-yaml", "compression", "runtime-uvloop", "runtime-trio", "full-featured"):
        assert token in readme
        assert token in optional_doc
    assert "OPTIONAL_DEPENDENCY_SURFACE.md" in docs_readme
    assert "runtime `trio` is **not** part of the supported public runtime surface" in pairing
    assert "surfaced-but-not-yet-wired execution mode" not in pairing


def test_optional_dependency_error_hints_point_to_declared_extras() -> None:
    yaml_config = ROOT / "tests/fixtures_pkg/phase1_yaml_missing.yaml"
    yaml_config.write_text("app:\n  target: tests.fixtures_pkg.appmod:app\n", encoding="utf-8")
    try:
        with patch("tigrcorn.config.files.yaml", None):
            with pytest.raises(ConfigFileError) as ctx:
                load_config_file(yaml_config)
        assert "tigrcorn[config-yaml]" in str(ctx.value)
    finally:
        yaml_config.unlink(missing_ok=True)

    with patch("tigrcorn.protocols.content_coding.brotli", None):
        with pytest.raises(RuntimeError) as ctx:
            encode_content("br", b"payload")
    assert "tigrcorn[compression]" in str(ctx.value)

    bootstrap_source = (ROOT / "src/tigrcorn/server/bootstrap.py").read_text(encoding="utf-8")
    assert "tigrcorn[runtime-uvloop]" in bootstrap_source
