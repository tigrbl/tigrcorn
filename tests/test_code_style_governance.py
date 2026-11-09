from __future__ import annotations

import ast
from pathlib import Path

from tools.style_governance import audit_repository


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_API = ROOT / "pkgs" / "tigrcorn-runtime" / "src" / "tigrcorn_runtime" / "api.py"


def _public_docstring(name: str) -> str:
    tree = ast.parse(PUBLIC_API.read_text(encoding="utf-8"), filename=str(PUBLIC_API))
    for node in tree.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return ast.get_docstring(node) or ""
    raise AssertionError(f"missing public API function {name}")


def test_code_style_governance_audit_passes() -> None:
    report = audit_repository(ROOT)

    assert report["passed"], report
    assert report["line_lengths"]["blocking_count"] == 0
    assert report["docstrings"]["malformed_section_count"] == 0
    assert report["docstrings"]["sectioned_docstrings"] > 0


def test_public_runtime_api_docstrings_use_spacy_sections() -> None:
    for name in ("serve", "serve_import_string", "run"):
        docstring = _public_docstring(name)
        assert "Args:" in docstring
        assert "Returns:" in docstring
    assert "Raises:" in _public_docstring("serve_import_string")
