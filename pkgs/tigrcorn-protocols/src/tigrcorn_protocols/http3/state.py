from __future__ import annotations

from dataclasses import dataclass, field


HTTP3_REQUEST_PHASE_INITIAL = 'initial'
HTTP3_REQUEST_PHASE_DATA = 'data'
HTTP3_REQUEST_PHASE_TRAILERS = 'trailers'

HTTP3RequestPhase_INITIAL = HTTP3_REQUEST_PHASE_INITIAL
HTTP3RequestPhase_DATA = HTTP3_REQUEST_PHASE_DATA
HTTP3RequestPhase_TRAILERS = HTTP3_REQUEST_PHASE_TRAILERS

HTTP3_REQUEST_TRANSITION_TABLE: tuple[dict[str, object], ...] = (
    {'from': 'initial', 'event': 'HEADERS', 'to': 'data', 'notes': 'initial request header section decoded successfully'},
    {'from': 'initial', 'event': 'HEADERS (QPACK blocked)', 'to': 'initial', 'notes': 'blocked section is preserved until encoder instructions arrive'},
    {'from': 'initial', 'event': 'DATA', 'to': 'error', 'notes': 'DATA before initial HEADERS is forbidden'},
    {'from': 'data', 'event': 'DATA', 'to': 'data', 'notes': 'body payload accumulates and content-length accounting advances'},
    {'from': 'data', 'event': 'HEADERS', 'to': 'trailers', 'notes': 'trailing header section closes the data phase'},
    {'from': 'trailers', 'event': 'DATA', 'to': 'error', 'notes': 'DATA after trailers is forbidden'},
    {'from': 'initial|data|trailers', 'event': 'FIN + complete parse + validators satisfied', 'to': 'ready', 'notes': 'request is ready only when fin is seen, initial headers exist, no blocked sections remain, and content-length matches'},
)

HTTP3_CONTROL_STREAM_RULES: tuple[dict[str, object], ...] = (
    {'rule': 'single-control-stream', 'error_code': 'H3_STREAM_CREATION_ERROR', 'notes': 'peer must not open more than one control stream'},
    {'rule': 'control-stream-begins-with-settings', 'error_code': 'H3_MISSING_SETTINGS', 'notes': 'first frame on control stream must be SETTINGS'},
    {'rule': 'duplicate-settings-forbidden', 'error_code': 'H3_FRAME_UNEXPECTED', 'notes': 'second SETTINGS frame is rejected'},
    {'rule': 'control-stream-close-is-fatal', 'error_code': 'H3_CLOSED_CRITICAL_STREAM', 'notes': 'control stream cannot be closed'},
    {'rule': 'request-frames-forbidden-on-control-stream', 'error_code': 'H3_FRAME_UNEXPECTED', 'notes': 'HEADERS, DATA, and PUSH_PROMISE are not valid control-stream frames'},
    {'rule': 'goaway-id-must-not-increase', 'error_code': 'H3_ID_ERROR', 'notes': 'successive GOAWAY identifiers are monotonic non-increasing'},
    {'rule': 'server-goaway-id-must-name-client-bidi-stream', 'error_code': 'H3_ID_ERROR', 'notes': 'server GOAWAY identifier must reference a client-initiated bidirectional stream id'},
    {'rule': 'server-cannot-send-max-push-id', 'error_code': 'H3_FRAME_UNEXPECTED', 'notes': 'MAX_PUSH_ID is only valid from the client'},
)

HTTP3_QPACK_ACCOUNTING_RULES: tuple[dict[str, object], ...] = (
    {'rule': 'blocked-header-sections-are-retained', 'notes': 'request body and partial parse state are preserved until QPACK unblocks'},
    {'rule': 'encoder-stream-errors-map-to-encoder-stream-error', 'notes': 'invalid encoder stream payload is surfaced as QPACK_ENCODER_STREAM_ERROR'},
    {'rule': 'decoder-stream-errors-map-to-decoder-stream-error', 'notes': 'invalid decoder stream payload is surfaced as QPACK_DECODER_STREAM_ERROR'},
    {'rule': 'field-section-errors-map-to-decompression-failed', 'notes': 'bad field sections surface as QPACK_DECOMPRESSION_FAILED'},
)


def http3_request_transition_table() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in HTTP3_REQUEST_TRANSITION_TABLE)


def http3_control_stream_rule_table() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in HTTP3_CONTROL_STREAM_RULES)


def http3_qpack_accounting_rule_table() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in HTTP3_QPACK_ACCOUNTING_RULES)


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
    informational_headers: list[list[tuple[bytes, bytes]]] = field(default_factory=list)
    trailers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body_parts: list[bytes] = field(default_factory=list)
    ended: bool = False
    parse_buffer: bytearray = field(default_factory=bytearray)
    blocked_header_sections: list[HTTP3BlockedSection] = field(default_factory=list)
    phase: str = HTTP3_REQUEST_PHASE_INITIAL
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
