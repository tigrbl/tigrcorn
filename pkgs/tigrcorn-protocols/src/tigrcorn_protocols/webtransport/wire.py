from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from hmac import compare_digest
from typing import Any, Callable, Iterable, Mapping, Sequence

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint


WEBTRANSPORT_UPGRADE_TOKEN = "webtransport"
HEADER_WT_AVAILABLE_PROTOCOLS = "wt-available-protocols"
HEADER_WT_PROTOCOL = "wt-protocol"
HEADER_WEBTRANSPORT_INIT = "webtransport-init"
HEADER_LEGACY_H3_DRAFT = "sec-webtransport-http3-draft"

SETTING_ENABLE_CONNECT_PROTOCOL = 0x08
SETTING_H3_DATAGRAM = 0x33
SETTING_ENABLE_WEBTRANSPORT_LEGACY = 0x2B603742
SETTING_WEBTRANSPORT_MAX_SESSIONS = 0x2B60
SETTING_WEBTRANSPORT_INITIAL_MAX_DATA = 0x2B61
SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_UNI = 0x2B62
SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_BIDI = 0x2B63
SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_UNI = 0x2B64
SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_BIDI = 0x2B65
SETTING_WT_MAX_SESSIONS = 0x14E9CD29

H3_FRAME_WEBTRANSPORT_STREAM = 0x41
H3_STREAM_TYPE_WEBTRANSPORT = 0x54
H3_ERROR_WT_APPLICATION_ERROR = 0x52E4A40FA8DB
H3_ERROR_WT_BUFFERED_STREAM_REJECTED = 0x3994BD84
H3_ERROR_WT_SESSION_GONE = 0x170D7B68

CAPSULE_DATAGRAM = 0x00
CAPSULE_WT_CLOSE_SESSION = 0x2843
CAPSULE_WT_DRAIN_SESSION = 0x78AE
CAPSULE_PADDING = 0x190B4D38
CAPSULE_WT_RESET_STREAM = 0x190B4D39
CAPSULE_WT_STOP_SENDING = 0x190B4D3A
CAPSULE_WT_STREAM = 0x190B4D3B
CAPSULE_WT_STREAM_FIN = 0x190B4D3C
CAPSULE_WT_MAX_DATA = 0x190B4D3D
CAPSULE_WT_MAX_STREAM_DATA = 0x190B4D3E
CAPSULE_WT_MAX_STREAMS_BIDI = 0x190B4D3F
CAPSULE_WT_MAX_STREAMS_UNI = 0x190B4D40
CAPSULE_WT_DATA_BLOCKED = 0x190B4D41
CAPSULE_WT_STREAM_DATA_BLOCKED = 0x190B4D42
CAPSULE_WT_STREAMS_BLOCKED_BIDI = 0x190B4D43
CAPSULE_WT_STREAMS_BLOCKED_UNI = 0x190B4D44

H2_SETTINGS_REGISTRY = {
    "SETTINGS_WEBTRANSPORT_MAX_SESSIONS": SETTING_WEBTRANSPORT_MAX_SESSIONS,
    "SETTINGS_WEBTRANSPORT_INITIAL_MAX_DATA": SETTING_WEBTRANSPORT_INITIAL_MAX_DATA,
    "SETTINGS_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_UNI": SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_UNI,
    "SETTINGS_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_BIDI": SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_BIDI,
    "SETTINGS_WEBTRANSPORT_INITIAL_MAX_STREAMS_UNI": SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_UNI,
    "SETTINGS_WEBTRANSPORT_INITIAL_MAX_STREAMS_BIDI": SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_BIDI,
}

H3_DRAFT13_REGISTRY = {
    "SETTINGS_WT_MAX_SESSIONS": SETTING_WT_MAX_SESSIONS,
    "WT_STREAM_FRAME": H3_FRAME_WEBTRANSPORT_STREAM,
    "WT_UNIDI_STREAM_TYPE": H3_STREAM_TYPE_WEBTRANSPORT,
    "WT_APPLICATION_ERROR": H3_ERROR_WT_APPLICATION_ERROR,
    "WT_BUFFERED_STREAM_REJECTED": H3_ERROR_WT_BUFFERED_STREAM_REJECTED,
    "WT_SESSION_GONE": H3_ERROR_WT_SESSION_GONE,
    "WT_CLOSE_SESSION": CAPSULE_WT_CLOSE_SESSION,
    "WT_DRAIN_SESSION": CAPSULE_WT_DRAIN_SESSION,
    "WT_MAX_STREAMS_BIDI": CAPSULE_WT_MAX_STREAMS_BIDI,
    "WT_MAX_STREAMS_UNI": CAPSULE_WT_MAX_STREAMS_UNI,
    "WT_STREAMS_BLOCKED_BIDI": CAPSULE_WT_STREAMS_BLOCKED_BIDI,
    "WT_STREAMS_BLOCKED_UNI": CAPSULE_WT_STREAMS_BLOCKED_UNI,
    "WT_MAX_DATA": CAPSULE_WT_MAX_DATA,
    "WT_DATA_BLOCKED": CAPSULE_WT_DATA_BLOCKED,
}

