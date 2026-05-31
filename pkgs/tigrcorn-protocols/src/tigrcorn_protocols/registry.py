from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProtocolDescriptor:
    name: str
    multiplexed: bool = False
    asgi_scope_types: tuple[str, ...] = ()


BUILTIN_PROTOCOLS = {
    "http1": ProtocolDescriptor(name="http1", multiplexed=False, asgi_scope_types=("http",)),
    "http2": ProtocolDescriptor(name="http2", multiplexed=True, asgi_scope_types=("http",)),
    "http3": ProtocolDescriptor(name="http3", multiplexed=True, asgi_scope_types=("http",)),
    "quic": ProtocolDescriptor(name="quic", multiplexed=True, asgi_scope_types=("tigrcorn.quic",)),
    "websocket": ProtocolDescriptor(name="websocket", multiplexed=False, asgi_scope_types=("websocket",)),
    "lifespan": ProtocolDescriptor(name="lifespan", multiplexed=False, asgi_scope_types=("lifespan",)),
    "rawframed": ProtocolDescriptor(name="rawframed", multiplexed=False, asgi_scope_types=("tigrcorn.rawframed",)),
    "custom": ProtocolDescriptor(name="custom", multiplexed=False, asgi_scope_types=("tigrcorn.stream",)),
}
