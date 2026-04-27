from __future__ import annotations

from typing import Any

from tigrcorn_asgi.scopes.custom import build_custom_scope
from tigrcorn_core.errors import ProtocolError

SUPPORTED_SCOPE_TYPES = ("http", "websocket", "lifespan", "webtransport", "tigrcorn.stream", "tigrcorn.datagram")
_PATH_SCOPE_TYPES = {"http", "websocket", "webtransport", "tigrcorn.stream"}


def validate_scope(scope: dict[str, Any]) -> None:
    scope_type = scope.get("type")
    if scope_type not in SUPPORTED_SCOPE_TYPES:
        raise ProtocolError(f"unsupported contract scope type: {scope_type!r}")
    if scope_type in _PATH_SCOPE_TYPES and not isinstance(scope.get("path", "/"), str):
        raise ProtocolError(f"{scope_type} scope path must be a string")
    if scope_type == "http" and scope.get("method") is not None and not isinstance(scope["method"], str):
        raise ProtocolError("http scope method must be a string")
    if scope_type == "websocket" and scope.get("subprotocols") is not None and not isinstance(scope["subprotocols"], list):
        raise ProtocolError("websocket scope subprotocols must be a list")
    if scope_type == "lifespan" and scope.get("state") is not None and not isinstance(scope["state"], dict):
        raise ProtocolError("lifespan scope state must be a mapping")
    if scope_type == "webtransport":
        extensions = scope.get("extensions", {})
        if "h3" not in extensions or "quic" not in extensions:
            raise ProtocolError("webtransport scope requires h3 and quic extension metadata")
    if scope_type == "tigrcorn.datagram" and "datagram_id" in scope and not scope["datagram_id"]:
        raise ProtocolError("datagram scope datagram_id must not be empty")


def contract_scope(scope_type: str, **fields: Any) -> dict[str, Any]:
    scope = build_custom_scope(scope_type, **fields)
    validate_scope(scope)
    return scope
