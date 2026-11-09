from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from tigrcorn_core.errors import ProtocolError
from tigrcorn_transports.quic.recovery import QuicLossRecovery

PACKET_SPACE_INITIAL = 'initial'
PACKET_SPACE_HANDSHAKE = 'handshake'
PACKET_SPACE_APPLICATION = 'application'
PACKET_SPACE_ZERO_RTT = '0rtt'

TRANSPORT_ERROR_NO_ERROR = 0x00
TRANSPORT_ERROR_INTERNAL_ERROR = 0x01
TRANSPORT_ERROR_PROTOCOL_VIOLATION = 0x0A
TRANSPORT_ERROR_INVALID_TOKEN = 0x0B
TRANSPORT_ERROR_APPLICATION_ERROR = 0x0C
TRANSPORT_ERROR_TRANSPORT_PARAMETER = 0x08

_TOKEN_FORMAT_VERSION = 1
_TOKEN_PURPOSE_RETRY = 1
_TOKEN_PURPOSE_NEW_TOKEN = 2
_TOKEN_MAC_LENGTH = 16
_DEFAULT_PATH_KEY = '__default__'
_TIMER_ACK = 'ack'
_TIMER_LOSS = 'loss'
_TIMER_PTO = 'pto'
_ACK_DELAY_DEFAULT = 0.025
_MIN_INITIAL_DATAGRAM_SIZE = 1200

QUIC_CONNECTION_STATE_TRANSITION_TABLE: tuple[dict[str, object], ...] = (
    {'from': 'new', 'event': 'build_initial|send_crypto_data|send_early_stream_data', 'to': 'establishing', 'notes': 'connection leaves idle/new state once handshake or 0-RTT data is emitted'},
    {'from': 'new', 'event': 'handle_version_negotiation(match)', 'to': 'version_negotiated', 'notes': 'client selected an alternate supported version'},
    {'from': 'new', 'event': 'handle_version_negotiation(no-match)', 'to': 'version_negotiation_failed', 'notes': 'no mutually supported version remained'},
    {'from': 'establishing', 'event': 'stream-data-send', 'to': 'established', 'notes': '1-RTT stream transmission implies established application state'},
    {'from': 'establishing', 'event': 'handshake_done|handshake_complete|stream-receive', 'to': 'established', 'notes': 'handshake completion and 1-RTT traffic converge on established'},
    {'from': 'established', 'event': 'connection_close', 'to': 'closing', 'notes': 'local protocol violations or explicit close enter closing'},
    {'from': 'established', 'event': 'peer_connection_close', 'to': 'draining', 'notes': 'peer close moves runtime to draining'},
    {'from': 'any-active', 'event': 'stateless_reset', 'to': 'closed', 'notes': 'validated stateless reset closes the connection immediately'},
)

QUIC_TRANSPORT_ERROR_MATRIX: tuple[dict[str, object], ...] = (
    {'name': 'NO_ERROR', 'code': TRANSPORT_ERROR_NO_ERROR, 'trigger': 'graceful close with no transport error'},
    {'name': 'INTERNAL_ERROR', 'code': TRANSPORT_ERROR_INTERNAL_ERROR, 'trigger': 'implementation-internal failure mapped to transport close'},
    {'name': 'TRANSPORT_PARAMETER_ERROR', 'code': TRANSPORT_ERROR_TRANSPORT_PARAMETER, 'trigger': 'invalid or forbidden transport parameter combinations'},
    {'name': 'PROTOCOL_VIOLATION', 'code': TRANSPORT_ERROR_PROTOCOL_VIOLATION, 'trigger': 'frame legality or packet-sequencing invariant failure'},
    {'name': 'INVALID_TOKEN', 'code': TRANSPORT_ERROR_INVALID_TOKEN, 'trigger': 'Retry or NEW_TOKEN validation failure'},
    {'name': 'APPLICATION_ERROR', 'code': TRANSPORT_ERROR_APPLICATION_ERROR, 'trigger': 'application close surfaced through QUIC transport'},
)


def quic_connection_state_table() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in QUIC_CONNECTION_STATE_TRANSITION_TABLE)



def quic_transport_error_matrix() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in QUIC_TRANSPORT_ERROR_MATRIX)


QUIC_FLOW_CONTROL_EVIDENCE_MAP: dict[str, tuple[str, ...]] = {
    'credit-exhaustion': ('FRAME_DATA_BLOCKED', 'MAX_DATA'),
    'replenishment': ('MAX_DATA', 'MAX_STREAM_DATA'),
    'stream-level-backpressure': ('STREAM_DATA_BLOCKED', 'MAX_STREAM_DATA'),
    'connection-level-backpressure': ('DATA_BLOCKED', 'MAX_DATA'),
}


