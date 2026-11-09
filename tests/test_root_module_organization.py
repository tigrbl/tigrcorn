from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIGRCORN_ROOT = ROOT / "src" / "tigrcorn"


def test_root_tigrcorn_python_files_stay_under_400_lines() -> None:
    oversized = []
    for path in TIGRCORN_ROOT.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 400:
            oversized.append((len(lines), path.relative_to(ROOT).as_posix()))
    assert oversized == []


def test_perf_runner_compat_public_imports_remain_compatible() -> None:
    from tigrcorn.compat.perf_runner import (
        PerfMatrix,
        PerfProfile,
        PerfProfileResult,
        PerfRunSummary,
        PerfRunnerError,
        load_performance_matrix,
        run_performance_matrix,
        validate_performance_artifacts,
    )
    from tigrcorn_certification.perf_runner import (
        PerfMatrix as CertificationPerfMatrix,
        PerfProfile as CertificationPerfProfile,
        PerfProfileResult as CertificationPerfProfileResult,
        PerfRunSummary as CertificationPerfRunSummary,
        PerfRunnerError as CertificationPerfRunnerError,
        load_performance_matrix as certification_load_performance_matrix,
        run_performance_matrix as certification_run_performance_matrix,
        validate_performance_artifacts as certification_validate_performance_artifacts,
    )

    assert PerfMatrix is CertificationPerfMatrix
    assert PerfProfile is CertificationPerfProfile
    assert PerfProfileResult is CertificationPerfProfileResult
    assert PerfRunSummary is CertificationPerfRunSummary
    assert PerfRunnerError is CertificationPerfRunnerError
    assert load_performance_matrix is certification_load_performance_matrix
    assert run_performance_matrix is certification_run_performance_matrix
    assert validate_performance_artifacts is certification_validate_performance_artifacts


def test_perf_runner_compat_resolves_to_certification_package() -> None:
    module = importlib.import_module("tigrcorn.compat.perf_runner")
    certification_module = importlib.import_module("tigrcorn_certification.perf_runner")

    assert module is certification_module


def test_root_compat_modules_remain_facades() -> None:
    offenders: list[tuple[str, str]] = []
    for path in (TIGRCORN_ROOT / "compat").glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                offenders.append((path.relative_to(ROOT).as_posix(), node.name))

    assert offenders == []


def test_root_package_does_not_own_transport_or_protocol_implementations() -> None:
    implementation_nodes: list[tuple[str, str]] = []
    facade_roots = {
        "asgi",
        "certification",
        "compat",
        "config",
        "contract",
        "flow",
        "http",
        "listeners",
        "observability",
        "protocols",
        "scheduler",
        "security",
        "server",
        "sessions",
        "streams",
        "transports",
        "utils",
        "webtransport",
        "workers",
    }
    allowed_facade_functions = {"__getattr__", "__dir__"}
    for root_name in facade_roots:
        for path in (TIGRCORN_ROOT / root_name).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if path.name == "__init__.py" and node.name in allowed_facade_functions:
                        continue
                    implementation_nodes.append((path.relative_to(ROOT).as_posix(), node.name))

    assert implementation_nodes == []
