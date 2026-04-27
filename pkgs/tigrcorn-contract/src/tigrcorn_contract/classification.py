from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tigrcorn_core.errors import ConfigError

BindingKind = Literal["http", "websocket", "lifespan", "webtransport", "stream", "datagram", "rest", "jsonrpc", "sse"]

_SERVER_OWNED_RUNTIMES = {"http", "websocket", "lifespan", "webtransport", "stream", "datagram"}
_CLASSIFICATION_ONLY = {"rest", "jsonrpc", "sse"}
_SUPPORTED_APP_INTERFACES = {"auto", "tigr-asgi-contract", "asgi3"}


@dataclass(frozen=True, slots=True)
class BindingClassification:
    kind: BindingKind
    runtime_owned: bool
    classification_only: bool
    dispatch_runtime: str


@dataclass(frozen=True, slots=True)
class FamilyCapability:
    family: str
    bindings: tuple[str, ...]
    subevents: tuple[str, ...]
    exchanges: tuple[str, ...]


_FAMILY_CAPABILITIES = {
    "request": FamilyCapability(
        family="request",
        bindings=("http", "http.stream", "rest", "jsonrpc"),
        subevents=("request.open", "request.body_in", "request.chunk_in", "request.close", "request.disconnect"),
        exchanges=("unary", "server_stream"),
    ),
    "session": FamilyCapability(
        family="session",
        bindings=("websocket", "webtransport", "lifespan"),
        subevents=("session.open", "session.accept", "session.ready", "session.heartbeat", "session.close", "session.disconnect"),
        exchanges=("duplex",),
    ),
    "message": FamilyCapability(
        family="message",
        bindings=("websocket", "sse", "jsonrpc"),
        subevents=("message.in", "message.decode", "message.handle", "message.out", "message.ack", "message.nack"),
        exchanges=("unary", "server_stream", "duplex"),
    ),
    "stream": FamilyCapability(
        family="stream",
        bindings=("http.stream", "webtransport", "stream"),
        subevents=("stream.open", "stream.chunk_in", "stream.chunk_out", "stream.flush", "stream.finalize", "stream.abort", "stream.close"),
        exchanges=("server_stream", "duplex"),
    ),
    "datagram": FamilyCapability(
        family="datagram",
        bindings=("webtransport", "datagram"),
        subevents=("datagram.in", "datagram.handle", "datagram.out", "datagram.ack", "datagram.close"),
        exchanges=("duplex",),
    ),
}


def classify_binding(kind: str) -> BindingClassification:
    normalized = kind.strip().lower().replace("_", "-")
    if normalized == "json-rpc":
        normalized = "jsonrpc"
    if normalized not in _SERVER_OWNED_RUNTIMES | _CLASSIFICATION_ONLY:
        raise ConfigError(f"unsupported binding classification: {kind!r}")
    return BindingClassification(
        kind=normalized,  # type: ignore[arg-type]
        runtime_owned=normalized in _SERVER_OWNED_RUNTIMES,
        classification_only=normalized in _CLASSIFICATION_ONLY,
        dispatch_runtime="application" if normalized in _CLASSIFICATION_ONLY else "tigrcorn",
    )


def runtime_interface_available(interface: str) -> bool:
    normalized = interface.strip().lower().replace("_", "-")
    if normalized == "jsonrpc":
        normalized = "json-rpc"
    return normalized in _SUPPORTED_APP_INTERFACES


def family_capability(family: str) -> FamilyCapability:
    normalized = family.strip().lower()
    try:
        return _FAMILY_CAPABILITIES[normalized]
    except KeyError as exc:
        raise ConfigError(f"unsupported contract family: {family!r}") from exc


def validate_binding_legality(*, binding: str, family: str, subevent: str | None = None, exchange: str | None = None) -> None:
    normalized_binding = binding.strip().lower()
    if normalized_binding == "json-rpc":
        normalized_binding = "jsonrpc"
    capability = family_capability(family)
    if normalized_binding not in capability.bindings:
        raise ConfigError(f"binding {binding!r} is illegal for family {family!r}")
    if subevent is not None and subevent not in capability.subevents and not subevent.endswith(".emit_complete"):
        raise ConfigError(f"subevent {subevent!r} is illegal for family {family!r}")
    if exchange is not None and exchange not in capability.exchanges:
        raise ConfigError(f"exchange {exchange!r} is illegal for family {family!r}")
