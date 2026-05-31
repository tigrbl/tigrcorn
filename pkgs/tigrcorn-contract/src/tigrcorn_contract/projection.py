from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tigrcorn_core.errors import ProtocolError

try:  # pragma: no cover - exercised when the newer contract package is installed.
    from tigr_asgi_contract import classify_event as _contract_classify_event
    from tigr_asgi_contract import validate_event_classification as _contract_validate_event_classification
    from tigr_asgi_contract import validate_event_payload as _contract_validate_event_payload
except Exception:  # pragma: no cover - current published 0.3.2 lacks these APIs.
    _contract_classify_event = None
    _contract_validate_event_classification = None
    _contract_validate_event_payload = None


_FRAMINGS = {"json", "jsonrpc", "ndjson", "sse", "text", "bytes", "binary"}
_BINDING_ALIASES = {
    "http.rest": "rest",
    "https.rest": "rest",
    "rest": "rest",
    "http.jsonrpc": "jsonrpc",
    "https.jsonrpc": "jsonrpc",
    "jsonrpc": "jsonrpc",
    "http.stream": "http.stream",
    "https.stream": "http.stream",
    "http.sse": "sse",
    "https.sse": "sse",
    "sse": "sse",
    "ws": "websocket",
    "wss": "websocket",
    "websocket": "websocket",
    "webtransport": "webtransport",
    "lifespan": "lifespan",
}


@dataclass(frozen=True, slots=True)
class ScopeProjection:
    scope_type: str
    binding: str
    alpn: str | None = None
    secure: bool = False
    framing: str | None = None


@dataclass(frozen=True, slots=True)
class EventProjection:
    event: str
    channel: str
    scope_type: str
    binding: str
    family: str
    exchange: str
    direction: str
    allowed_framings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ClassificationRow:
    event: str
    channel: str
    scope_type: str
    binding: str
    family: str
    exchange: str
    direction: str
    allowed_framings: tuple[str, ...] = ()
    required_payload_fields: tuple[str, ...] = ()
    stream_direction: str | None = None
    capability_gates: tuple[str, ...] = ()


_ROWS = (
    _ClassificationRow("http.request", "receive", "http", "rest", "request", "unary", "client_to_server", ("json", "text", "bytes", "binary")),
    _ClassificationRow("http.request", "receive", "http", "jsonrpc", "request", "unary", "client_to_server", ("jsonrpc",)),
    _ClassificationRow("http.request", "receive", "http", "http.stream", "stream", "client_stream", "client_to_server", ("json", "ndjson", "text", "bytes", "binary")),
    _ClassificationRow("http.disconnect", "receive", "http", "rest", "request", "unary", "client_to_server"),
    _ClassificationRow("http.response.start", "send", "http", "rest", "request", "unary", "server_to_client"),
    _ClassificationRow("http.response.start", "send", "http", "jsonrpc", "request", "unary", "server_to_client"),
    _ClassificationRow("http.response.body", "send", "http", "rest", "request", "unary", "server_to_client", ("json", "text", "bytes", "binary")),
    _ClassificationRow("http.response.body", "send", "http", "jsonrpc", "request", "unary", "server_to_client", ("jsonrpc",)),
    _ClassificationRow("http.response.body", "send", "http", "http.stream", "stream", "server_stream", "server_to_client", ("json", "ndjson", "text", "bytes", "binary")),
    _ClassificationRow("http.response.body", "send", "http", "sse", "stream", "server_stream", "server_to_client", ("sse",)),
    _ClassificationRow("http.response.pathsend", "send", "http", "http.stream", "request", "unary", "server_to_client", required_payload_fields=("path",)),
    _ClassificationRow("websocket.connect", "receive", "websocket", "websocket", "session", "unary", "client_to_server"),
    _ClassificationRow("websocket.receive", "receive", "websocket", "websocket", "message", "duplex", "client_to_server", ("json", "jsonrpc", "ndjson", "text", "bytes", "binary")),
    _ClassificationRow("websocket.disconnect", "receive", "websocket", "websocket", "session", "unary", "client_to_server"),
    _ClassificationRow("websocket.accept", "send", "websocket", "websocket", "session", "unary", "server_to_client"),
    _ClassificationRow("websocket.send", "send", "websocket", "websocket", "message", "duplex", "server_to_client", ("json", "jsonrpc", "ndjson", "text", "bytes", "binary")),
    _ClassificationRow("websocket.close", "send", "websocket", "websocket", "session", "unary", "server_to_client"),
    _ClassificationRow("webtransport.connect", "receive", "webtransport", "webtransport", "session", "unary", "client_to_server"),
    _ClassificationRow("webtransport.accept", "send", "webtransport", "webtransport", "session", "unary", "server_to_client"),
    _ClassificationRow("webtransport.stream.receive", "receive", "webtransport", "webtransport", "stream", "duplex", "client_to_server", ("json", "jsonrpc", "ndjson", "text", "bytes", "binary"), ("stream_id", "stream_direction"), "bidi", ("supports_bidi_streams",)),
    _ClassificationRow("webtransport.stream.receive", "receive", "webtransport", "webtransport", "stream", "client_stream", "client_to_server", ("json", "jsonrpc", "ndjson", "text", "bytes", "binary"), ("stream_id", "stream_direction"), "client_to_server", ("supports_uni_streams",)),
    _ClassificationRow("webtransport.stream.send", "send", "webtransport", "webtransport", "stream", "duplex", "server_to_client", ("json", "jsonrpc", "ndjson", "text", "bytes", "binary"), ("stream_id", "stream_direction"), "bidi", ("supports_bidi_streams",)),
    _ClassificationRow("webtransport.stream.send", "send", "webtransport", "webtransport", "stream", "server_stream", "server_to_client", ("json", "ndjson", "text", "bytes", "binary"), ("stream_id", "stream_direction"), "server_to_client", ("supports_uni_streams",)),
    _ClassificationRow("webtransport.datagram.receive", "receive", "webtransport", "webtransport", "datagram", "duplex", "client_to_server", ("json", "text", "bytes", "binary"), ("datagram_id",), capability_gates=("supports_datagrams",)),
    _ClassificationRow("webtransport.datagram.send", "send", "webtransport", "webtransport", "datagram", "duplex", "server_to_client", ("json", "text", "bytes", "binary"), ("datagram_id",), capability_gates=("supports_datagrams",)),
    _ClassificationRow("webtransport.disconnect", "receive", "webtransport", "webtransport", "session", "unary", "client_to_server"),
    _ClassificationRow("webtransport.close", "send", "webtransport", "webtransport", "session", "unary", "server_to_client"),
    _ClassificationRow("lifespan.startup", "receive", "lifespan", "lifespan", "lifespan", "unary", "system"),
    _ClassificationRow("lifespan.shutdown", "receive", "lifespan", "lifespan", "lifespan", "unary", "system"),
    _ClassificationRow("lifespan.startup.complete", "send", "lifespan", "lifespan", "lifespan", "unary", "system"),
    _ClassificationRow("lifespan.startup.failed", "send", "lifespan", "lifespan", "lifespan", "unary", "system", required_payload_fields=("message",)),
    _ClassificationRow("lifespan.shutdown.complete", "send", "lifespan", "lifespan", "lifespan", "unary", "system"),
    _ClassificationRow("lifespan.shutdown.failed", "send", "lifespan", "lifespan", "lifespan", "unary", "system", required_payload_fields=("message",)),
)


