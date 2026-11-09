from __future__ import annotations

from typing import Literal


ListenerKind = Literal["tcp", "udp", "unix", "pipe", "inproc"]
ProtocolName = Literal["http1", "http2", "http3", "quic", "websocket", "webtransport", "rawframed", "custom"]
ClaimClass = Literal["rfc_scoped", "hybrid", "pure_operator", "non_rfc_custom"]
AppInterface = Literal["auto", "tigr-asgi-contract", "asgi3"]