H2_CAPSULE_REGISTRY = {
    "DATAGRAM": CAPSULE_DATAGRAM,
    "PADDING": CAPSULE_PADDING,
    "WT_RESET_STREAM": CAPSULE_WT_RESET_STREAM,
    "WT_STOP_SENDING": CAPSULE_WT_STOP_SENDING,
    "WT_STREAM": CAPSULE_WT_STREAM,
    "WT_STREAM_FIN": CAPSULE_WT_STREAM_FIN,
    "WT_MAX_DATA": CAPSULE_WT_MAX_DATA,
    "WT_MAX_STREAM_DATA": CAPSULE_WT_MAX_STREAM_DATA,
    "WT_MAX_STREAMS_BIDI": CAPSULE_WT_MAX_STREAMS_BIDI,
    "WT_MAX_STREAMS_UNI": CAPSULE_WT_MAX_STREAMS_UNI,
    "WT_DATA_BLOCKED": CAPSULE_WT_DATA_BLOCKED,
    "WT_STREAM_DATA_BLOCKED": CAPSULE_WT_STREAM_DATA_BLOCKED,
    "WT_STREAMS_BLOCKED_BIDI": CAPSULE_WT_STREAMS_BLOCKED_BIDI,
    "WT_STREAMS_BLOCKED_UNI": CAPSULE_WT_STREAMS_BLOCKED_UNI,
    "WT_CLOSE_SESSION": CAPSULE_WT_CLOSE_SESSION,
    "WT_DRAIN_SESSION": CAPSULE_WT_DRAIN_SESSION,
}


class Carrier(str, Enum):
    H2 = "h2"
    H3 = "h3"


class StreamDirection(str, Enum):
    BIDI = "bidi"
    UNI = "uni"


class SessionState(str, Enum):
    CONNECTING = "connecting"
    OPEN = "open"
    DRAINING = "draining"
    CLOSED = "closed"


class WebTransportWireError(ProtocolError):
    """Raised when draft WebTransport wire validation fails closed."""


@dataclass(frozen=True, slots=True)
class Capsule:
    capsule_type: int
    payload: bytes = b""

    def encode(self) -> bytes:
        return encode_capsule(self.capsule_type, self.payload)


@dataclass(frozen=True, slots=True)
class WebTransportInit:
    max_stream_data_uni: int = 0
    max_stream_data_bidi: int = 0
    max_streams_uni: int = 0
    max_streams_bidi: int = 0
    max_data: int = 0

    @classmethod
    def from_h2_settings_and_header(
        cls,
        settings: Mapping[int, int],
        header: str | None = None,
    ) -> "WebTransportInit":
        values = {
            "max_data": int(settings.get(SETTING_WEBTRANSPORT_INITIAL_MAX_DATA, 0)),
            "max_stream_data_uni": int(settings.get(SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_UNI, 0)),
            "max_stream_data_bidi": int(settings.get(SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_BIDI, 0)),
            "max_streams_uni": int(settings.get(SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_UNI, 0)),
            "max_streams_bidi": int(settings.get(SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_BIDI, 0)),
        }
        if header:
            for key, value in parse_webtransport_init_header(header).items():
                values[key] = max(values[key], value)
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ConnectRequest:
    stream_id: int
    headers: Mapping[str, str]
    carrier: Carrier
    negotiated_settings: Mapping[int, int]
    allowed_origins: Sequence[str] = ()
    selected_protocol: str | None = None

    @property
    def session_id(self) -> str:
        return str(self.stream_id)


@dataclass(frozen=True, slots=True)
class ConnectDecision:
    accepted: bool
    status: int
    reason: str
    session_id: str | None = None
    response_headers: tuple[tuple[str, str], ...] = ()


