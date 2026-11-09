from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tigrcorn_core.constants import (
    DEFAULT_BACKLOG,
    DEFAULT_HOST,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_MAX_DATAGRAM_SIZE,
    DEFAULT_PIPE_MODE,
    DEFAULT_PORT,
)

from .types import ListenerKind


@dataclass(slots=True)
class CongestionControlConfig:
    algorithm: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QUICConfig:
    quic_secret: bytes | None = None
    require_retry: bool = False
    max_datagram_size: int = DEFAULT_MAX_DATAGRAM_SIZE
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT
    early_data_policy: Literal["allow", "deny", "require"] = "deny"
    congestion_control: CongestionControlConfig = field(
        default_factory=lambda: CongestionControlConfig(algorithm="reno")
    )


@dataclass(slots=True)
class WebTransportConfig:
    enabled: bool = False
    compatibility: Literal["current", "draft13"] = "current"
    profiles: list[str] = field(default_factory=list)
    preferred_profile: str | None = None
    max_sessions: int | None = None
    max_streams: int | None = None
    max_datagram_size: int | None = None
    stream_receive_coalesce_bytes: int = 16 * 1024
    stream_receive_max_delay_ms: int = 5
    origins: list[str] = field(default_factory=list)
    path: str | None = None


@dataclass(slots=True)
class ListenerConfig:
    kind: ListenerKind = "tcp"
    bind: str | None = None
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    path: str | None = None
    fd: int | None = None
    endpoint: str | None = None
    insecure_bind: str | None = None
    quic_bind: str | None = None
    backlog: int = DEFAULT_BACKLOG
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None
    ssl_keyfile_password: str | bytes | None = None
    ssl_ca_certs: str | None = None
    ssl_require_client_cert: bool = False
    ssl_ciphers: str | None = None
    resolved_cipher_suites: tuple[int, ...] = ()
    alpn_protocols: list[str] = field(default_factory=list)
    ocsp_mode: Literal["off", "soft-fail", "require"] = "off"
    ocsp_soft_fail: bool = False
    ocsp_cache_size: int = 128
    ocsp_max_age: float | None = 43_200.0
    crl_mode: Literal["off", "soft-fail", "require"] = "off"
    ssl_crl: str | None = None
    revocation_fetch: bool = True
    http_versions: list[str] = field(default_factory=lambda: ["1.1", "2"])
    websocket: bool = True
    reuse_port: bool = False
    reuse_address: bool = True
    nodelay: bool = True
    protocols: list[str] = field(default_factory=list)
    quic_secret: bytes | None = None
    quic_require_retry: bool = False
    max_datagram_size: int = DEFAULT_MAX_DATAGRAM_SIZE
    congestion_control: CongestionControlConfig | None = None
    pipe_mode: Literal["rawframed", "stream"] = DEFAULT_PIPE_MODE
    user: str | int | None = None
    group: str | int | None = None
    umask: int | None = None
    scheme: str | None = None

    @property
    def ssl_enabled(self) -> bool:
        return bool(self.ssl_certfile and self.ssl_keyfile)

    @property
    def label(self) -> str:
        if self.fd is not None:
            return f"fd://{self.fd}"
        if self.endpoint:
            return self.endpoint
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
