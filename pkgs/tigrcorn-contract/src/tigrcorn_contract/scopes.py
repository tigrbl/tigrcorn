from __future__ import annotations

from typing import Any

from tigrcorn_asgi.scopes.custom import build_custom_scope
from tigrcorn_core.errors import ProtocolError

SUPPORTED_SCOPE_TYPES = ("http", "websocket", "lifespan", "webtransport", "tigrcorn.stream", "tigrcorn.datagram")


def validate_scope(scope: dict[str, Any]) -> None:
    scope_type = scope.get("type")
    if scope_type not in SUPPORTED_SCOPE_TYPES:
        raise ProtocolError(f"unsupported contract scope type: {scope_type!r}")
    if scope_type == "webtransport":
        extensions = scope.get("extensions", {})
        if "h3" not in extensions or "quic" not in extensions:
            raise ProtocolError("webtransport scope requires h3 and quic extension metadata")


def contract_scope(scope_type: str, **fields: Any) -> dict[str, Any]:
    scope = build_custom_scope(scope_type, **fields)
    validate_scope(scope)
    return scope