@dataclass(slots=True)
class WebTransportFlowController:
    max_data: int = 0
    max_stream_data_uni: int = 0
    max_stream_data_bidi: int = 0
    max_streams_uni: int = 0
    max_streams_bidi: int = 0
    data_sent: int = 0
    streams_opened_uni: int = 0
    streams_opened_bidi: int = 0
    stream_data_sent: dict[int, int] = field(default_factory=dict)

    def allow_data(self, amount: int) -> None:
        if amount < 0:
            raise WebTransportWireError("flow-control amount must be non-negative")
        if self.max_data and self.data_sent + amount > self.max_data:
            raise WebTransportWireError("WT_MAX_DATA exceeded")
        self.data_sent += amount

    def allow_stream_data(self, stream_id: int, direction: StreamDirection, amount: int) -> None:
        if amount < 0:
            raise WebTransportWireError("flow-control amount must be non-negative")
        limit = self.max_stream_data_uni if direction is StreamDirection.UNI else self.max_stream_data_bidi
        current = self.stream_data_sent.get(stream_id, 0)
        if limit and current + amount > limit:
            raise WebTransportWireError("WT_MAX_STREAM_DATA exceeded")
        self.stream_data_sent[stream_id] = current + amount
        self.allow_data(amount)

    def open_stream(self, direction: StreamDirection) -> int:
        if direction is StreamDirection.UNI:
            if self.max_streams_uni and self.streams_opened_uni >= self.max_streams_uni:
                raise WebTransportWireError("WT_MAX_STREAMS uni exceeded")
            self.streams_opened_uni += 1
            return self.streams_opened_uni - 1
        if self.max_streams_bidi and self.streams_opened_bidi >= self.max_streams_bidi:
            raise WebTransportWireError("WT_MAX_STREAMS bidi exceeded")
        self.streams_opened_bidi += 1
        return self.streams_opened_bidi - 1

    def apply_flow_control_capsule(self, capsule: Capsule) -> None:
        try:
            values = list(decode_varints(capsule.payload))
        except (ProtocolError, ValueError) as exc:
            raise WebTransportWireError("malformed flow-control capsule") from exc
        if capsule.capsule_type == CAPSULE_WT_MAX_DATA:
            self.max_data = _single_value(values, "WT_MAX_DATA")
            return
        if capsule.capsule_type == CAPSULE_WT_MAX_STREAM_DATA:
            stream_id, limit = _two_values(values, "WT_MAX_STREAM_DATA")
            self.stream_data_sent.setdefault(stream_id, 0)
            if stream_id & 1:
                self.max_stream_data_uni = max(self.max_stream_data_uni, limit)
            else:
                self.max_stream_data_bidi = max(self.max_stream_data_bidi, limit)
            return
        if capsule.capsule_type == CAPSULE_WT_MAX_STREAMS_UNI:
            self.max_streams_uni = _single_value(values, "WT_MAX_STREAMS_UNI")
            return
        if capsule.capsule_type == CAPSULE_WT_MAX_STREAMS_BIDI:
            self.max_streams_bidi = _single_value(values, "WT_MAX_STREAMS_BIDI")
            return
        if capsule.capsule_type == CAPSULE_WT_DATA_BLOCKED:
            _single_value(values, "WT_DATA_BLOCKED")
            return
        if capsule.capsule_type == CAPSULE_WT_STREAM_DATA_BLOCKED:
            _two_values(values, "WT_STREAM_DATA_BLOCKED")
            return
        if capsule.capsule_type == CAPSULE_WT_STREAMS_BLOCKED_BIDI:
            _single_value(values, "WT_STREAMS_BLOCKED_BIDI")
            return
        if capsule.capsule_type == CAPSULE_WT_STREAMS_BLOCKED_UNI:
            _single_value(values, "WT_STREAMS_BLOCKED_UNI")
            return
        raise WebTransportWireError(f"unsupported flow-control capsule {capsule.capsule_type:#x}")


@dataclass(slots=True)
class WebTransportSession:
    session_id: str
    carrier: Carrier
    connect_stream_id: int
    origin: str | None
    path: str
    selected_protocol: str | None = None
    flow: WebTransportFlowController = field(default_factory=WebTransportFlowController)
    state: SessionState = SessionState.OPEN
    streams: dict[int, StreamDirection] = field(default_factory=dict)
    datagrams: list[bytes] = field(default_factory=list)
    close_code: int | None = None
    close_reason: str = ""

    def ensure_open(self) -> None:
        if self.state is SessionState.CLOSED:
            raise WebTransportWireError("WebTransport session is closed")

    def ensure_accepting_traffic(self) -> None:
        self.ensure_open()
        if self.state is SessionState.DRAINING:
            raise WebTransportWireError("WebTransport session is draining")


