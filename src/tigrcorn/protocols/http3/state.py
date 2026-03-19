from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HTTP3BlockedSection:
    kind: str
    payload: bytes
    push_id: int | None = None


@dataclass(slots=True)
class HTTP3PushPromiseState:
    push_id: int
    headers: list[tuple[bytes, bytes]]
    request_stream_ids: set[int] = field(default_factory=set)


@dataclass(slots=True)
class HTTP3RequestState:
    stream_id: int
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    trailers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body_parts: list[bytes] = field(default_factory=list)
    ended: bool = False
    parse_buffer: bytearray = field(default_factory=bytearray)
    blocked_header_sections: list[HTTP3BlockedSection] = field(default_factory=list)
    phase: str = 'initial'
    received_initial_headers: bool = False
    received_trailers: bool = False
    expected_content_length: int | None = None
    received_content_length: int = 0
    push_promises: dict[int, HTTP3PushPromiseState] = field(default_factory=dict)
    abandoned: bool = False

    @property
    def body(self) -> bytes:
        return b''.join(self.body_parts)

    @property
    def ready(self) -> bool:
        return (
            not self.abandoned
            and self.ended
            and self.received_initial_headers
            and not self.blocked_header_sections
            and not self.parse_buffer
        )


@dataclass(slots=True)
class HTTP3UniStreamState:
    stream_id: int
    stream_type: int | None = None
    parse_buffer: bytearray = field(default_factory=bytearray)
    settings_received: bool = False
    discard_stream: bool = False
    push_id: int | None = None


@dataclass(slots=True)
class HTTP3ConnectionState:
    local_settings: dict[int, int] = field(default_factory=dict)
    remote_settings: dict[int, int] = field(default_factory=dict)
    goaway_stream_id: int | None = field(default=None)
    local_goaway_id: int | None = None
    peer_goaway_id: int | None = None
    peer_goaway_direction: str | None = None
    control_stream_opened: bool = False
    remote_control_stream_id: int | None = None
    remote_qpack_encoder_stream_id: int | None = None
    remote_qpack_decoder_stream_id: int | None = None
    remote_push_stream_ids: set[int] = field(default_factory=set)
    uni_streams: dict[int, HTTP3UniStreamState] = field(default_factory=dict)
    promised_pushes: dict[int, HTTP3PushPromiseState] = field(default_factory=dict)
    cancelled_push_ids: set[int] = field(default_factory=set)
    local_max_push_id: int | None = None
    peer_max_push_id: int | None = None
