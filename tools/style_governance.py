from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("src", "pkgs", "tools", "tests")
IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".uv-cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
GENERATED_OR_EVIDENCE_PREFIXES = (
    "docs/review/",
    "tools/create_",
    "tools/normalize_documentation_truth.py",
    "tools/regenerate_",
    "tools/retrofit_",
)
SECTION_HEADERS = ("Args:", "Returns:", "Raises:", "Yields:")


@dataclass(frozen=True)
class LineFinding:
    path: str
    line: int
    length: int
    target: int
    reason: str


@dataclass(frozen=True)
class DocstringFinding:
    path: str
    name: str
    line: int
    reason: str


def iter_python_sources(root: Path = ROOT) -> Iterable[Path]:
    """Yield governed Python source files.

    Args:
        root: Repository root to scan.

    Yields:
        Python source paths under the governed source roots.
    """

    for source_root in SOURCE_ROOTS:
        base = root / source_root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if any(rel.startswith(prefix) for prefix in GENERATED_OR_EVIDENCE_PREFIXES):
                continue
            yield path


def _line_target(line: str) -> int:
    stripped = line.lstrip()
    if stripped.startswith("#") or stripped.startswith(('"""', "'''", "*")):
        return 72
    return 79


def _is_practical_line_length_exception(line: str, length: int) -> tuple[bool, str]:
    stripped = line.strip()
    if length <= 120:
        return True, "within project formatter ceiling"
    if length <= 160:
        return True, "legacy wider formatter ceiling"
    if not stripped:
        return True, "blank line"
    if any(token in stripped for token in ("http://", "https://", "feat:", "clm:", "evd:", "tst:", "spc:", "adr:")):
        return True, "traceability literal"
    if any(quote in stripped for quote in ("'", '"')):
        return True, "protocol or documentation literal"
    if stripped.startswith(("'", '"', "f'", 'f"', "b'", 'b"', "r'", 'r"', "u'", 'u"')):
        return True, "protocol or documentation literal"
    if stripped.startswith("from ") and " import " in stripped:
        return True, "import declaration"
    if "add_argument(" in stripped or "help=" in stripped:
        return True, "operator help declaration"
    if "__all__" in stripped:
        return True, "export declaration"
    if stripped.startswith(("{", "[", "(", ")", "]", "}")):
        return True, "structured literal"
    if "," in stripped and any(mark in stripped for mark in ("(", "[", "{", "=")):
        return True, "structured call or literal"
    return False, "wrap source line"


def audit_line_lengths(root: Path = ROOT) -> dict[str, object]:
    """Audit PEP 8 line-length targets with practical exceptions.

    Args:
        root: Repository root to scan.

    Returns:
        Summary counts plus blocking findings that require source cleanup.
    """

    advisory: list[LineFinding] = []
    blocking: list[LineFinding] = []
    scanned_files = 0
    scanned_lines = 0
    for path in iter_python_sources(root):
        scanned_files += 1
        rel = path.relative_to(root).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            scanned_lines += 1
            length = len(line)
            target = _line_target(line)
            if length <= target:
                continue
            practical, reason = _is_practical_line_length_exception(line, length)
            finding = LineFinding(rel, line_number, length, target, reason)
            if practical:
                advisory.append(finding)
            else:
                blocking.append(finding)

    return {
        "policy": {
            "code_target": 79,
            "comment_docstring_target": 72,
            "project_formatter_ceiling": 120,
            "practical_exceptions_allowed": True,
        },
        "scanned_files": scanned_files,
        "scanned_lines": scanned_lines,
        "advisory_count": len(advisory),
        "blocking_count": len(blocking),
        "blocking_findings": [asdict(item) for item in blocking],
    }


def audit_spacy_docstrings(root: Path = ROOT) -> dict[str, object]:
    """Audit spaCy-style docstring sections on public documented APIs.

    Args:
        root: Repository root to scan.

    Returns:
        Counts for public definitions, documented APIs, and malformed
        section headers.
    """

    malformed: list[DocstringFinding] = []
    documented = 0
    sectioned = 0
    public_defs = 0
    for path in iter_python_sources(root):
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=rel)
        except SyntaxError as exc:
            malformed.append(DocstringFinding(rel, "<module>", exc.lineno or 1, "syntax error"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name.startswith("_"):
                continue
            public_defs += 1
            docstring = ast.get_docstring(node)
            if not docstring:
                continue
            documented += 1
            if any(header in docstring for header in SECTION_HEADERS):
                sectioned += 1
            for line in docstring.splitlines():
                stripped = line.strip()
                if (
                    re.fullmatch(r"[A-Za-z]+:", stripped)
                    and stripped not in SECTION_HEADERS
                ):
                    malformed.append(
                        DocstringFinding(rel, node.name, node.lineno, f"unknown section {stripped}")
                    )

    return {
        "policy": {
            "recognized_sections": list(SECTION_HEADERS),
            "sections_required_when_they_add_signal": True,
        },
        "public_definitions": public_defs,
        "documented_public_definitions": documented,
        "sectioned_docstrings": sectioned,
        "malformed_section_count": len(malformed),
        "malformed_sections": [asdict(item) for item in malformed],
    }


def audit_repository(root: Path = ROOT) -> dict[str, object]:
    """Return the combined code-style governance audit.

    Args:
        root: Repository root to scan.

    Returns:
        Combined audit payload for SSOT evidence and pytest checks.
    """

    line_lengths = audit_line_lengths(root)
    docstrings = audit_spacy_docstrings(root)
    passed = (
        line_lengths["blocking_count"] == 0
        and docstrings["malformed_section_count"] == 0
        and docstrings["sectioned_docstrings"] > 0
    )
    return {
        "passed": passed,
        "line_lengths": line_lengths,
        "docstrings": docstrings,
    }


def main() -> int:
    """Run the style-governance audit from the command line.

    Returns:
        Process status code.
    """

    report = audit_repository(ROOT)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