@dataclass(slots=True)
class BufferedItem:
    session_id: str
    kind: str
    payload: bytes


KeyingMaterialExporter = Callable[[str, bytes, int], bytes]


class WebTransportWireRuntime:
    def __init__(
        self,
        *,
        max_sessions: int,
        max_datagram_size: int = 1200,
        buffer_limit: int = 16,
        keying_material_exporter: KeyingMaterialExporter | None = None,
    ) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        if max_datagram_size < 1:
            raise ValueError("max_datagram_size must be positive")
        if buffer_limit < 0:
            raise ValueError("buffer_limit must be non-negative")
        self.max_sessions = max_sessions
        self.max_datagram_size = max_datagram_size
        self.buffer_limit = buffer_limit
        self.sessions: dict[str, WebTransportSession] = {}
        self.buffered: list[BufferedItem] = []
        self.goaway_stream_id: int | None = None
        self._keying_material_exporter = keying_material_exporter

    def accept(self, request: ConnectRequest) -> ConnectDecision:
        decision = validate_extended_connect(request)
        if not decision.accepted:
            return decision
        if self.goaway_stream_id is not None and request.stream_id > self.goaway_stream_id:
            return ConnectDecision(False, 421, "goaway-limit")
        if len(self.sessions) >= self.max_sessions:
            return ConnectDecision(False, 429, "max-sessions")
        session = WebTransportSession(
            session_id=decision.session_id or request.session_id,
            carrier=request.carrier,
            connect_stream_id=request.stream_id,
            origin=_header(request.headers, "origin"),
            path=_required_header(request.headers, ":path"),
            selected_protocol=request.selected_protocol,
            flow=_flow_from_request(request),
        )
        self.sessions[session.session_id] = session
        return decision

    def open_stream(self, session_id: str, stream_id: int, direction: StreamDirection) -> None:
        session = self._session(session_id)
        session.ensure_accepting_traffic()
        session.flow.open_stream(direction)
        session.streams[stream_id] = direction

    def receive_stream_data(self, session_id: str, stream_id: int, data: bytes, direction: StreamDirection) -> None:
        session = self._session(session_id)
        session.ensure_accepting_traffic()
        if stream_id not in session.streams:
            self.open_stream(session_id, stream_id, direction)
        session.flow.allow_stream_data(stream_id, direction, len(data))

    def receive_datagram(self, session_id: str, payload: bytes) -> None:
        session = self._session(session_id)
        session.ensure_accepting_traffic()
        if len(payload) > self.max_datagram_size:
            raise WebTransportWireError("datagram size exceeded")
        session.datagrams.append(payload)

    def buffer_before_session(self, session_id: str, kind: str, payload: bytes) -> None:
        if session_id in self.sessions:
            raise WebTransportWireError("session already established")
        if len(self.buffered) >= self.buffer_limit:
            raise WebTransportWireError("WT_BUFFERED_STREAM_REJECTED")
        self.buffered.append(BufferedItem(session_id=session_id, kind=kind, payload=payload))

    def flush_buffered(self, session_id: str) -> tuple[BufferedItem, ...]:
        ready = tuple(item for item in self.buffered if item.session_id == session_id)
        self.buffered = [item for item in self.buffered if item.session_id != session_id]
        return ready

    def apply_capsule(self, session_id: str, capsule: Capsule) -> dict[str, Any]:
        session = self._session(session_id)
        session.ensure_open()
        if capsule.capsule_type == CAPSULE_WT_CLOSE_SESSION:
            code, reason = decode_close_session_payload(capsule.payload)
            session.state = SessionState.CLOSED
            session.close_code = code
            session.close_reason = reason
            return {"event": "webtransport.close", "code": code, "reason": reason}
        if capsule.capsule_type == CAPSULE_WT_DRAIN_SESSION:
            session.state = SessionState.DRAINING
            return {"event": "webtransport.drain"}
        if capsule.capsule_type == CAPSULE_DATAGRAM:
            self.receive_datagram(session_id, capsule.payload)
            return {"event": "webtransport.datagram", "bytes": len(capsule.payload)}
        if capsule.capsule_type in {
            CAPSULE_WT_MAX_DATA,
            CAPSULE_WT_MAX_STREAM_DATA,
            CAPSULE_WT_MAX_STREAMS_BIDI,
            CAPSULE_WT_MAX_STREAMS_UNI,
            CAPSULE_WT_DATA_BLOCKED,
            CAPSULE_WT_STREAM_DATA_BLOCKED,
            CAPSULE_WT_STREAMS_BLOCKED_BIDI,
            CAPSULE_WT_STREAMS_BLOCKED_UNI,
        }:
            session.flow.apply_flow_control_capsule(capsule)
            return {"event": "webtransport.flow-control", "capsule_type": capsule.capsule_type}
        if capsule.capsule_type in {CAPSULE_WT_STREAM, CAPSULE_WT_STREAM_FIN}:
            stream_id, data = decode_stream_capsule_payload(capsule.payload)
            self.receive_stream_data(session_id, stream_id, data, StreamDirection.BIDI)
            return {"event": "webtransport.stream", "stream_id": stream_id, "fin": capsule.capsule_type == CAPSULE_WT_STREAM_FIN}
        if capsule.capsule_type in {CAPSULE_WT_RESET_STREAM, CAPSULE_WT_STOP_SENDING}:
            stream_id, error_code = decode_stream_error_payload(capsule.payload)
            session.streams.pop(stream_id, None)
            return {"event": "webtransport.stream.error", "stream_id": stream_id, "error_code": error_code}
        if capsule.capsule_type == CAPSULE_PADDING:
            return {"event": "webtransport.padding", "bytes": len(capsule.payload)}
        raise WebTransportWireError(f"unsupported capsule {capsule.capsule_type:#x}")

    def goaway(self, last_stream_id: int) -> None:
        if last_stream_id < 0:
            raise WebTransportWireError("GOAWAY stream id must be non-negative")
        self.goaway_stream_id = last_stream_id

    def keying_material_exporter(self, session_id: str, label: str, context: bytes, length: int) -> bytes:
        session = self._session(session_id)
        session.ensure_open()
        if session.carrier is not Carrier.H3:
            raise WebTransportWireError("keying material exporters require HTTP/3 over QUIC")
        if length < 1:
            raise WebTransportWireError("exporter length must be positive")
        if self._keying_material_exporter is not None:
            exported = self._keying_material_exporter(label, context, length)
            if len(exported) != length:
                raise WebTransportWireError("keying material exporter returned wrong length")
            return exported
        seed = f"{session.session_id}:{label}:".encode("ascii") + context
        digest = sha256(seed).digest()
        output = bytearray()
        while len(output) < length:
            digest = sha256(digest + seed).digest()
            output.extend(digest)
        return bytes(output[:length])

    def _session(self, session_id: str) -> WebTransportSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise WebTransportWireError("WT_SESSION_GONE")
        return session