def _transport_ext(scope: dict[str, Any]) -> dict[str, Any]:
    ext = scope.setdefault("ext", {})
    if not isinstance(ext, dict):
        raise ProtocolError("scope ext must be a mapping")
    transport = ext.setdefault("transport", {})
    if not isinstance(transport, dict):
        raise ProtocolError("scope ext.transport must be a mapping")
    return transport


def _normalized_binding(binding: str | None, scope_type: str) -> str:
    if binding:
        normalized = str(binding).strip().lower().replace("_", "-")
        if normalized == "json-rpc":
            normalized = "jsonrpc"
        if normalized in _BINDING_ALIASES:
            return _BINDING_ALIASES[normalized]
        raise ProtocolError(f"unsupported binding for classification: {binding!r}")
    if scope_type == "http":
        return "rest"
    if scope_type == "websocket":
        return "websocket"
    if scope_type == "webtransport":
        return "webtransport"
    if scope_type == "lifespan":
        return "lifespan"
    raise ProtocolError(f"unsupported scope type for classification: {scope_type!r}")


def _scope_type(scope: dict[str, Any]) -> str:
    scope_type = str(scope.get("type", ""))
    if scope_type not in {"http", "websocket", "webtransport", "lifespan"}:
        raise ProtocolError(f"unsupported contract classification scope type: {scope_type!r}")
    return scope_type


def _capability(scope: dict[str, Any], gate: str) -> bool:
    ext = scope.get("ext", {})
    wt = ext.get("webtransport", {}) if isinstance(ext, dict) else {}
    if isinstance(wt, dict) and gate in wt:
        return bool(wt[gate])
    extensions = scope.get("extensions", {})
    legacy = extensions.get("tigrcorn.webtransport", {}) if isinstance(extensions, dict) else {}
    if isinstance(legacy, dict) and gate in legacy:
        return bool(legacy[gate])
    return False


def _derive_framing(event: dict[str, Any]) -> str | None:
    framing = event.get("framing")
    if framing is not None:
        return str(framing)
    if event.get("text") is not None:
        return "text"
    if event.get("bytes") is not None or event.get("data") is not None or event.get("body") is not None:
        return "bytes"
    return None


