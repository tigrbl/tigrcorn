from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tigrcorn.errors import ConfigError

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
