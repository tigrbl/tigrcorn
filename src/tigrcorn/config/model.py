from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from tigrcorn.constants import (
    DEFAULT_BACKLOG,
    DEFAULT_HOST,
    DEFAULT_LIFESPAN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_MAX_DATAGRAM_SIZE,
    DEFAULT_MAX_HEADER_SIZE,
    DEFAULT_PIPE_MODE,
    DEFAULT_PORT,
    DEFAULT_QUIC_SECRET,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_SERVER_HEADER,
    DEFAULT_SHUTDOWN_TIMEOUT,
    DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE,
    DEFAULT_WRITE_TIMEOUT,
)

ListenerKind = Literal["tcp", "udp", "unix", "pipe", "inproc"]
ProtocolName = Literal["http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"]


@dataclass(slots=True)
class ListenerConfig:
    kind: ListenerKind = "tcp"
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    path: str | None = None
    backlog: int = DEFAULT_BACKLOG
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None
    ssl_ca_certs: str | None = None
    ssl_require_client_cert: bool = False
    alpn_protocols: list[str] = field(default_factory=lambda: ["h2", "http/1.1"])
    http_versions: list[str] = field(default_factory=lambda: ["1.1", "2"])
    websocket: bool = True
    reuse_port: bool = False
    reuse_address: bool = True
    nodelay: bool = True
    protocols: list[str] = field(default_factory=list)
    quic_secret: bytes = DEFAULT_QUIC_SECRET
    quic_require_retry: bool = False
    max_datagram_size: int = DEFAULT_MAX_DATAGRAM_SIZE
    pipe_mode: Literal["rawframed", "stream"] = DEFAULT_PIPE_MODE
    scheme: str | None = None

    @property
    def ssl_enabled(self) -> bool:
        return bool(self.ssl_certfile and self.ssl_keyfile)

    @property
    def label(self) -> str:
        if self.kind == "unix":
            return self.path or "<unix:unset>"
        if self.kind == "pipe":
            return f"pipe://{self.path or 'default'}"
        if self.kind == "inproc":
            return "inproc://default"
        if self.kind == "udp":
            return f"udp://{self.host}:{self.port}"
        return f"{self.host}:{self.port}"

    @property
    def enabled_protocols(self) -> tuple[str, ...]:
        configured = [p.lower() for p in self.protocols]
        if not configured:
            if self.kind == "udp":
                configured = ["quic"]
                if "3" in self.http_versions:
                    configured.append("http3")
            elif self.kind == "pipe":
                configured = ["rawframed"] if self.pipe_mode == "rawframed" else ["custom"]
            elif self.kind == "inproc":
                configured = ["custom"]
            else:
                configured = ["http1"]
                if "2" in self.http_versions:
                    configured.append("http2")
                if self.websocket:
                    configured.append("websocket")
        seen: list[str] = []
        for item in configured:
            if item not in seen:
                seen.append(item)
        return tuple(seen)


@dataclass(slots=True)
class ServerConfig:
    app: str | None = None
    listeners: list[ListenerConfig] = field(default_factory=lambda: [ListenerConfig()])
    lifespan: Literal["auto", "on", "off"] = DEFAULT_LIFESPAN
    log_level: str = DEFAULT_LOG_LEVEL
    access_log: bool = True
    debug: bool = False
    read_timeout: float = DEFAULT_READ_TIMEOUT
    write_timeout: float = DEFAULT_WRITE_TIMEOUT
    shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT
    max_body_size: int = DEFAULT_MAX_BODY_SIZE
    max_header_size: int = DEFAULT_MAX_HEADER_SIZE
    websocket_max_message_size: int = DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE
    server_header: bytes = DEFAULT_SERVER_HEADER
    enable_h2c: bool = True

    @property
    def server_header_value(self) -> bytes | None:
        return self.server_header or None