def flow_control_evidence_map() -> dict[str, tuple[str, ...]]:
    return dict(QUIC_FLOW_CONTROL_EVIDENCE_MAP)



@dataclass(slots=True)
class QuicEvent:
    kind: str
    stream_id: int | None = None
    data: bytes = b''
    fin: bool = False
    packet_number: int | None = None
    packet_space: str | None = None
    detail: Any = None


@dataclass(slots=True)
class _CongestionState:
    bytes_in_flight: int = 0
    congestion_window: int = 12_000
    ssthresh: int = 2**31 - 1


@dataclass(slots=True)
class _QuicPacketNumberSpaces:
    initial_send: int = 0
    handshake_send: int = 0
    application_send: int = 0
    initial_largest_received: int = -1
    handshake_largest_received: int = -1
    application_largest_received: int = -1


@dataclass(slots=True)
class _CryptoReassemblyBuffer:
    contiguous: bytearray = field(default_factory=bytearray)
    pending: dict[int, bytes] = field(default_factory=dict)

    def _store_pending(self, offset: int, data: bytes) -> None:
        existing = self.pending.get(offset)
        if existing is None or len(existing) < len(data):
            self.pending[offset] = data

    def _merge_pending(self, newly_available: bytearray) -> None:
        while True:
            start = len(self.contiguous)
            chunk = self.pending.pop(start, None)
            if chunk is None:
                break
            self.contiguous.extend(chunk)
            newly_available.extend(chunk)

    def apply(self, offset: int, data: bytes) -> bytes:
        if offset < 0:
            raise ProtocolError('negative QUIC CRYPTO offset')
        newly_available = bytearray()
        contiguous_length = len(self.contiguous)
        if offset > contiguous_length:
            self._store_pending(offset, bytes(data))
            return b''
        if offset < contiguous_length:
            overlap = contiguous_length - offset
            if overlap >= len(data):
                return b''
            suffix = data[overlap:]
            self.contiguous.extend(suffix)
            newly_available.extend(suffix)
            self._merge_pending(newly_available)
            return bytes(newly_available)
        self.contiguous.extend(data)
        newly_available.extend(data)
        self._merge_pending(newly_available)
        return bytes(newly_available)


@dataclass(slots=True)
class _PacketSpaceState:
    name: str
    send: int = 0
    largest_received: int = -1
    received_packets: set[int] = field(default_factory=set)
    received_packet_times: dict[int, float] = field(default_factory=dict)
    crypto_send_offset: int = 0
    crypto_receive: _CryptoReassemblyBuffer = field(default_factory=_CryptoReassemblyBuffer)
    pending_ack_eliciting: int = 0
    ack_deadline: float | None = None


@dataclass(slots=True)
class _TokenInfo:
    purpose: int
    issued_at_ms: int
    address: tuple[str, int] | None
    original_destination_connection_id: bytes
    retry_source_connection_id: bytes


@dataclass(slots=True)
class _PathRuntime:
    key: Any
    addr: tuple[str, int] | None
    recovery: QuicLossRecovery
    max_udp_payload_size: int


@dataclass(slots=True)
class _SentPacketMeta:
    packet_space: str
    packet_number: int
    frames: list[object]
    raw: bytes
    path_key: Any
    token: bytes | None = None
    ack_eliciting: bool = True
    is_pto_probe: bool = False
    transmitted: bool = True


@dataclass(slots=True)
class _ScheduledFrameSpec:
    packet_space: str
    frames: list[object]
    path_key: Any = _DEFAULT_PATH_KEY
    token: bytes | None = None
    is_pto_probe: bool = False



def _current_time_ms() -> int:
    return int(time.time() * 1000)



def _serialize_address(addr: tuple[str, int] | None) -> bytes:
    if addr is None:
        return b''
    host, port = addr
    host_bytes = host.encode('utf-8')
    if len(host_bytes) > 0xFFFF:
        raise ValueError('address is too large to encode in a QUIC token')
    return len(host_bytes).to_bytes(2, 'big') + host_bytes + int(port).to_bytes(2, 'big', signed=False)



def _parse_serialized_address(data: bytes) -> tuple[str, int]:
    if len(data) < 4:
        raise ProtocolError('truncated serialized address in QUIC token')
    host_length = int.from_bytes(data[:2], 'big')
    if 2 + host_length + 2 != len(data):
        raise ProtocolError('invalid serialized address in QUIC token')
    host = data[2:2 + host_length].decode('utf-8')
    port = int.from_bytes(data[2 + host_length:], 'big')
    return host, port

__all__ = [name for name in globals() if not name.startswith("__")]
