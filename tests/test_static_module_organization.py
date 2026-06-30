from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "pkgs" / "tigrcorn-static" / "src" / "tigrcorn_static"


def test_tigrcorn_static_python_files_stay_under_400_lines() -> None:
    oversized = []
    for path in STATIC_ROOT.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 400:
            oversized.append((len(lines), path.relative_to(ROOT).as_posix()))
    assert oversized == []


def test_static_public_imports_remain_compatible() -> None:
    from tigrcorn.static import StaticFilesApp as RootStaticFilesApp
    from tigrcorn.static import mount_static_app as root_mount_static_app
    from tigrcorn_static.static import StaticFilesApp, mount_static_app, validate_static_path

    assert RootStaticFilesApp is StaticFilesApp
    assert root_mount_static_app is mount_static_app
    assert callable(validate_static_path)


def test_static_responsibility_modules_are_isolated() -> None:
    security = importlib.import_module("tigrcorn_static.static.security")
    mounting = importlib.import_module("tigrcorn_static.static.mounting")
    responses = importlib.import_module("tigrcorn_static.static.responses")

    assert hasattr(security, "certify_static_delivery_security")
    assert hasattr(mounting, "mount_static_app")
    assert hasattr(responses, "StaticResponseMixin")


def test_tigrcorn_static_does_not_import_runtime_transport_packages() -> None:
    banned_prefixes = (
        "tigrcorn_runtime",
        "tigrcorn_transports",
    )
    offenders: list[tuple[str, str]] = []
    for path in STATIC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module.startswith(banned_prefixes):
                        offenders.append((path.relative_to(ROOT).as_posix(), module))
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                if module.startswith(banned_prefixes):
                    offenders.append((path.relative_to(ROOT).as_posix(), module))
    assert offenders == []


def test_static_root_facade_exports_documented_surface() -> None:
    static = importlib.import_module("tigrcorn_static.static")

    expected = {
        "StaticFilesApp",
        "StaticSecurityCertificationError",
        "StaticSecurityPolicy",
        "build_static_certification_evidence",
        "certify_static_delivery_security",
        "mount_static_app",
        "normalize_static_route",
        "static_alt_svc_headers",
        "static_cache_headers",
        "static_delivery_certification_artifact",
        "static_security_policy",
        "validate_static_content_length",
        "validate_static_early_hints",
        "validate_static_path",
        "validate_static_range_amplification",
        "validate_static_range_request",
        "validate_static_resolved_path",
        "validate_static_sidecar_pair",
    }
    assert set(static.__all__) == expected
