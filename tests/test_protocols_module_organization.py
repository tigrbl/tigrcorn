from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS_ROOT = ROOT / "pkgs" / "tigrcorn-protocols" / "src" / "tigrcorn_protocols"


def test_tigrcorn_protocols_python_files_stay_under_400_lines() -> None:
    oversized = []
    for path in PROTOCOLS_ROOT.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 400:
            oversized.append((len(lines), path.relative_to(ROOT).as_posix()))
    assert oversized == []


def test_http1_parser_public_imports_remain_compatible() -> None:
    from tigrcorn.protocols.http1.parser import ParsedRequest as RootParsedRequest
    from tigrcorn.protocols.http1.parser import read_http11_request as root_read_request
    from tigrcorn.protocols.http1.parser import read_http11_request_head as root_read_head
    from tigrcorn_protocols.http1.parser import (
        ParsedRequest,
        ParsedRequestHead,
        _validate_header_name,
        _validate_header_value,
        http11_request_head_error_matrix,
        read_http11_request,
        read_http11_request_head,
    )

    assert RootParsedRequest is ParsedRequest
    assert root_read_request is read_http11_request
    assert root_read_head is read_http11_request_head
    assert callable(ParsedRequestHead)
    assert callable(_validate_header_name)
    assert callable(_validate_header_value)
    assert callable(http11_request_head_error_matrix)


def test_websocket_handler_public_imports_remain_compatible() -> None:
    from tigrcorn.protocols.websocket.handler import WebSocketConnectionHandler as RootHandler
    from tigrcorn.protocols.websocket.handler import _WSAppSend as RootAppSend
    from tigrcorn_protocols.websocket.handler import WebSocketConnectionHandler, _WSAppSend

    assert RootHandler is WebSocketConnectionHandler
    assert RootAppSend is _WSAppSend


def test_client_session_coverage_public_imports_remain_compatible() -> None:
    from tigrcorn_protocols.client_session_coverage import (
        ClientSessionRobustnessHarness,
        ClientSessionTopologyHarness,
        ClientTopology,
        ProtocolCarrier,
        SessionScope,
        build_matrix_row,
        bounded_interleaved_pair,
        classify_default_session_scope,
        sequential_pair,
        validate_matrix_row,
    )

    assert classify_default_session_scope(ProtocolCarrier.HTTP1) is SessionScope.REQUEST_SCOPED
    assert callable(ClientSessionRobustnessHarness)
    assert callable(ClientSessionTopologyHarness)
    assert callable(build_matrix_row)
    assert callable(bounded_interleaved_pair)
    assert callable(sequential_pair)
    assert callable(validate_matrix_row)
    assert ClientTopology.SEQUENTIAL_CLIENTS.value == "sequential_clients"


def test_transport_adapter_imports_remain_isolated_to_http3_handler() -> None:
    banned_prefixes = ("tigrcorn_transports", "tigrcorn_runtime.server")
    allowed_transport_adapter_files = {
        "pkgs/tigrcorn-protocols/src/tigrcorn_protocols/http3/handler/imports.py",
        "pkgs/tigrcorn-protocols/src/tigrcorn_protocols/http3/handler/session.py",
        "pkgs/tigrcorn-protocols/src/tigrcorn_protocols/http3/handler/webtransport.py",
    }
    offenders: list[tuple[str, str]] = []
    for path in PROTOCOLS_ROOT.rglob("*.py"):
        relative_path = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes) and relative_path not in allowed_transport_adapter_files:
                        offenders.append((relative_path, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(banned_prefixes) and relative_path not in allowed_transport_adapter_files:
                    offenders.append((relative_path, node.module))
    assert offenders == []


def test_protocol_responsibility_modules_are_isolated() -> None:
    assert hasattr(importlib.import_module("tigrcorn_protocols.client_session_coverage.models"), "ProtocolCarrier")
    assert hasattr(importlib.import_module("tigrcorn_protocols.client_session_coverage.robustness"), "ClientSessionRobustnessHarness")
    assert hasattr(importlib.import_module("tigrcorn_protocols.http1.parser.head"), "read_http11_request_head")
    assert hasattr(importlib.import_module("tigrcorn_protocols.http1.parser.body"), "_read_chunked_body")
    assert hasattr(importlib.import_module("tigrcorn_protocols.websocket.handler.app_send"), "_WSAppSend")
    assert hasattr(importlib.import_module("tigrcorn_protocols.websocket.handler.core"), "WebSocketConnectionHandler")