def project_scope_classification(scope: dict[str, Any]) -> ScopeProjection:
    scope_type = _scope_type(scope)
    transport = _transport_ext(scope)
    binding = _normalized_binding(transport.get("binding") or scope.get("binding"), scope_type)
    transport["binding"] = binding
    if "alpn" not in transport:
        http_version = scope.get("http_version")
        if http_version == "2":
            transport["alpn"] = "h2"
        elif http_version == "3":
            transport["alpn"] = "h3"
        elif http_version == "1.1":
            transport["alpn"] = "http/1.1"
    if "secure" not in transport:
        transport["secure"] = scope.get("scheme") in {"https", "wss"}
    return ScopeProjection(
        scope_type=scope_type,
        binding=binding,
        alpn=transport.get("alpn"),
        secure=bool(transport.get("secure", False)),
        framing=transport.get("framing"),
    )


def _row_to_projection(row: Any) -> EventProjection:
    if isinstance(row, _ClassificationRow):
        return EventProjection(row.event, row.channel, row.scope_type, row.binding, row.family, row.exchange, row.direction, row.allowed_framings)
    return EventProjection(
        event=row.event,
        channel=row.channel,
        scope_type=row.scope_type,
        binding=row.binding,
        family=row.family,
        exchange=row.exchange,
        direction=row.direction,
        allowed_framings=tuple(getattr(row, "allowed_framings", ()) or ()),
    )


def _projection_key(projection: EventProjection) -> tuple[str, str, str, str, str, str, str, tuple[str, ...]]:
    return (
        projection.event,
        projection.channel,
        projection.scope_type,
        projection.binding,
        projection.family,
        projection.exchange,
        projection.direction,
        projection.allowed_framings,
    )


def _fallback_classify(scope: dict[str, Any], channel: str, event: dict[str, Any]) -> EventProjection:
    if channel not in {"receive", "send"}:
        raise ProtocolError(f"unsupported ASGI contract channel: {channel!r}")
    scope_projection = project_scope_classification(scope)
    event_type = str(event.get("type", ""))
    for row in _ROWS:
        if row.event != event_type or row.channel != channel:
            continue
        if row.scope_type != scope_projection.scope_type or row.binding != scope_projection.binding:
            continue
        missing = [field for field in row.required_payload_fields if field not in event]
        if missing:
            raise ProtocolError(f"event {event_type!r} missing required fields: {missing!r}")
        if row.stream_direction is not None and event.get("stream_direction") != row.stream_direction:
            continue
        if any(not _capability(scope, gate) for gate in row.capability_gates):
            continue
        framing = _derive_framing(event)
        if framing is not None:
            if framing not in _FRAMINGS:
                raise ProtocolError(f"unsupported framing: {framing!r}")
            if row.allowed_framings and framing not in row.allowed_framings:
                raise ProtocolError(f"framing {framing!r} is illegal for {event_type!r}")
            if framing == "jsonrpc" and event.get("jsonrpc_complete") is not True:
                raise ProtocolError("jsonrpc framing requires jsonrpc_complete=True")
            if framing == "ndjson" and event.get("jsonrpc_complete") is True:
                raise ProtocolError("ndjson framing must not claim jsonrpc_complete")
        return _row_to_projection(row)
    raise ProtocolError(f"no contract classification for {channel}:{event_type}")


def project_event_classification(scope: dict[str, Any], channel: str, event: dict[str, Any]) -> EventProjection:
    if "subsurface" in event:
        raise ProtocolError("subsurface is not a contract event payload field")
    project_scope_classification(scope)
    event_type = str(event.get("type", ""))
    if _contract_classify_event is not None:
        try:
            row = _contract_classify_event(scope, channel, event_type, event)
            if _contract_validate_event_payload is not None and not _contract_validate_event_payload(event_type, event, row):
                raise ProtocolError(f"event payload failed contract validation: {event_type!r}")
            contract_projection = _row_to_projection(row)
            fallback_projection = _fallback_classify(scope, channel, event)
            if _projection_key(contract_projection) != _projection_key(fallback_projection):
                raise ProtocolError(f"contract classification drift for {channel}:{event_type}")
            return contract_projection
        except Exception as exc:
            raise ProtocolError(str(exc)) from exc
    return _fallback_classify(scope, channel, event)


def project_receive_event(scope: dict[str, Any], event: dict[str, Any]) -> EventProjection:
    return project_event_classification(scope, "receive", event)


def project_send_event(scope: dict[str, Any], event: dict[str, Any]) -> EventProjection:
    return project_event_classification(scope, "send", event)


def validate_projected_event(scope: dict[str, Any], channel: str, event: dict[str, Any]) -> None:
    project_event_classification(scope, channel, event)
