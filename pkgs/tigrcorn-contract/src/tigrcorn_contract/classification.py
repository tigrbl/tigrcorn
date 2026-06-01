from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tigrcorn_core.errors import ConfigError

BindingKind = Literal["http", "http.stream", "websocket", "lifespan", "webtransport", "stream", "datagram", "rest", "jsonrpc", "sse"]
ProductSurfaceKind = Literal[
    "auto",
    "tigr-asgi-contract",
    "asgi3",
    "asgi2",
    "wsgi",
    "rsgi",
    "rest",
    "jsonrpc",
]

_SERVER_OWNED_RUNTIMES = {"http", "http.stream", "websocket", "lifespan", "webtransport", "stream", "datagram"}
_CLASSIFICATION_ONLY = {"rest", "jsonrpc", "sse"}
_SUPPORTED_APP_INTERFACES = {"auto", "tigr-asgi-contract", "asgi3"}
_UNSUPPORTED_COMPAT_INTERFACES = {"asgi2", "wsgi", "rsgi"}
_RUNTIME_EXCLUDED_CLASSIFICATIONS = {"rest", "jsonrpc"}


@dataclass(frozen=True, slots=True)
class BindingClassification:
    kind: BindingKind
    runtime_owned: bool
    classification_only: bool
    dispatch_runtime: str
    scope_type: str
    family: str
    exchange: str
    framing: str | None = None
    allowed_framings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FamilyCapability:
    family: str
    bindings: tuple[str, ...]
    subevents: tuple[str, ...]
    exchanges: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductSurfaceStatus:
    kind: ProductSurfaceKind
    runtime_available: bool
    classification_only: bool
    compatibility_exclusion: bool
    reason: str


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
        bindings=("websocket",),
        subevents=("message.in", "message.decode", "message.handle", "message.out", "message.ack", "message.nack"),
        exchanges=("duplex",),
    ),
    "stream": FamilyCapability(
        family="stream",
        bindings=("http.stream", "webtransport", "stream", "sse"),
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

_BINDING_SHAPES: dict[str, tuple[str, str, str, str | None, tuple[str, ...]]] = {
    "http": ("http", "request", "unary", None, ()),
    "http.stream": ("http", "stream", "server_stream", None, ()),
    "websocket": ("websocket", "message", "duplex", None, ()),
    "lifespan": ("lifespan", "session", "duplex", None, ()),
    "webtransport": ("webtransport", "session", "duplex", None, ()),
    "stream": ("tigrcorn.stream", "stream", "duplex", None, ()),
    "datagram": ("tigrcorn.datagram", "datagram", "duplex", None, ()),
    "rest": ("http", "request", "unary", "json", ("json",)),
    "jsonrpc": ("http", "request", "unary", "jsonrpc", ("jsonrpc",)),
    "sse": ("http", "stream", "server_stream", "sse", ("sse",)),
}


def classify_binding(kind: str) -> BindingClassification:
    normalized = kind.strip().lower().replace("_", "-")
    if normalized == "json-rpc":
        normalized = "jsonrpc"
    if normalized not in _SERVER_OWNED_RUNTIMES | _CLASSIFICATION_ONLY:
        raise ConfigError(f"unsupported binding classification: {kind!r}")
    scope_type, family, exchange, framing, allowed_framings = _BINDING_SHAPES[normalized]
    return BindingClassification(
        kind=normalized,  # type: ignore[arg-type]
        runtime_owned=normalized in _SERVER_OWNED_RUNTIMES,
        classification_only=normalized in _CLASSIFICATION_ONLY,
        dispatch_runtime="application" if normalized in _CLASSIFICATION_ONLY else "tigrcorn",
        scope_type=scope_type,
        family=family,
        exchange=exchange,
        framing=framing,
        allowed_framings=allowed_framings,
    )


def runtime_interface_available(interface: str) -> bool:
    return product_surface_status(interface).runtime_available


def _normalize_product_surface(value: str) -> ProductSurfaceKind:
    normalized = value.strip().lower().replace("_", "-")
    if normalized == "json-rpc":
        normalized = "jsonrpc"
    if normalized not in _SUPPORTED_APP_INTERFACES | _UNSUPPORTED_COMPAT_INTERFACES | _RUNTIME_EXCLUDED_CLASSIFICATIONS:
        raise ConfigError(f"unsupported product surface: {value!r}")
    return normalized  # type: ignore[return-value]


def product_surface_status(surface: str) -> ProductSurfaceStatus:
    normalized = _normalize_product_surface(surface)
    if normalized in _SUPPORTED_APP_INTERFACES:
        return ProductSurfaceStatus(
            kind=normalized,
            runtime_available=True,
            classification_only=False,
            compatibility_exclusion=False,
            reason="supported app interface",
        )
    if normalized in _RUNTIME_EXCLUDED_CLASSIFICATIONS:
        return ProductSurfaceStatus(
            kind=normalized,
            runtime_available=False,
            classification_only=True,
            compatibility_exclusion=False,
            reason="classification-only binding; runtime belongs to the application layer",
        )
    return ProductSurfaceStatus(
        kind=normalized,
        runtime_available=False,
        classification_only=False,
        compatibility_exclusion=True,
        reason="unsupported compatibility interface",
    )


def require_product_runtime_available(surface: str) -> ProductSurfaceStatus:
    status = product_surface_status(surface)
    if not status.runtime_available:
        raise ConfigError(f"unsupported runtime product surface: {surface!r} ({status.reason})")
    return status


def family_capability(family: str) -> FamilyCapability:
    normalized = family.strip().lower()
    try:
        return _FAMILY_CAPABILITIES[normalized]
    except KeyError as exc:
        raise ConfigError(f"unsupported contract family: {family!r}") from exc


def validate_binding_legality(*, binding: str, family: str, subevent: str | None = None, exchange: str | None = None) -> None:
    normalized_binding = binding.strip().lower().replace("_", "-")
    if normalized_binding == "json-rpc":
        normalized_binding = "jsonrpc"
    classification = classify_binding(normalized_binding)
    normalized_family = family.strip().lower()
    if classification.classification_only and normalized_family != classification.family:
        raise ConfigError(f"binding {binding!r} is illegal for family {family!r}")
    capability = family_capability(family)
    if normalized_binding not in capability.bindings:
        raise ConfigError(f"binding {binding!r} is illegal for family {family!r}")
    if subevent is not None and subevent not in capability.subevents and not subevent.endswith(".emit_complete"):
        raise ConfigError(f"subevent {subevent!r} is illegal for family {family!r}")
    if classification.classification_only and exchange is not None and exchange != classification.exchange:
        raise ConfigError(f"exchange {exchange!r} is illegal for binding {binding!r}")
    if exchange is not None and exchange not in capability.exchanges:
        raise ConfigError(f"exchange {exchange!r} is illegal for family {family!r}")
