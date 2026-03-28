from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tigrcorn.constants import (
    DEFAULT_BACKLOG,
    DEFAULT_ENV_PREFIX,
    DEFAULT_HOST,
    DEFAULT_HTTP_CONTENT_CODINGS,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_KEEPALIVE_TIMEOUT,
    DEFAULT_LIFESPAN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_MAX_DATAGRAM_SIZE,
    DEFAULT_MAX_HEADER_SIZE,
    DEFAULT_HTTP1_BUFFER_SIZE,
    DEFAULT_HTTP1_MAX_INCOMPLETE_EVENT_SIZE,
    DEFAULT_HTTP2_INITIAL_CONNECTION_WINDOW_SIZE,
    DEFAULT_HTTP2_INITIAL_STREAM_WINDOW_SIZE,
    DEFAULT_PIPE_MODE,
    DEFAULT_PORT,
    DEFAULT_QUIC_SECRET,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_SERVER_HEADER,
    DEFAULT_SHUTDOWN_TIMEOUT,
    DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE,
    DEFAULT_WEBSOCKET_MAX_QUEUE,
    DEFAULT_RUNTIME,
    DEFAULT_WORKER_CLASS,
    DEFAULT_WORKER_HEALTHCHECK_TIMEOUT,
    DEFAULT_WORKERS,
    DEFAULT_WRITE_TIMEOUT,
)

ListenerKind = Literal["tcp", "udp", "unix", "pipe", "inproc"]
ProtocolName = Literal["http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"]
ClaimClass = Literal["rfc_scoped", "hybrid", "pure_operator", "non_rfc_custom"]


@dataclass(slots=True)
class AppConfig:
    target: str | None = None
    factory: bool = False
    app_dir: str | None = None
    config_file: str | None = None
    env_prefix: str = DEFAULT_ENV_PREFIX
    env_file: str | None = None
    lifespan: Literal["auto", "on", "off"] = DEFAULT_LIFESPAN
    reload: bool = False
    reload_dirs: list[str] = field(default_factory=list)
    reload_include: list[str] = field(default_factory=list)
    reload_exclude: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProcessConfig:
    workers: int = DEFAULT_WORKERS
    worker_class: str = DEFAULT_WORKER_CLASS
    runtime: str = DEFAULT_RUNTIME
    pid_file: str | None = None
    worker_healthcheck_timeout: float = DEFAULT_WORKER_HEALTHCHECK_TIMEOUT
    limit_max_requests: int | None = None
    max_requests_jitter: int = 0


@dataclass(slots=True)
class TLSConfig:
    certfile: str | None = None
    keyfile: str | None = None
    keyfile_password: str | bytes | None = None
    ca_certs: str | None = None
    require_client_cert: bool = False
    ciphers: str | None = None
    resolved_cipher_suites: tuple[int, ...] = ()
    alpn_protocols: list[str] = field(default_factory=lambda: ["h2", "http/1.1"])
    ocsp_mode: Literal["off", "soft-fail", "require"] = "off"
    ocsp_soft_fail: bool = False
    ocsp_cache_size: int = 128
    ocsp_max_age: float | None = 43_200.0
    crl_mode: Literal["off", "soft-fail", "require"] = "off"
    crl: str | None = None
    revocation_fetch: bool = True