def h2_webtransport_settings(max_sessions: int, init: WebTransportInit | None = None) -> dict[int, int]:
    if max_sessions < 0:
        raise ValueError("max_sessions must be non-negative")
    init = init or WebTransportInit()
    return {
        SETTING_ENABLE_CONNECT_PROTOCOL: 1,
        SETTING_WEBTRANSPORT_MAX_SESSIONS: max_sessions,
        SETTING_WEBTRANSPORT_INITIAL_MAX_DATA: init.max_data,
        SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_UNI: init.max_stream_data_uni,
        SETTING_WEBTRANSPORT_INITIAL_MAX_STREAM_DATA_BIDI: init.max_stream_data_bidi,
        SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_UNI: init.max_streams_uni,
        SETTING_WEBTRANSPORT_INITIAL_MAX_STREAMS_BIDI: init.max_streams_bidi,
    }


def h3_draft13_settings(max_sessions: int) -> dict[int, int]:
    if max_sessions < 0:
        raise ValueError("max_sessions must be non-negative")
    return {
        SETTING_ENABLE_CONNECT_PROTOCOL: 1,
        SETTING_H3_DATAGRAM: 1,
        SETTING_WT_MAX_SESSIONS: max_sessions,
    }


def h3_compat_settings(max_sessions: int) -> dict[int, int]:
    settings = h3_draft13_settings(max_sessions)
    settings[SETTING_ENABLE_WEBTRANSPORT_LEGACY] = 1
    return settings


def h2_transport_capable(settings: Mapping[int, int]) -> bool:
    return (
        int(settings.get(SETTING_ENABLE_CONNECT_PROTOCOL, 0)) == 1
        and int(settings.get(SETTING_WEBTRANSPORT_MAX_SESSIONS, 0)) > 0
    )


