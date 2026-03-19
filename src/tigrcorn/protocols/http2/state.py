from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.http2.codec import DEFAULT_SETTINGS, SETTING_ENABLE_PUSH, SETTING_INITIAL_WINDOW_SIZE, SETTING_MAX_CONCURRENT_STREAMS, SETTING_MAX_FRAME_SIZE, SETTING_MAX_HEADER_LIST_SIZE

MAX_FLOW_WINDOW = 0x7FFFFFFF


class H2StreamLifecycle(str, Enum):
    IDLE = "idle"
    RESERVED_LOCAL = "reserved-local"
    RESERVED_REMOTE = "reserved-remote"
    OPEN = "open"
    HALF_CLOSED_LOCAL = "half-closed-local"
    HALF_CLOSED_REMOTE = "half-closed-remote"
    CLOSED = "closed"


@dataclass(slots=True)
class FlowWindow:
    available: int

    def consume(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.available -= amount

    def increase(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if self.available > MAX_FLOW_WINDOW - amount:
            raise ProtocolError("HTTP/2 flow-control window overflow")
        self.available += amount

    def adjust(self, delta: int) -> None:
        if delta == 0:
            return
        if delta > 0 and self.available > MAX_FLOW_WINDOW - delta:
            raise ProtocolError("HTTP/2 flow-control window overflow")
        self.available += delta


@dataclass(slots=True)
class H2StreamState:
    stream_id: int
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    trailers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body_parts: list[bytes] = field(default_factory=list)
    header_fragments: list[bytes] = field(default_factory=list)
    headers_complete: bool = False
    trailers_complete: bool = False
    awaiting_continuation: bool = False
    end_stream_received: bool = False
    dispatched: bool = False
    closed: bool = False
    websocket_session: object | None = None
    connect_tunnel: object | None = None
    send_window: FlowWindow = field(default_factory=lambda: FlowWindow(DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE]))
    receive_window: FlowWindow = field(default_factory=lambda: FlowWindow(DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE]))
    receive_window_target: int = DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE]
    receive_consumed_since_update: int = 0
    buffered_body_size: int = 0
    header_block_bytes: int = 0
    current_header_block_is_trailers: bool = False
    opened: bool = False
    local_closed: bool = False
    reserved_local: bool = False
    reserved_remote: bool = False
    reset_received: bool = False
    reset_sent: bool = False
    lifecycle: H2StreamLifecycle = H2StreamLifecycle.IDLE

    @property
    def body(self) -> bytes:
        return b"".join(self.body_parts)

    @property
    def remote_closed(self) -> bool:
        return self.end_stream_received

    def _sync_lifecycle(self) -> None:
        if self.reset_received or self.reset_sent or (self.local_closed and self.end_stream_received):
            self.lifecycle = H2StreamLifecycle.CLOSED
        elif self.reserved_local:
            self.lifecycle = H2StreamLifecycle.RESERVED_LOCAL
        elif self.reserved_remote:
            self.lifecycle = H2StreamLifecycle.RESERVED_REMOTE
        elif not self.opened:
            self.lifecycle = H2StreamLifecycle.IDLE
        elif self.local_closed:
            self.lifecycle = H2StreamLifecycle.HALF_CLOSED_LOCAL
        elif self.end_stream_received:
            self.lifecycle = H2StreamLifecycle.HALF_CLOSED_REMOTE
        else:
            self.lifecycle = H2StreamLifecycle.OPEN
        self.closed = self.lifecycle is H2StreamLifecycle.CLOSED

    def open_remote(self, *, end_stream: bool = False) -> None:
        if self.opened and self.lifecycle is not H2StreamLifecycle.IDLE:
            raise ProtocolError("HTTP/2 stream is already open")
        self.opened = True
        self.end_stream_received = end_stream
        self._sync_lifecycle()

    def reserve_local(self) -> None:
        self.reserved_local = True
        self.opened = False
        self.local_closed = False
        self.end_stream_received = False
        self._sync_lifecycle()

    def open_local_reserved(self, *, end_stream: bool = False) -> None:
        if not self.reserved_local:
            raise ProtocolError("HTTP/2 local stream is not reserved")
        self.reserved_local = False
        self.opened = True
        self.end_stream_received = True
        self.local_closed = end_stream
        self._sync_lifecycle()

    def receive_end_stream(self) -> None:
        self.end_stream_received = True
        self._sync_lifecycle()

    def send_end_stream(self) -> None:
        self.local_closed = True
        self._sync_lifecycle()

    def mark_reset_received(self) -> None:
        self.reset_received = True
        self.local_closed = True
        self.end_stream_received = True
        self._sync_lifecycle()

    def mark_reset_sent(self) -> None:
        self.reset_sent = True
        self.local_closed = True
        self.end_stream_received = True
        self._sync_lifecycle()

    def append_body(self, payload: bytes) -> None:
        if payload:
            self.body_parts.append(payload)
            self.buffered_body_size += len(payload)


@dataclass(slots=True)
class H2ConnectionState:
    local_settings: dict[int, int] = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    remote_settings: dict[int, int] = field(default_factory=lambda: {**DEFAULT_SETTINGS, SETTING_ENABLE_PUSH: 1})
    connection_send_window: FlowWindow = field(default_factory=lambda: FlowWindow(DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE]))
    connection_receive_window: FlowWindow = field(default_factory=lambda: FlowWindow(DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE]))
    connection_receive_window_target: int = DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE]
    connection_receive_consumed_since_update: int = 0
    preface_seen: bool = False
    remote_settings_seen: bool = False
    shutdown: bool = False
    last_stream_id: int = 0
    highest_remote_stream_id: int = 0
    peer_goaway_received: bool = False
    peer_last_stream_id: int | None = None
    local_goaway_sent: bool = False
    local_goaway_last_stream_id: int | None = None
    next_local_stream_id: int = 2

    @property
    def max_frame_size(self) -> int:
        return self.remote_settings.get(SETTING_MAX_FRAME_SIZE, DEFAULT_SETTINGS[SETTING_MAX_FRAME_SIZE])

    @property
    def initial_window_size(self) -> int:
        return self.remote_settings.get(SETTING_INITIAL_WINDOW_SIZE, DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE])

    @property
    def local_initial_window_size(self) -> int:
        return self.local_settings.get(SETTING_INITIAL_WINDOW_SIZE, DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE])

    @property
    def max_concurrent_streams(self) -> int:
        return self.local_settings.get(SETTING_MAX_CONCURRENT_STREAMS, DEFAULT_SETTINGS[SETTING_MAX_CONCURRENT_STREAMS])

    @property
    def max_header_list_size(self) -> int:
        return self.local_settings.get(SETTING_MAX_HEADER_LIST_SIZE, DEFAULT_SETTINGS[SETTING_MAX_HEADER_LIST_SIZE])

    @property
    def client_allows_push(self) -> bool:
        return self.remote_settings.get(SETTING_ENABLE_PUSH, 1) != 0