@dataclass(slots=True)
class ProxyConfig:
    proxy_headers: bool = False
    forwarded_allow_ips: list[str] = field(default_factory=list)
    root_path: str = ""
    server_header: bytes | str = DEFAULT_SERVER_HEADER
    include_server_header: bool = True
    include_date_header: bool = True
    default_headers: list[tuple[bytes | str, bytes | str] | list[bytes | str] | dict[str, bytes | str]] = field(default_factory=list)
    server_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HTTPConfig:
    http_versions: list[str] = field(default_factory=lambda: ["1.1", "2"])
    enable_h2c: bool = True
    keep_alive_timeout: float = DEFAULT_KEEPALIVE_TIMEOUT
    read_timeout: float = DEFAULT_READ_TIMEOUT
    write_timeout: float = DEFAULT_WRITE_TIMEOUT
    shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT
    max_body_size: int = DEFAULT_MAX_BODY_SIZE
    max_header_size: int = DEFAULT_MAX_HEADER_SIZE
    http1_max_incomplete_event_size: int = DEFAULT_HTTP1_MAX_INCOMPLETE_EVENT_SIZE
    http1_buffer_size: int = DEFAULT_HTTP1_BUFFER_SIZE
    http1_header_read_timeout: float | None = None
    http1_keep_alive: bool = True
    http2_max_concurrent_streams: int | None = None
    http2_max_headers_size: int | None = None
    http2_max_frame_size: int | None = None
    http2_adaptive_window: bool = False
    http2_initial_connection_window_size: int | None = DEFAULT_HTTP2_INITIAL_CONNECTION_WINDOW_SIZE
    http2_initial_stream_window_size: int | None = DEFAULT_HTTP2_INITIAL_STREAM_WINDOW_SIZE
    http2_keep_alive_interval: float | None = None
    http2_keep_alive_timeout: float | None = None
    connect_policy: Literal["relay", "deny", "allowlist"] = "relay"
    connect_allow: list[str] = field(default_factory=list)
    trailer_policy: Literal["pass", "drop", "strict"] = "pass"
    content_coding_policy: Literal["allowlist", "identity-only", "strict"] = "allowlist"
    content_codings: list[str] = field(default_factory=lambda: list(DEFAULT_HTTP_CONTENT_CODINGS))
    alt_svc_headers: list[bytes | str] = field(default_factory=list)
    alt_svc_auto: bool = False
    alt_svc_max_age: int = 86_400
    alt_svc_persist: bool = False


@dataclass(slots=True)
class WebSocketConfig:
    enabled: bool = True
    max_message_size: int = DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE
    max_queue: int = DEFAULT_WEBSOCKET_MAX_QUEUE
    ping_interval: float | None = None
    ping_timeout: float | None = None
    compression: Literal["off", "permessage-deflate"] = "off"


@dataclass(slots=True)
class StaticConfig:
    route: str | None = None
    mount: str | None = None
    dir_to_file: bool = True
    index_file: str | None = 'index.html'
    expires: int | None = None


@dataclass(slots=True)
class QUICConfig:
    quic_secret: bytes = DEFAULT_QUIC_SECRET
    require_retry: bool = False
    max_datagram_size: int = DEFAULT_MAX_DATAGRAM_SIZE
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT
    early_data_policy: Literal["allow", "deny", "require"] = "allow"


@dataclass(slots=True)
class LoggingConfig:
    level: str = DEFAULT_LOG_LEVEL
    access_log: bool = True
    access_log_file: str | None = None
    access_log_format: str | None = None
    error_log_file: str | None = None
    log_config: str | None = None
    structured: bool = False
    use_colors: bool | None = None
    explicit_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MetricsConfig:
    enabled: bool = False
    bind: str | None = None
    statsd_host: str | None = None
    otel_endpoint: str | None = None


@dataclass(slots=True)
class SchedulerConfig:
    limit_concurrency: int | None = None
    max_connections: int | None = None
    max_tasks: int | None = None
    max_streams: int | None = None


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
    quic_secret: bytes = DEFAULT_QUIC_SECRET
    quic_require_retry: bool = False
    max_datagram_size: int = DEFAULT_MAX_DATAGRAM_SIZE
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


@dataclass(slots=True)
class HooksConfig:
    on_startup: list[Any] = field(default_factory=list)
    on_shutdown: list[Any] = field(default_factory=list)
    on_reload: list[Any] = field(default_factory=list)


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
                normalized.append((name.encode("latin1") if isinstance(name, str) else bytes(name), value.encode("latin1") if isinstance(value, str) else bytes(value)))
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
            if listener.kind != 'udp':
                continue
            if 'http3' not in listener.enabled_protocols and '3' not in listener.http_versions:
                continue
            rendered = f'h3=":{int(listener.port)}"; ma={int(self.http.alt_svc_max_age)}'
            if self.http.alt_svc_persist:
                rendered += '; persist=1'
            payload = rendered.encode('ascii')
            if payload not in seen:
                seen.add(payload)
                values.append(payload)
        return tuple(values)

    @property
    def enable_h2c(self) -> bool:
        return self.http.enable_h2c

    @enable_h2c.setter
    def enable_h2c(self, value: bool) -> None:
        self.http.enable_h2c = value

    @property
    def static_mount_enabled(self) -> bool:
        return bool(self.static.mount)