def h3_draft13_transport_capable(settings: Mapping[int, int]) -> bool:
    return (
        int(settings.get(SETTING_ENABLE_CONNECT_PROTOCOL, 0)) == 1
        and int(settings.get(SETTING_H3_DATAGRAM, 0)) == 1
        and int(settings.get(SETTING_WT_MAX_SESSIONS, 0)) > 0
    )


def validate_extended_connect(request: ConnectRequest) -> ConnectDecision:
    headers = request.headers
    if request.carrier is Carrier.H2 and not h2_transport_capable(request.negotiated_settings):
        return ConnectDecision(False, 421, "webtransport-h2-settings-not-negotiated")
    if request.carrier is Carrier.H3 and not h3_draft13_transport_capable(request.negotiated_settings):
        return ConnectDecision(False, 421, "webtransport-h3-draft13-settings-not-negotiated")
    if _required_header(headers, ":method").upper() != "CONNECT":
        return ConnectDecision(False, 405, "method")
    if _required_header(headers, ":protocol").lower() != WEBTRANSPORT_UPGRADE_TOKEN:
        return ConnectDecision(False, 406, "protocol")
    if _required_header(headers, ":scheme").lower() != "https":
        return ConnectDecision(False, 400, "scheme")
    if not _required_header(headers, ":authority"):
        return ConnectDecision(False, 400, "authority")
    if not _required_header(headers, ":path").startswith("/"):
        return ConnectDecision(False, 400, "path")
    origin = _header(headers, "origin")
    if request.allowed_origins and origin not in request.allowed_origins:
        return ConnectDecision(False, 403, "origin")
    response_headers: list[tuple[str, str]] = []
    if request.selected_protocol is not None:
        response_headers.append(("WT-Protocol", request.selected_protocol))
    return ConnectDecision(True, 200, "accepted", session_id=request.session_id, response_headers=tuple(response_headers))


def select_wt_protocol(available: Sequence[str], selected: str | None) -> str | None:
    if selected is None:
        return available[0] if available else None
    if selected not in available:
        raise WebTransportWireError("WT-Protocol must be listed in WT-Available-Protocols")
    return selected


def encode_protocol_headers(available: Sequence[str], selected: str | None = None) -> dict[str, str]:
    headers = {"WT-Available-Protocols": ", ".join(available)}
    chosen = select_wt_protocol(available, selected)
    if chosen is not None:
        headers["WT-Protocol"] = chosen
    return headers


