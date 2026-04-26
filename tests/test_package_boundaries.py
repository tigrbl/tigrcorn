from __future__ import annotations

import ast
import importlib
import tomllib
from pathlib import Path

from tools.package_boundaries import PACKAGE_BOUNDARIES, PACKAGE_BY_DISTRIBUTION, workspace_distributions


ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_workspace_declares_all_target_packages() -> None:
    root_pyproject = _load_pyproject(ROOT / "pyproject.toml")
    members = root_pyproject["tool"]["uv"]["workspace"]["members"]

    assert members == ["pkgs/*"]
    for distribution in workspace_distributions():
        package_root = ROOT / "pkgs" / distribution
        assert (package_root / "pyproject.toml").is_file(), distribution
        assert (package_root / "README.md").is_file(), distribution


def test_package_dependency_dag_is_forward_only() -> None:
    for boundary in PACKAGE_BOUNDARIES:
        for dependency in boundary.depends_on:
            if dependency not in PACKAGE_BY_DISTRIBUTION:
                continue
            dependency_boundary = PACKAGE_BY_DISTRIBUTION[dependency]
            assert dependency_boundary.layer < boundary.layer, (boundary.distribution, dependency)


def test_package_pyprojects_match_boundary_manifest() -> None:
    for boundary in PACKAGE_BOUNDARIES:
        pyproject = _load_pyproject(ROOT / "pkgs" / boundary.distribution / "pyproject.toml")
        project = pyproject["project"]
        assert project["name"] == boundary.distribution
        assert project["version"] == "0.3.9"
        declared_dependencies = set(project.get("dependencies", []))
        for dependency in boundary.depends_on:
            if dependency.startswith("tigrcorn-"):
                assert f"{dependency}==0.3.9" in declared_dependencies
            else:
                assert any(item.startswith(dependency) for item in declared_dependencies)
        package_file = ROOT / "pkgs" / boundary.distribution / "src" / boundary.import_name / "__init__.py"
        assert package_file.is_file(), boundary.import_name
        assert (package_file.parent / "py.typed").is_file(), boundary.import_name


def test_extracted_core_is_importable_and_compat_shims_preserve_old_surface() -> None:
    from tigrcorn.constants import H2_PREFACE as shim_preface
    from tigrcorn.errors import ProtocolError as ShimProtocolError
    from tigrcorn.types import Scope as ShimScope
    from tigrcorn_core.constants import H2_PREFACE
    from tigrcorn_core.errors import ProtocolError
    from tigrcorn_core.types import Scope

    assert shim_preface == H2_PREFACE
    assert ShimProtocolError is ProtocolError
    assert ShimScope is Scope


def test_scaffold_import_names_are_available() -> None:
    for boundary in PACKAGE_BOUNDARIES:
        module = importlib.import_module(boundary.import_name)
        assert getattr(module, "PACKAGE_BOUNDARY", "core") in {boundary.distribution.removeprefix("tigrcorn-"), "core"}


def test_core_package_has_no_inward_tigrcorn_imports() -> None:
    core_root = ROOT / "pkgs" / "tigrcorn-core" / "src" / "tigrcorn_core"
    forbidden_prefixes = ("tigrcorn.", "tigrcorn_", "tigrcorn-")
    for path in core_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert not name.startswith(forbidden_prefixes), (path, name)
