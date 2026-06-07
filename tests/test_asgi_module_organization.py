from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASGI_ROOT = ROOT / "pkgs" / "tigrcorn-asgi" / "src" / "tigrcorn_asgi"


def test_tigrcorn_asgi_python_files_stay_under_400_lines() -> None:
    oversized = []
    for path in ASGI_ROOT.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 400:
            oversized.append((len(lines), path.relative_to(ROOT).as_posix()))
    assert oversized == []


def test_asgi_send_public_imports_remain_compatible() -> None:
    from tigrcorn.asgi.send import HTTPResponseCollector as RootCollector
    from tigrcorn_asgi.send import (
        FileBodySegment,
        HTTPResponseCollector,
        HTTPResponseWriter,
        LifespanSend,
        MemoryBodySegment,
        iter_response_body_segments,
        materialize_response_body_segments,
        normalize_response_file_segments,
        normalize_response_pathsend_segment,
    )

    assert RootCollector is HTTPResponseCollector
    assert FileBodySegment("x").path == "x"
    assert MemoryBodySegment(b"x").data == b"x"
    assert callable(HTTPResponseWriter)
    assert callable(LifespanSend)
    assert callable(iter_response_body_segments)
    assert callable(materialize_response_body_segments)
    assert callable(normalize_response_file_segments)
    assert callable(normalize_response_pathsend_segment)


def test_asgi_send_responsibility_modules_are_isolated() -> None:
    assert hasattr(importlib.import_module("tigrcorn_asgi.send.segments"), "FileBodySegment")
    assert hasattr(importlib.import_module("tigrcorn_asgi.send.materialize"), "iter_response_body_segments")
    assert hasattr(importlib.import_module("tigrcorn_asgi.send.collector"), "HTTPResponseCollector")
    assert hasattr(importlib.import_module("tigrcorn_asgi.send.writer"), "HTTPResponseWriter")
    assert hasattr(importlib.import_module("tigrcorn_asgi.send.lifespan"), "LifespanSend")


def test_tigrcorn_asgi_does_not_import_runtime_server_or_transport_packages() -> None:
    banned_prefixes = ("tigrcorn_runtime.server", "tigrcorn_transports")
    offenders: list[tuple[str, str]] = []
    for path in ASGI_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes):
                        offenders.append((path.relative_to(ROOT).as_posix(), alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(banned_prefixes):
                    offenders.append((path.relative_to(ROOT).as_posix(), node.module))
    assert offenders == []