def parse_protocol_header(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def parse_webtransport_init_header(value: str) -> dict[str, int]:
    result: dict[str, int] = {}
    key_map = {
        "d": "max_data",
        "u": "max_stream_data_uni",
        "b": "max_stream_data_bidi",
        "su": "max_streams_uni",
        "sb": "max_streams_bidi",
    }
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" not in part:
            raise WebTransportWireError("invalid WebTransport-Init item")
        raw_key, raw_value = part.split("=", 1)
        key = key_map.get(raw_key.strip())
        if key is None:
            continue
        try:
            parsed = int(raw_value.strip())
        except ValueError as exc:
            raise WebTransportWireError("invalid WebTransport-Init integer") from exc
        if parsed < 0:
            raise WebTransportWireError("WebTransport-Init values must be non-negative")
        result[key] = parsed
    return result


def encode_capsule(capsule_type: int, payload: bytes = b"") -> bytes:
    return encode_quic_varint(capsule_type) + encode_quic_varint(len(payload)) + payload


def decode_capsule(data: bytes, offset: int = 0) -> tuple[Capsule, int]:
    try:
        capsule_type, offset = decode_quic_varint(data, offset)
        length, offset = decode_quic_varint(data, offset)
    except (ProtocolError, ValueError) as exc:
        raise WebTransportWireError("malformed capsule header") from exc
    end = offset + length
    if end > len(data):
        raise WebTransportWireError("truncated capsule payload")
    return Capsule(capsule_type, data[offset:end]), end


def parse_capsules(data: bytes) -> tuple[Capsule, ...]:
    capsules: list[Capsule] = []
    offset = 0
    while offset < len(data):
        capsule, offset = decode_capsule(data, offset)
        capsules.append(capsule)
    return tuple(capsules)


def encode_varints(*values: int) -> bytes:
    out = bytearray()
    for value in values:
        out.extend(encode_quic_varint(value))
    return bytes(out)


def decode_varints(payload: bytes) -> Iterable[int]:
    offset = 0
    while offset < len(payload):
        value, offset = decode_quic_varint(payload, offset)
        yield value


def encode_stream_capsule(stream_id: int, data: bytes, *, fin: bool = False) -> Capsule:
    capsule_type = CAPSULE_WT_STREAM_FIN if fin else CAPSULE_WT_STREAM
    return Capsule(capsule_type, encode_quic_varint(stream_id) + data)


def decode_stream_capsule_payload(payload: bytes) -> tuple[int, bytes]:
    try:
        stream_id, offset = decode_quic_varint(payload, 0)
    except (ProtocolError, ValueError) as exc:
        raise WebTransportWireError("malformed WT_STREAM capsule") from exc
    return stream_id, payload[offset:]


def encode_stream_error_payload(stream_id: int, error_code: int) -> bytes:
    return encode_varints(stream_id, error_code)


def decode_stream_error_payload(payload: bytes) -> tuple[int, int]:
    return _two_values(list(decode_varints(payload)), "WT_STREAM_ERROR")


def encode_close_session_payload(code: int, reason: str = "") -> bytes:
    reason_bytes = reason.encode("utf-8")
    return code.to_bytes(4, "big") + reason_bytes


def decode_close_session_payload(payload: bytes) -> tuple[int, str]:
    if len(payload) < 4:
        raise WebTransportWireError("WT_CLOSE_SESSION payload too short")
    return int.from_bytes(payload[:4], "big"), payload[4:].decode("utf-8", errors="replace")


def encode_h3_bidi_prefix(session_id: int) -> bytes:
    return encode_varints(H3_FRAME_WEBTRANSPORT_STREAM, session_id)


def decode_h3_bidi_prefix(payload: bytes) -> tuple[int, bytes]:
    values = []
    offset = 0
    for _ in range(2):
        try:
            value, offset = decode_quic_varint(payload, offset)
        except (ProtocolError, ValueError) as exc:
            raise WebTransportWireError("malformed H3 WebTransport bidi prefix") from exc
        values.append(value)
    if values[0] != H3_FRAME_WEBTRANSPORT_STREAM:
        raise WebTransportWireError("missing H3 WT_STREAM frame prefix")
    return values[1], payload[offset:]


def encode_h3_unidi_prefix(session_id: int) -> bytes:
    return encode_varints(H3_STREAM_TYPE_WEBTRANSPORT, session_id)


def decode_h3_unidi_prefix(payload: bytes) -> tuple[int, bytes]:
    values = []
    offset = 0
    for _ in range(2):
        try:
            value, offset = decode_quic_varint(payload, offset)
        except (ProtocolError, ValueError) as exc:
            raise WebTransportWireError("malformed H3 WebTransport unidi prefix") from exc
        values.append(value)
    if values[0] != H3_STREAM_TYPE_WEBTRANSPORT:
        raise WebTransportWireError("missing H3 WT unidi stream type")
    return values[1], payload[offset:]


def encode_h3_datagram_payload(connect_stream_id: int, data: bytes) -> bytes:
    return encode_quic_varint(connect_stream_id // 4) + data


def decode_h3_datagram_payload(payload: bytes) -> tuple[int, bytes]:
    try:
        quarter_stream_id, offset = decode_quic_varint(payload, 0)
    except (ProtocolError, ValueError) as exc:
        raise WebTransportWireError("malformed H3 datagram payload") from exc
    return int(quarter_stream_id) * 4, payload[offset:]


def carrier_for_selection(transport: str, protocol: str) -> Carrier:
    normalized_transport = transport.lower()
    normalized_protocol = protocol.lower().replace("-", "_")
    if normalized_protocol in {"webtransport_h2", "webtransport_http2"}:
        if normalized_transport not in {"tcp", "tls"}:
            raise WebTransportWireError("WebTransport over HTTP/2 requires a TCP/TLS listener")
        return Carrier.H2
    if normalized_protocol in {"webtransport", "webtransport_h3", "webtransport_http3"}:
        if normalized_transport != "udp":
            raise WebTransportWireError("WebTransport over HTTP/3 requires a UDP listener")
        return Carrier.H3
    raise WebTransportWireError("unsupported WebTransport carrier selection")


def constant_registry_snapshot() -> dict[str, dict[str, int]]:
    return {
        "h2_settings": dict(H2_SETTINGS_REGISTRY),
        "h2_capsules": dict(H2_CAPSULE_REGISTRY),
        "h3_draft13": dict(H3_DRAFT13_REGISTRY),
    }


def _flow_from_request(request: ConnectRequest) -> WebTransportFlowController:
    init = WebTransportInit.from_h2_settings_and_header(
        request.negotiated_settings,
        _header(request.headers, HEADER_WEBTRANSPORT_INIT),
    )
    return WebTransportFlowController(
        max_data=init.max_data,
        max_stream_data_uni=init.max_stream_data_uni,
        max_stream_data_bidi=init.max_stream_data_bidi,
        max_streams_uni=init.max_streams_uni,
        max_streams_bidi=init.max_streams_bidi,
    )


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return str(value)
    return None


def _required_header(headers: Mapping[str, str], name: str) -> str:
    value = _header(headers, name)
    return "" if value is None else value


def _single_value(values: Sequence[int], context: str) -> int:
    if len(values) != 1:
        raise WebTransportWireError(f"{context} requires one integer")
    return values[0]


def _two_values(values: Sequence[int], context: str) -> tuple[int, int]:
    if len(values) != 2:
        raise WebTransportWireError(f"{context} requires two integers")
    return values[0], values[1]


def exporter_matches(left: bytes, right: bytes) -> bool:
    return compare_digest(left, right)


__all__ = [
    "CAPSULE_DATAGRAM",
    "CAPSULE_PADDING",
    "CAPSULE_WT_CLOSE_SESSION",
    "CAPSULE_WT_DATA_BLOCKED",
    "CAPSULE_WT_DRAIN_SESSION",
    "CAPSULE_WT_MAX_DATA",
    "CAPSULE_WT_MAX_STREAMS_BIDI",
    "CAPSULE_WT_MAX_STREAMS_UNI",
    "CAPSULE_WT_MAX_STREAM_DATA",
    "CAPSULE_WT_RESET_STREAM",
    "CAPSULE_WT_STOP_SENDING",
    "CAPSULE_WT_STREAM",
    "CAPSULE_WT_STREAMS_BLOCKED_BIDI",
    "CAPSULE_WT_STREAMS_BLOCKED_UNI",
    "CAPSULE_WT_STREAM_DATA_BLOCKED",
    "Carrier",
    "ConnectDecision",
    "ConnectRequest",
    "H2_CAPSULE_REGISTRY",
    "H2_SETTINGS_REGISTRY",
    "H3_DRAFT13_REGISTRY",
    "H3_ERROR_WT_APPLICATION_ERROR",
    "H3_ERROR_WT_BUFFERED_STREAM_REJECTED",
    "H3_ERROR_WT_SESSION_GONE",
    "H3_FRAME_WEBTRANSPORT_STREAM",
    "H3_STREAM_TYPE_WEBTRANSPORT",
    "HEADER_LEGACY_H3_DRAFT",
    "HEADER_WEBTRANSPORT_INIT",
    "HEADER_WT_AVAILABLE_PROTOCOLS",
    "HEADER_WT_PROTOCOL",
    "SETTING_ENABLE_CONNECT_PROTOCOL",
    "SETTING_ENABLE_WEBTRANSPORT_LEGACY",
    "SETTING_H3_DATAGRAM",
    "SETTING_WEBTRANSPORT_MAX_SESSIONS",
    "SETTING_WT_MAX_SESSIONS",
    "SessionState",
    "StreamDirection",
    "WebTransportFlowController",
    "WebTransportInit",
    "WebTransportWireError",
    "WebTransportWireRuntime",
    "KeyingMaterialExporter",
    "carrier_for_selection",
    "constant_registry_snapshot",
    "decode_capsule",
    "decode_close_session_payload",
    "decode_h3_bidi_prefix",
    "decode_h3_datagram_payload",
    "decode_h3_unidi_prefix",
    "decode_stream_capsule_payload",
    "encode_capsule",
    "encode_close_session_payload",
    "encode_h3_bidi_prefix",
    "encode_h3_datagram_payload",
    "encode_h3_unidi_prefix",
    "encode_protocol_headers",
    "encode_stream_capsule",
    "encode_stream_error_payload",
    "exporter_matches",
    "h2_transport_capable",
    "h2_webtransport_settings",
    "h3_compat_settings",
    "h3_draft13_settings",
    "h3_draft13_transport_capable",
    "parse_capsules",
    "parse_protocol_header",
    "parse_webtransport_init_header",
    "select_wt_protocol",
    "validate_extended_connect",
]
