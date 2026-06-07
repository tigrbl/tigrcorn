from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .app import AppConfig, HooksConfig, ProcessConfig
from .http import HTTPConfig, StaticConfig, WebSocketConfig
from .observability import LoggingConfig, MetricsConfig
from .scheduler import SchedulerConfig
from .security import ProxyConfig, TLSConfig
from .transports import ListenerConfig, QUICConfig, WebTransportConfig


@dataclass(slots=True)
class ServerConfig:
    app: AppConfig = field(default_factory=AppConfig)
    process: ProcessConfig = field(default_factory=ProcessConfig)
    listeners: list[ListenerConfig] = field(default_factory=lambda: [ListenerConfig()])
    tls: TLSConfig = field(default_factory=TLSConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    http: HTTPConfig = field(default_factory=HTTPConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    static: StaticConfig = field(default_factory=StaticConfig)
    quic: QUICConfig = field(default_factory=QUICConfig)
    webtransport: WebTransportConfig = field(default_factory=WebTransportConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    hooks: HooksConfig = field(default_factory=HooksConfig)
    debug: bool = False

    @property
    def lifespan(self) -> Literal["auto", "on", "off"]:
        return self.app.lifespan

    @lifespan.setter
    def lifespan(self, value: Literal["auto", "on", "off"]) -> None:
        self.app.lifespan = value

    @property
    def log_level(self) -> str:
        return self.logging.level

    @log_level.setter
    def log_level(self, value: str) -> None:
        self.logging.level = value

    @property
    def access_log(self) -> bool:
        return self.logging.access_log

    @access_log.setter
    def access_log(self, value: bool) -> None:
        self.logging.access_log = value

    @property
    def read_timeout(self) -> float:
        return self.http.read_timeout

    @read_timeout.setter
    def read_timeout(self, value: float) -> None:
        self.http.read_timeout = value

    @property
    def write_timeout(self) -> float:
        return self.http.write_timeout

    @write_timeout.setter
    def write_timeout(self, value: float) -> None:
        self.http.write_timeout = value

    @property
    def shutdown_timeout(self) -> float:
        return self.http.shutdown_timeout

    @shutdown_timeout.setter
    def shutdown_timeout(self, value: float) -> None:
        self.http.shutdown_timeout = value

    @property
    def max_body_size(self) -> int:
        return self.http.max_body_size

    @max_body_size.setter
    def max_body_size(self, value: int) -> None:
        self.http.max_body_size = value

    @property
    def max_header_size(self) -> int:
        return self.http.max_header_size

    @max_header_size.setter
    def max_header_size(self, value: int) -> None:
        self.http.max_header_size = value

    @property
    def websocket_max_message_size(self) -> int:
        return self.websocket.max_message_size

    @websocket_max_message_size.setter
    def websocket_max_message_size(self, value: int) -> None:
        self.websocket.max_message_size = value

    @property
    def websocket_max_queue(self) -> int:
        return self.websocket.max_queue

    @websocket_max_queue.setter
    def websocket_max_queue(self, value: int) -> None:
        self.websocket.max_queue = value

    @property
    def server_header(self) -> bytes | str:
        return self.proxy.server_header

    @server_header.setter
    def server_header(self, value: bytes | str) -> None:
        self.proxy.server_header = value

    @property
    def server_header_value(self) -> bytes | None:
        if not self.proxy.include_server_header:
            return None
        value = self.proxy.server_header
        if isinstance(value, str):
            return value.encode("latin1") if value else None
        return value or None

    @property
    def include_date_header(self) -> bool:
        return self.proxy.include_date_header

    @include_date_header.setter
    def include_date_header(self, value: bool) -> None:
        self.proxy.include_date_header = value

    @property
    def default_response_headers(self) -> list[tuple[bytes, bytes]]:
        normalized: list[tuple[bytes, bytes]] = []
        for entry in self.proxy.default_headers:
            if isinstance(entry, tuple) and len(entry) == 2:
                name, value = entry
                normalized.append(
                    (
                        name.encode("latin1") if isinstance(name, str) else bytes(name),
                        value.encode("latin1") if isinstance(value, str) else bytes(value),
                    )
                )
        return normalized

    @property
    def allowed_server_names(self) -> tuple[str, ...]:
        return tuple(self.proxy.server_names)

    @property
    def alt_svc_values(self) -> tuple[bytes, ...]:
        explicit: list[bytes] = []
        for entry in self.http.alt_svc_headers:
            if isinstance(entry, str):
                value = entry.encode("ascii") if entry else b""
            else:
                value = bytes(entry)
            if value:
                explicit.append(value)
        if explicit:
            return tuple(explicit)
        if not self.http.alt_svc_auto:
            return ()
        values: list[bytes] = []
        seen: set[bytes] = set()
        for listener in self.listeners:
            if listener.kind != "udp":
                continue
            if "http3" not in listener.enabled_protocols and "3" not in listener.http_versions:
                continue
            rendered = f'h3=":{int(listener.port)}"; ma={int(self.http.alt_svc_max_age)}'
            if self.http.alt_svc_persist:
                rendered += "; persist=1"
            payload = rendered.encode("ascii")
            if payload not in seen:
                seen.add(payload)
                values.append(payload)
        return tuple(values)
