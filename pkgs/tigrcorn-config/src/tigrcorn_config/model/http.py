from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from tigrcorn_core.constants import (
    DEFAULT_HTTP_CONTENT_CODINGS,
    DEFAULT_HTTP1_BUFFER_SIZE,
    DEFAULT_HTTP1_MAX_INCOMPLETE_EVENT_SIZE,
    DEFAULT_HTTP2_INITIAL_CONNECTION_WINDOW_SIZE,
    DEFAULT_HTTP2_INITIAL_STREAM_WINDOW_SIZE,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_KEEPALIVE_TIMEOUT,
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_MAX_HEADER_SIZE,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_SHUTDOWN_TIMEOUT,
    DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE,
    DEFAULT_WEBSOCKET_MAX_QUEUE,
    DEFAULT_WRITE_TIMEOUT,
)


@dataclass(slots=True)
class HTTPConfig:
    http_versions: list[str] = field(default_factory=lambda: ["1.1", "2"])
    enable_h2c: bool = False
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
    connect_policy: Literal["relay", "deny", "allowlist"] = "deny"
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
    index_file: str | None = "index.html"
    expires: int | None = None
