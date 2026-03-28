from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from tigrcorn.errors import ProtocolError
from tigrcorn.transports.quic.crypto import (
    QuicPacketProtectionKeys,
    derive_initial_packet_protection_keys,
    derive_quic_packet_protection_keys,
    derive_secret,
    generate_connection_id,
    protect_quic_packet,
    unprotect_quic_packet,
    update_quic_secret,
)
from tigrcorn.transports.quic.flow import QuicFlowControl
from tigrcorn.transports.quic.handshake import HandshakeFlight, QuicTlsHandshakeDriver, TlsAlertError, TransportParameters
from tigrcorn.transports.quic.packets import (
    QuicLongHeaderPacket,
    QuicLongHeaderType,
    QuicRetryPacket,
    QuicShortHeaderPacket,
    QuicStatelessResetPacket,
    QuicVersionNegotiationPacket,
    coalesce_packets,
    decode_packet,
    split_coalesced_packets,
)
from tigrcorn.transports.quic.recovery import QuicLossRecovery
from tigrcorn.transports.quic.scheduler import QuicTimerWheel
from tigrcorn.transports.quic.streams import (
    FRAME_ACK,
    FRAME_CONNECTION_CLOSE,
    FRAME_CONNECTION_CLOSE_APP,
    FRAME_PADDING,
    FRAME_PING,
    QuicAckFrame,
    QuicConnectionCloseFrame,
    QuicCryptoFrame,
    QuicDataBlockedFrame,
    QuicHandshakeDoneFrame,
    QuicMaxDataFrame,
    QuicMaxStreamDataFrame,
    QuicMaxStreamsFrame,
    QuicNewConnectionIdFrame,
    QuicNewTokenFrame,
    QuicPathChallengeFrame,
    QuicPathResponseFrame,
    QuicResetStreamFrame,
    QuicRetireConnectionIdFrame,
    QuicStopSendingFrame,
    QuicStreamDataBlockedFrame,
    QuicStreamFrame,
    QuicStreamManager,
    QuicStreamsBlockedFrame,
    decode_frame,
    encode_frame,
    frame_type_value,
    stream_is_local_initiated,
    stream_is_unidirectional,
    validate_frame_for_packet_space,
    validate_frames_for_packet_space,
)
from tigrcorn.utils.bytes import decode_quic_varint

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


class QuicConnection:
    def __init__(
        self,
        *,
        is_client: bool = False,
        version: int = 1,
        secret: bytes | None = None,
        local_cid: bytes | None = None,
        remote_cid: bytes | None = None,
        supported_versions: Sequence[int] | None = None,
        require_retry: bool = False,
        retry_token_lifetime_ms: int = 10_000,
        new_token_lifetime_ms: int = 7 * 24 * 60 * 60 * 1000,
        max_datagram_size: int = 1200,
    ) -> None:
        self.is_client = is_client
        self.version = version
        self.supported_versions = tuple(dict.fromkeys(tuple(supported_versions or (version,)) + (version,)))
        self.local_cid = generate_connection_id() if local_cid is None else local_cid
        self.remote_cid = generate_connection_id() if (is_client and remote_cid is None) else remote_cid
        self.secret = secret or derive_secret(self.local_cid, b'tigrcorn-quic')
        self.max_datagram_size = max(max_datagram_size, 1200)
        self.require_retry = require_retry
        self.retry_token_lifetime_ms = retry_token_lifetime_ms
        self.new_token_lifetime_ms = new_token_lifetime_ms
        self._packet_spaces: dict[str, _PacketSpaceState] = {
            PACKET_SPACE_INITIAL: _PacketSpaceState(name=PACKET_SPACE_INITIAL),
            PACKET_SPACE_HANDSHAKE: _PacketSpaceState(name=PACKET_SPACE_HANDSHAKE),
            PACKET_SPACE_APPLICATION: _PacketSpaceState(name=PACKET_SPACE_APPLICATION),
        }
        self.packet_numbers = _QuicPacketNumberSpaces()
        self._client_application_secret = derive_secret(self.secret, b'client 1rtt')
        self._server_application_secret = derive_secret(self.secret, b'server 1rtt')
        self.client_1rtt_keys = derive_quic_packet_protection_keys(self._client_application_secret)
        self.server_1rtt_keys = derive_quic_packet_protection_keys(self._server_application_secret)
        self._client_handshake_secret: bytes | None = None
        self._server_handshake_secret: bytes | None = None
        self.client_handshake_keys: QuicPacketProtectionKeys | None = None
        self.server_handshake_keys: QuicPacketProtectionKeys | None = None
        self.client_0rtt_keys: QuicPacketProtectionKeys | None = None
        self._handshake_traffic_installed = False
        self._application_traffic_installed = False
        self._send_key_phase = 0
        self._recv_key_phase = 0
        self.state = 'new'
        self.flow = QuicFlowControl(local_is_client=is_client)
        self.streams = QuicStreamManager(local_is_client=is_client)
        self.last_acked = -1
        self.congestion = _CongestionState()
        self._path_states: dict[Any, _PathRuntime] = {
            _DEFAULT_PATH_KEY: _PathRuntime(
                key=_DEFAULT_PATH_KEY,
                addr=None,
                recovery=QuicLossRecovery(max_datagram_size=self.max_datagram_size),
            )
        }
        self._active_path_key: Any = _DEFAULT_PATH_KEY
        self.recovery = self._path_states[_DEFAULT_PATH_KEY].recovery
        self._timer_wheel = QuicTimerWheel()
        self._sent_packets: dict[tuple[str, int], _SentPacketMeta] = {}
        self._wire_datagram_packets: dict[bytes, list[tuple[str, int]]] = {}
        self._scheduled_specs: list[_ScheduledFrameSpec] = []
        self.path_challenges: set[bytes] = set()
        self.retire_connection_ids: list[int] = []
        self.handshake_driver: QuicTlsHandshakeDriver | None = None
        self._pending_handshake_datagrams: list[bytes] = []
        self.bytes_received = 0
        self.bytes_sent = 0
        self.address_validated = is_client
        self.connection_id_sequence = 0
        self.issued_connection_ids: dict[int, tuple[bytes, bytes]] = {}
        self.peer_connection_ids: dict[int, tuple[bytes, bytes]] = {}
        self.peer_transport_parameters: TransportParameters | None = None
        self.local_transport_parameters: TransportParameters | None = None
        self._peer_active_connection_id_limit = 4
        self._peer_default_stream_window = 65_535
        self._handshake_done_sent = False
        self._peer_new_tokens: list[bytes] = []
        self._token_secret = derive_secret(self.secret, b'quic-address-token', length=32)
        self._original_destination_connection_id: bytes | None = self.remote_cid if is_client else None
        self._peer_initial_source_connection_id: bytes | None = None
        self._first_server_source_connection_id: bytes | None = None
        self._retry_source_connection_id: bytes | None = None
        self._retry_token: bytes = b''
        self._received_retry = False
        self._sent_retry = False
        self._peer_preferred_address: bytes | None = None
        self._path_addr: tuple[str, int] | None = None
        self._ack_delay_exponent = 3
        self._sync_packet_number_snapshot()

    @property
    def peer_new_tokens(self) -> tuple[bytes, ...]:
        return tuple(self._peer_new_tokens)

    @property
    def peer_preferred_address(self) -> bytes | None:
        return self._peer_preferred_address

    @property
    def _send_1rtt_keys(self) -> QuicPacketProtectionKeys:
        return self.client_1rtt_keys if self.is_client else self.server_1rtt_keys

    @property
    def _recv_1rtt_keys(self) -> QuicPacketProtectionKeys:
        return self.server_1rtt_keys if self.is_client else self.client_1rtt_keys

    def _space_state(self, packet_space: str) -> _PacketSpaceState:
        normalized = PACKET_SPACE_APPLICATION if packet_space == PACKET_SPACE_ZERO_RTT else packet_space
        if normalized not in self._packet_spaces:
            self._packet_spaces[normalized] = _PacketSpaceState(name=normalized)
        return self._packet_spaces[normalized]

    def _recovery_space(self, packet_space: str) -> str:
        return PACKET_SPACE_APPLICATION if packet_space == PACKET_SPACE_ZERO_RTT else packet_space

    def _path_key_for_addr(self, addr: tuple[str, int] | None) -> Any:
        return _DEFAULT_PATH_KEY if addr is None else addr

    def _path_state(self, path_key: Any) -> _PathRuntime:
        state = self._path_states.get(path_key)
        if state is None:
            addr = None if path_key == _DEFAULT_PATH_KEY else path_key
            state = _PathRuntime(key=path_key, addr=addr, recovery=QuicLossRecovery(max_datagram_size=self.max_datagram_size))
            if self.peer_transport_parameters is not None:
                state.recovery.rtt.max_ack_delay = self.recovery.rtt.max_ack_delay
            self._path_states[path_key] = state
        return state

    def _activate_path(self, path_key: Any) -> _PathRuntime:
        state = self._path_state(path_key)
        self._active_path_key = path_key
        self.recovery = state.recovery
        self.congestion.bytes_in_flight = self.recovery.bytes_in_flight
        self.congestion.congestion_window = self.recovery.congestion_window
        self.congestion.ssthresh = self.recovery.ssthresh
        return state

    def _refresh_congestion_snapshot(self, recovery: QuicLossRecovery | None = None) -> None:
        target = self.recovery if recovery is None else recovery
        if target is self.recovery:
            self.congestion.bytes_in_flight = target.bytes_in_flight
            self.congestion.congestion_window = target.congestion_window
            self.congestion.ssthresh = target.ssthresh

    def _register_datagram_packets(self, datagram: bytes, packet_refs: list[tuple[str, int]]) -> None:
        if packet_refs:
            self._wire_datagram_packets[datagram] = list(packet_refs)

    def _packet_refs_for_datagram(self, datagram: bytes) -> list[tuple[str, int]]:
        refs = self._wire_datagram_packets.get(datagram)
        if refs is not None:
            return list(refs)
        try:
            packets = split_coalesced_packets(datagram, destination_connection_id_length=max(len(self.local_cid), 1))
        except ProtocolError:
            return []
        resolved: list[tuple[str, int]] = []
        for packet in packets:
            packet_refs = self._wire_datagram_packets.get(packet)
            if packet_refs is None:
                continue
            resolved.extend(packet_refs)
        if resolved:
            self._wire_datagram_packets[datagram] = list(resolved)
        return resolved

    def _sync_packet_number_snapshot(self) -> None:
        self.packet_numbers.initial_send = self._packet_spaces[PACKET_SPACE_INITIAL].send
        self.packet_numbers.handshake_send = self._packet_spaces[PACKET_SPACE_HANDSHAKE].send
        self.packet_numbers.application_send = self._packet_spaces[PACKET_SPACE_APPLICATION].send
        self.packet_numbers.initial_largest_received = self._packet_spaces[PACKET_SPACE_INITIAL].largest_received
        self.packet_numbers.handshake_largest_received = self._packet_spaces[PACKET_SPACE_HANDSHAKE].largest_received
        self.packet_numbers.application_largest_received = self._packet_spaces[PACKET_SPACE_APPLICATION].largest_received

    def _issue_address_token(
        self,
        *,
        purpose: int,
        addr: tuple[str, int] | None,
        original_destination_connection_id: bytes = b'',
        retry_source_connection_id: bytes = b'',
    ) -> bytes:
        address_bytes = _serialize_address(addr)
        if len(original_destination_connection_id) > 255 or len(retry_source_connection_id) > 255:
            raise ValueError('connection ids are too large to encode in a QUIC token')
        body = bytearray()
        body.append(_TOKEN_FORMAT_VERSION)
        body.append(purpose)
        body.extend(_current_time_ms().to_bytes(8, 'big'))
        body.extend(len(address_bytes).to_bytes(2, 'big'))
        body.extend(address_bytes)
        body.append(len(original_destination_connection_id))
        body.extend(original_destination_connection_id)
        body.append(len(retry_source_connection_id))
        body.extend(retry_source_connection_id)
        mac = hmac.new(self._token_secret, bytes(body), hashlib.sha256).digest()[:_TOKEN_MAC_LENGTH]
        return bytes(body) + mac

    def _validate_address_token(
        self,
        token: bytes,
        *,
        addr: tuple[str, int] | None,
        expected_purpose: int | None = None,
    ) -> _TokenInfo | None:
        minimum = 1 + 1 + 8 + 2 + 1 + 1 + _TOKEN_MAC_LENGTH
        if len(token) < minimum:
            return None
        body, mac = token[:-_TOKEN_MAC_LENGTH], token[-_TOKEN_MAC_LENGTH:]
        expected_mac = hmac.new(self._token_secret, body, hashlib.sha256).digest()[:_TOKEN_MAC_LENGTH]
        if not hmac.compare_digest(mac, expected_mac):
            return None
        offset = 0
        format_version = body[offset]
        offset += 1
        if format_version != _TOKEN_FORMAT_VERSION:
            return None
        purpose = body[offset]
        offset += 1
        if expected_purpose is not None and purpose != expected_purpose:
            return None
        if offset + 8 > len(body):
            return None
        issued_at_ms = int.from_bytes(body[offset:offset + 8], 'big')
        offset += 8
        if offset + 2 > len(body):
            return None
        address_length = int.from_bytes(body[offset:offset + 2], 'big')
        offset += 2
        end = offset + address_length
        if end > len(body):
            return None
        address_bytes = body[offset:end]
        offset = end
        if offset >= len(body):
            return None
        original_length = body[offset]
        offset += 1
        end = offset + original_length
        if end > len(body):
            return None
        original_destination_connection_id = body[offset:end]
        offset = end
        if offset >= len(body):
            return None
        retry_length = body[offset]
        offset += 1
        end = offset + retry_length
        if end != len(body):
            return None
        retry_source_connection_id = body[offset:end]
        if addr is not None and address_bytes and address_bytes != _serialize_address(addr):
            return None
        now_ms = _current_time_ms()
        if issued_at_ms > now_ms + 60_000:
            return None
        lifetime_ms = self.retry_token_lifetime_ms if purpose == _TOKEN_PURPOSE_RETRY else self.new_token_lifetime_ms
        if now_ms - issued_at_ms > lifetime_ms:
            return None
        address = _parse_serialized_address(address_bytes) if address_bytes else None
        return _TokenInfo(
            purpose=purpose,
            issued_at_ms=issued_at_ms,
            address=address,
            original_destination_connection_id=original_destination_connection_id,
            retry_source_connection_id=retry_source_connection_id,
        )

    def _update_local_transport_parameters(self) -> None:
        if self.handshake_driver is None:
            return
        transport_parameters = self.handshake_driver.transport_parameters
        transport_parameters.initial_source_connection_id = self.local_cid
        if self.is_client:
            transport_parameters.original_destination_connection_id = None
            transport_parameters.preferred_address = None
            transport_parameters.retry_source_connection_id = None
            transport_parameters.stateless_reset_token = None
        else:
            if transport_parameters.stateless_reset_token is None:
                transport_parameters.stateless_reset_token = derive_secret(self.local_cid + self.secret, b'stateless-reset', length=16)
            if self._original_destination_connection_id is not None:
                transport_parameters.original_destination_connection_id = self._original_destination_connection_id
            if self._retry_source_connection_id is not None:
                transport_parameters.retry_source_connection_id = self._retry_source_connection_id
        self.local_transport_parameters = transport_parameters
        self.streams.configure_local_initial_limits(
            bidirectional=transport_parameters.max_streams_bidi,
            unidirectional=transport_parameters.max_streams_uni,
        )
        self.flow.configure_local_initial_limits(
            max_data=transport_parameters.max_data,
            max_stream_data_bidi_local=transport_parameters.max_stream_data_bidi_local,
            max_stream_data_bidi_remote=transport_parameters.max_stream_data_bidi_remote,
            max_stream_data_uni=transport_parameters.max_stream_data_uni,
        )

    def _derive_tls_packet_protection_keys(self, secret: bytes, *, stage: str) -> QuicPacketProtectionKeys:
        if self.handshake_driver is None:
            return derive_quic_packet_protection_keys(secret)
        parameters = self.handshake_driver.packet_protection_parameters(stage=stage)
        return derive_quic_packet_protection_keys(
            secret,
            key_length=parameters.key_length,
            iv_length=parameters.iv_length,
            hp_length=parameters.hp_length,
            hash_name=parameters.hash_name,
        )

    def _tls_hash_name(self) -> str:
        if self.handshake_driver is None:
            return 'sha256'
        return self.handshake_driver.cipher_parameters.hash_name

    def _refresh_tls_key_material(self) -> None:
        if self.handshake_driver is None:
            return
        self._update_local_transport_parameters()
        client_early_secret = getattr(self.handshake_driver, '_client_early_secret', None)
        if client_early_secret is not None and self.client_0rtt_keys is None:
            self.client_0rtt_keys = self._derive_tls_packet_protection_keys(client_early_secret, stage='0rtt')
        client_handshake_secret = getattr(self.handshake_driver, '_client_handshake_secret', None)
        server_handshake_secret = getattr(self.handshake_driver, '_server_handshake_secret', None)
        if client_handshake_secret is not None and server_handshake_secret is not None and not self._handshake_traffic_installed:
            self._client_handshake_secret = client_handshake_secret
            self._server_handshake_secret = server_handshake_secret
            self.client_handshake_keys = self._derive_tls_packet_protection_keys(client_handshake_secret, stage='handshake')
            self.server_handshake_keys = self._derive_tls_packet_protection_keys(server_handshake_secret, stage='handshake')
            self._handshake_traffic_installed = True
        traffic_secrets = self.handshake_driver.traffic_secrets
        if traffic_secrets is None or self._application_traffic_installed:
            return
        self._client_handshake_secret = traffic_secrets.client_handshake_secret
        self._server_handshake_secret = traffic_secrets.server_handshake_secret
        self.client_handshake_keys = self._derive_tls_packet_protection_keys(traffic_secrets.client_handshake_secret, stage='handshake')
        self.server_handshake_keys = self._derive_tls_packet_protection_keys(traffic_secrets.server_handshake_secret, stage='handshake')
        if traffic_secrets.client_early_secret is not None:
            self.client_0rtt_keys = self._derive_tls_packet_protection_keys(traffic_secrets.client_early_secret, stage='0rtt')
        self._client_application_secret = traffic_secrets.client_application_secret
        self._server_application_secret = traffic_secrets.server_application_secret
        self.client_1rtt_keys = self._derive_tls_packet_protection_keys(traffic_secrets.client_application_secret, stage='application')
        self.server_1rtt_keys = self._derive_tls_packet_protection_keys(traffic_secrets.server_application_secret, stage='application')
        self._application_traffic_installed = True

    def _apply_peer_transport_parameters(self) -> None:
        if self.handshake_driver is None or self.handshake_driver.peer_transport_parameters is None:
            return
        peer = self.handshake_driver.peer_transport_parameters
        if self.is_client:
            if self._original_destination_connection_id is not None and peer.original_destination_connection_id != self._original_destination_connection_id:
                raise ProtocolError('server original_destination_connection_id transport parameter mismatch')
            if self._first_server_source_connection_id is not None and peer.initial_source_connection_id != self._first_server_source_connection_id:
                raise ProtocolError('server initial_source_connection_id transport parameter mismatch')
            if self._received_retry:
                if peer.retry_source_connection_id != self._retry_source_connection_id:
                    raise ProtocolError('server retry_source_connection_id transport parameter mismatch')
            elif peer.retry_source_connection_id is not None:
                raise ProtocolError('server sent retry_source_connection_id without using Retry')
        else:
            if peer.original_destination_connection_id is not None:
                raise ProtocolError('client sent forbidden original_destination_connection_id transport parameter')
            if peer.preferred_address is not None:
                raise ProtocolError('client sent forbidden preferred_address transport parameter')
            if peer.retry_source_connection_id is not None:
                raise ProtocolError('client sent forbidden retry_source_connection_id transport parameter')
            if peer.stateless_reset_token is not None:
                raise ProtocolError('client sent forbidden stateless_reset_token transport parameter')
            if self._peer_initial_source_connection_id is not None and peer.initial_source_connection_id != self._peer_initial_source_connection_id:
                raise ProtocolError('client initial_source_connection_id transport parameter mismatch')
        self.peer_transport_parameters = peer
        self.local_transport_parameters = self.handshake_driver.transport_parameters
        ack_delay_exponent = peer.ack_delay_exponent if peer.ack_delay_exponent >= 0 else 3
        max_ack_delay = max(peer.max_ack_delay, 0) / 1000.0
        for path in self._path_states.values():
            path.recovery.rtt.max_ack_delay = max_ack_delay
        self._peer_active_connection_id_limit = peer.active_connection_id_limit
        self._peer_default_stream_window = peer.max_stream_data_bidi_remote
        self.flow.configure_peer_initial_limits(
            max_data=peer.max_data,
            max_stream_data_bidi_local=peer.max_stream_data_bidi_local,
            max_stream_data_bidi_remote=peer.max_stream_data_bidi_remote,
            max_stream_data_uni=peer.max_stream_data_uni,
        )
        self.streams.configure_peer_initial_limits(
            bidirectional=peer.max_streams_bidi,
            unidirectional=peer.max_streams_uni,
        )
        self._peer_preferred_address = peer.preferred_address
        self._ack_delay_exponent = ack_delay_exponent
        self._update_runtime_timers()

    def _initial_keys(self, *, destination_connection_id: bytes | None = None) -> tuple[QuicPacketProtectionKeys, QuicPacketProtectionKeys]:
        if destination_connection_id is not None:
            connection_id = destination_connection_id
        elif self.is_client:
            connection_id = self.remote_cid or self._original_destination_connection_id or self.local_cid
        else:
            connection_id = self._retry_source_connection_id or self.local_cid or self._original_destination_connection_id or self.remote_cid
        return derive_initial_packet_protection_keys(connection_id)

    def _recv_initial_keys(self, packet: QuicLongHeaderPacket) -> tuple[QuicPacketProtectionKeys, QuicPacketProtectionKeys]:
        if self.is_client:
            connection_id = self.remote_cid or self._retry_source_connection_id or self._original_destination_connection_id or packet.source_connection_id
        else:
            connection_id = packet.destination_connection_id
        return derive_initial_packet_protection_keys(connection_id)

    def _send_handshake_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        keys = self.client_handshake_keys if self.is_client else self.server_handshake_keys
        if keys is None:
            raise ProtocolError('handshake packet protection keys are not available')
        return keys

    def _recv_handshake_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        keys = self.server_handshake_keys if self.is_client else self.client_handshake_keys
        if keys is None:
            raise ProtocolError('handshake packet protection keys are not available')
        return keys

    def _send_0rtt_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        if not self.is_client:
            raise ProtocolError('only clients can send 0-RTT packets')
        if self.client_0rtt_keys is None:
            raise ProtocolError('0-RTT packet protection keys are not available')
        return self.client_0rtt_keys

    def _recv_0rtt_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        if self.client_0rtt_keys is None:
            raise ProtocolError('0-RTT packet protection keys are not available')
        return self.client_0rtt_keys

    def _promote_key_update(self) -> None:
        hash_name = self._tls_hash_name()
        self._client_application_secret = update_quic_secret(self._client_application_secret, hash_name=hash_name)
        self._server_application_secret = update_quic_secret(self._server_application_secret, hash_name=hash_name)
        self.client_1rtt_keys = self._derive_tls_packet_protection_keys(self._client_application_secret, stage='application')
        self.server_1rtt_keys = self._derive_tls_packet_protection_keys(self._server_application_secret, stage='application')

    def initiate_key_update(self) -> None:
        self._promote_key_update()
        self._send_key_phase ^= 1
        self._recv_key_phase = self._send_key_phase

    def _ack_eliciting(self, frames: Iterable[object]) -> bool:
        for frame in frames:
            frame_type = frame_type_value(frame) if not isinstance(frame, int) or frame in {FRAME_PADDING, FRAME_PING} else int(frame)
            if frame_type not in {FRAME_PADDING, FRAME_ACK, FRAME_CONNECTION_CLOSE, FRAME_CONNECTION_CLOSE_APP}:
                return True
        return False

    def _retransmittable_frames(self, frames: Iterable[object]) -> list[object]:
        retransmittable: list[object] = []
        for frame in frames:
            frame_type = frame_type_value(frame) if not isinstance(frame, int) or frame in {FRAME_PADDING, FRAME_PING} else int(frame)
            if frame_type in {FRAME_PADDING, FRAME_ACK}:
                continue
            retransmittable.append(frame)
        return retransmittable

    def _schedule_ack(self, packet_space: str, *, immediate: bool = False, now: float | None = None) -> None:
        normalized = self._recovery_space(packet_space)
        state = self._space_state(normalized)
        at = time.monotonic() if now is None else now
        state.pending_ack_eliciting += 1
        if immediate or normalized in {PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE} or state.pending_ack_eliciting >= 2:
            state.ack_deadline = at
        else:
            delay = self.local_transport_parameters.max_ack_delay / 1000.0 if self.local_transport_parameters is not None else _ACK_DELAY_DEFAULT
            state.ack_deadline = at + max(delay, 0.0)
        self._timer_wheel.schedule(_TIMER_ACK, state.ack_deadline, path_key=self._active_path_key, packet_space=normalized)

    def _clear_ack_schedule(self, packet_space: str) -> None:
        normalized = self._recovery_space(packet_space)
        state = self._space_state(normalized)
        state.pending_ack_eliciting = 0
        state.ack_deadline = None
        self._timer_wheel.cancel(_TIMER_ACK, path_key=self._active_path_key, packet_space=normalized)

    def _queue_scheduled_spec(
        self,
        *,
        packet_space: str,
        frames: list[object],
        token: bytes | None = None,
        path_key: Any | None = None,
        is_pto_probe: bool = False,
    ) -> None:
        self._scheduled_specs.append(
            _ScheduledFrameSpec(
                packet_space=packet_space,
                frames=list(frames),
                token=token,
                path_key=self._active_path_key if path_key is None else path_key,
                is_pto_probe=is_pto_probe,
            )
        )

    def _emit_scheduled_specs(self) -> list[bytes]:
        if not self._scheduled_specs:
            return []
        previous_path = self._active_path_key
        encoded_packets: list[tuple[str, bytes]] = []
        while self._scheduled_specs:
            spec = self._scheduled_specs.pop(0)
            self._activate_path(spec.path_key)
            encoded_packets.append(
                (
                    spec.packet_space,
                    self.send_frames(
                        spec.frames,
                        packet_space=spec.packet_space,
                        token=spec.token,
                        is_pto_probe=spec.is_pto_probe,
                    ),
                )
            )
        self._activate_path(previous_path)
        return self._pack_encoded_packets(encoded_packets)

    def _register_coalesced_datagrams(self, datagrams: Iterable[bytes]) -> None:
        for datagram in datagrams:
            if datagram in self._wire_datagram_packets:
                continue
            try:
                packets = split_coalesced_packets(datagram, destination_connection_id_length=max(len(self.local_cid), 1))
            except ProtocolError:
                continue
            refs: list[tuple[str, int]] = []
            for packet in packets:
                refs.extend(self._wire_datagram_packets.get(packet, []))
            if refs:
                self._wire_datagram_packets[datagram] = refs

    def _pack_encoded_packets(self, encoded_packets: list[tuple[str, bytes]]) -> list[bytes]:
        datagrams: list[bytes] = []
        long_header_group: list[bytes] = []

        def flush_long_group() -> None:
            nonlocal long_header_group
            if not long_header_group:
                return
            datagrams.extend(coalesce_packets(long_header_group, max_datagram_size=self.max_datagram_size))
            long_header_group = []

        for packet_space, raw in encoded_packets:
            if packet_space == PACKET_SPACE_APPLICATION:
                flush_long_group()
                datagrams.append(raw)
                continue
            long_header_group.append(raw)
        flush_long_group()
        self._register_coalesced_datagrams(datagrams)
        return datagrams

    def _acknowledgement_datagram(self, packet_space: str) -> bytes | None:
        normalized = self._recovery_space(packet_space)
        state = self._space_state(normalized)
        if not state.received_packets:
            self._clear_ack_schedule(normalized)
            return None
        raw = self.acknowledge(packet_space=normalized)
        self._clear_ack_schedule(normalized)
        return raw

    def _on_packets_lost(self, *, path_key: Any, packet_space: str, lost_numbers: Iterable[int]) -> None:
        for packet_number in sorted(set(lost_numbers)):
            meta = self._sent_packets.pop((packet_space, packet_number), None)
            if meta is None:
                continue
            self._wire_datagram_packets.pop(meta.raw, None)
            retransmittable = self._retransmittable_frames(meta.frames)
            if not retransmittable:
                continue
            self._queue_scheduled_spec(
                packet_space=meta.packet_space,
                frames=retransmittable,
                token=meta.token,
                path_key=path_key,
            )

    def _handle_ack_for_path(
        self,
        *,
        path_key: Any,
        packet_space: str,
        acked_numbers: list[int],
        ack_delay: float,
    ) -> None:
        if not acked_numbers:
            return
        recovery = self._path_state(path_key).recovery
        lost = recovery.on_ack_received(
            acked_numbers,
            ack_delay=ack_delay,
            packet_space=packet_space,
        )
        for packet_number in acked_numbers:
            meta = self._sent_packets.pop((packet_space, packet_number), None)
            if meta is not None:
                self._wire_datagram_packets.pop(meta.raw, None)
        self._on_packets_lost(path_key=path_key, packet_space=packet_space, lost_numbers=lost)
        if path_key == self._active_path_key:
            self._refresh_congestion_snapshot(recovery)

    def _handle_ack_frame(self, frame: QuicAckFrame, *, packet_space: str) -> None:
        normalized = self._recovery_space(packet_space)
        acked = frame.acknowledged_packets() or [frame.largest_acked]
        self.last_acked = max(self.last_acked, max(acked))
        ack_delay_exponent = self.peer_transport_parameters.ack_delay_exponent if self.peer_transport_parameters is not None else 3
        ack_delay = float(frame.ack_delay * (1 << ack_delay_exponent)) / 1_000_000 if frame.ack_delay else 0.0
        by_path: dict[Any, list[int]] = {}
        for packet_number in acked:
            meta = self._sent_packets.get((normalized, packet_number))
            if meta is None:
                continue
            by_path.setdefault(meta.path_key, []).append(packet_number)
        if not by_path:
            by_path[self._active_path_key] = acked
        for path_key, packet_numbers in by_path.items():
            self._handle_ack_for_path(
                path_key=path_key,
                packet_space=normalized,
                acked_numbers=packet_numbers,
                ack_delay=ack_delay,
            )
        self._update_runtime_timers()

    def _build_pto_probe_specs(self, *, path_key: Any) -> None:
        path_state = self._path_state(path_key)
        due_spaces = path_state.recovery.pto_due_spaces(now=time.monotonic())
        if not due_spaces:
            candidates = path_state.recovery.pto_candidates(now=time.monotonic())
            if not candidates:
                return
            earliest_deadline = min(deadline for _space, deadline in candidates)
            due_spaces = [space for space, deadline in candidates if abs(deadline - earliest_deadline) <= 0.001]
        path_state.recovery.on_pto_expired()
        probes_sent = 0
        for space in due_spaces:
            outstanding = [
                meta
                for (packet_space, _packet_number), meta in self._sent_packets.items()
                if packet_space == space and meta.path_key == path_key
            ]
            outstanding.sort(key=lambda item: item.packet_number)
            if outstanding:
                for meta in outstanding:
                    retransmittable = self._retransmittable_frames(meta.frames)
                    if not retransmittable:
                        continue
                    self._queue_scheduled_spec(
                        packet_space=meta.packet_space,
                        frames=retransmittable,
                        token=meta.token,
                        path_key=path_key,
                        is_pto_probe=True,
                    )
                    probes_sent += 1
                    break
            else:
                probe_space = PACKET_SPACE_APPLICATION if space == PACKET_SPACE_APPLICATION else space
                self._queue_scheduled_spec(packet_space=probe_space, frames=[FRAME_PING], path_key=path_key, is_pto_probe=True)
                probes_sent += 1
            if probes_sent >= 2:
                break
        if probes_sent == 1:
            self._queue_scheduled_spec(packet_space=PACKET_SPACE_APPLICATION if due_spaces and due_spaces[0] == PACKET_SPACE_APPLICATION else (due_spaces[0] if due_spaces else PACKET_SPACE_APPLICATION), frames=[FRAME_PING], path_key=path_key, is_pto_probe=True)

    def _run_loss_detection(self, *, now: float | None = None) -> None:
        at = time.monotonic() if now is None else now
        for path_key, path_state in self._path_states.items():
            for packet_space, space in path_state.recovery.spaces.items():
                if space.loss_time is not None and space.loss_time <= at + 1e-9:
                    lost = path_state.recovery.detect_lost_packets(now=at, packet_space=packet_space)
                    self._on_packets_lost(path_key=path_key, packet_space=packet_space, lost_numbers=lost)
            if path_state.recovery.pto_due_spaces(now=at):
                self._build_pto_probe_specs(path_key=path_key)
            if path_key == self._active_path_key:
                self._refresh_congestion_snapshot(path_state.recovery)
        self._update_runtime_timers(now=at)

    def _update_runtime_timers(self, *, now: float | None = None) -> None:
        at = time.monotonic() if now is None else now
        for packet_space in (PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE, PACKET_SPACE_APPLICATION):
            state = self._space_state(packet_space)
            if state.ack_deadline is None:
                self._timer_wheel.cancel(_TIMER_ACK, path_key=self._active_path_key, packet_space=packet_space)
            else:
                self._timer_wheel.schedule(_TIMER_ACK, state.ack_deadline, path_key=self._active_path_key, packet_space=packet_space)
        for path_key, path_state in self._path_states.items():
            path_has_loss = False
            for packet_space, space in path_state.recovery.spaces.items():
                if space.loss_time is None:
                    self._timer_wheel.cancel(_TIMER_LOSS, path_key=path_key, packet_space=packet_space)
                    continue
                path_has_loss = True
                self._timer_wheel.schedule(_TIMER_LOSS, space.loss_time, path_key=path_key, packet_space=packet_space)
            if not path_has_loss:
                for packet_space in (PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE, PACKET_SPACE_APPLICATION):
                    if path_state.recovery._space(packet_space).loss_time is None:
                        self._timer_wheel.cancel(_TIMER_LOSS, path_key=path_key, packet_space=packet_space)
            pto_delay = path_state.recovery.next_pto_deadline(now=at)
            if pto_delay is None:
                self._timer_wheel.cancel(_TIMER_PTO, path_key=path_key)
            else:
                self._timer_wheel.schedule(_TIMER_PTO, at + pto_delay, path_key=path_key)

    def next_runtime_deadline(self) -> float | None:
        return self._timer_wheel.next_delay()

    def drain_scheduled_datagrams(self) -> list[bytes]:
        due_datagrams: list[bytes] = []
        due_timers = self._timer_wheel.pop_due()
        if due_timers:
            for timer in due_timers:
                if timer.kind == _TIMER_ACK and timer.packet_space is not None:
                    raw = self._acknowledgement_datagram(timer.packet_space)
                    if raw is not None:
                        due_datagrams.append(raw)
                    continue
                if timer.kind == _TIMER_LOSS:
                    self._run_loss_detection(now=timer.deadline)
                    continue
                if timer.kind == _TIMER_PTO:
                    self._build_pto_probe_specs(path_key=timer.path_key)
                    self._update_runtime_timers(now=timer.deadline)
        due_datagrams.extend(self._emit_scheduled_specs())
        return due_datagrams

    def can_transmit_datagram(self, datagram: bytes, *, now: float | None = None) -> bool:
        at = time.monotonic() if now is None else now
        if not self.can_send_amplification_limited(len(datagram)):
            return False
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return self.recovery.can_send(len(datagram), now=at)
        ack_eliciting_bytes_by_path: dict[Any, int] = {}
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or not meta.ack_eliciting:
                continue
            ack_eliciting_bytes_by_path[meta.path_key] = ack_eliciting_bytes_by_path.get(meta.path_key, 0) + len(meta.raw)
        if not ack_eliciting_bytes_by_path:
            return True
        for path_key, amount in ack_eliciting_bytes_by_path.items():
            if not self._path_state(path_key).recovery.can_send(amount, now=at):
                return False
        return True

    def next_transmit_delay(self, datagram: bytes, *, now: float | None = None) -> float | None:
        at = time.monotonic() if now is None else now
        if not self.can_send_amplification_limited(len(datagram)):
            return None
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return self.recovery.time_until_send(len(datagram), now=at)
        ack_eliciting_bytes_by_path: dict[Any, int] = {}
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or not meta.ack_eliciting:
                continue
            ack_eliciting_bytes_by_path[meta.path_key] = ack_eliciting_bytes_by_path.get(meta.path_key, 0) + len(meta.raw)
        if not ack_eliciting_bytes_by_path:
            return 0.0
        delays: list[float] = []
        for path_key, amount in ack_eliciting_bytes_by_path.items():
            delay = self._path_state(path_key).recovery.time_until_send(amount, now=at)
            if delay is None:
                return None
            delays.append(delay)
        return max(delays) if delays else 0.0

    def defer_datagram(self, datagram: bytes) -> bool:
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return False
        changed = False
        refunded = 0
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or not meta.transmitted:
                continue
            meta.transmitted = False
            refunded += len(meta.raw)
            if meta.ack_eliciting:
                self._path_state(meta.path_key).recovery.deactivate_packet(ref[1], packet_space=ref[0], now=time.monotonic())
            changed = True
        if changed:
            self.bytes_sent = max(0, self.bytes_sent - refunded)
            self._update_runtime_timers()
        return changed

    def confirm_datagram_sent(self, datagram: bytes, *, now: float | None = None) -> bool:
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return False
        at = time.monotonic() if now is None else now
        changed = False
        added = 0
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or meta.transmitted:
                continue
            meta.transmitted = True
            added += len(meta.raw)
            if meta.ack_eliciting:
                self._path_state(meta.path_key).recovery.activate_packet(ref[1], packet_space=ref[0], sent_time=at, now=at)
            changed = True
        if changed:
            self.bytes_sent += added
            self._update_runtime_timers(now=at)
        return changed

    def _record_packet_send(
        self,
        *,
        packet_space: str,
        packet_number: int,
        raw: bytes,
        frames: list[object],
        token: bytes | None = None,
        is_pto_probe: bool = False,
    ) -> None:
        recovery_space = self._recovery_space(packet_space)
        path_state = self._path_state(self._active_path_key)
        ack_eliciting = self._ack_eliciting(frames)
        path_state.recovery.on_packet_sent(
            packet_number,
            len(raw),
            ack_eliciting=ack_eliciting,
            packet_space=recovery_space,
            is_pto_probe=is_pto_probe,
        )
        self._sent_packets[(recovery_space, packet_number)] = _SentPacketMeta(
            packet_space=packet_space,
            packet_number=packet_number,
            frames=list(frames),
            raw=raw,
            path_key=path_state.key,
            token=token,
            ack_eliciting=ack_eliciting,
            is_pto_probe=is_pto_probe,
        )
        self._register_datagram_packets(raw, [(recovery_space, packet_number)])
        self.bytes_sent += len(raw)
        self._refresh_congestion_snapshot(path_state.recovery)
        self._update_runtime_timers()

    def _encode_long(
        self,
        *,
        packet_type: QuicLongHeaderType,
        packet_space: str,
        frames: list[object],
        token: bytes = b'',
        keys: QuicPacketProtectionKeys,
        is_pto_probe: bool = False,
    ) -> bytes:
        validate_frames_for_packet_space(frames, packet_space, is_client=self.is_client)
        if self.remote_cid is None:
            self.remote_cid = self.local_cid
        if self.is_client and packet_type == QuicLongHeaderType.INITIAL and self._original_destination_connection_id is None:
            self._original_destination_connection_id = self.remote_cid
        state = self._space_state(packet_space)
        packet_number = state.send
        pn_bytes = packet_number.to_bytes(4, 'big')
        plaintext = b''.join(encode_frame(frame) for frame in frames)
        original_plaintext_length = len(plaintext)
        packet = QuicLongHeaderPacket(
            packet_type=packet_type,
            version=self.version,
            destination_connection_id=self.remote_cid,
            source_connection_id=self.local_cid,
            packet_number=pn_bytes,
            payload=b'\x00' * (len(plaintext) + 16),
            token=token,
        )
        if packet_type == QuicLongHeaderType.INITIAL and self.is_client:
            while True:
                packet_length = len(packet.header_bytes()) + len(plaintext) + 16
                if packet_length < _MIN_INITIAL_DATAGRAM_SIZE:
                    plaintext += b'\x00' * (_MIN_INITIAL_DATAGRAM_SIZE - packet_length)
                elif packet_length > _MIN_INITIAL_DATAGRAM_SIZE and len(plaintext) > original_plaintext_length:
                    trim = min(packet_length - _MIN_INITIAL_DATAGRAM_SIZE, len(plaintext) - original_plaintext_length)
                    plaintext = plaintext[:-trim]
                else:
                    break
                packet = QuicLongHeaderPacket(
                    packet_type=packet_type,
                    version=self.version,
                    destination_connection_id=self.remote_cid,
                    source_connection_id=self.local_cid,
                    packet_number=pn_bytes,
                    payload=b'\x00' * (len(plaintext) + 16),
                    token=token,
                )
        raw = protect_quic_packet(
            packet.header_bytes(),
            plaintext,
            packet_number=packet_number,
            pn_offset=packet.pn_offset,
            keys=keys,
        )
        state.send += 1
        self._sync_packet_number_snapshot()
        self._record_packet_send(
            packet_space=packet_space,
            packet_number=packet_number,
            raw=raw,
            frames=frames,
            token=token or None,
            is_pto_probe=is_pto_probe,
        )
        return raw

    def _encode_initial(self, frames: list[object], *, token: bytes | None = None, is_pto_probe: bool = False) -> bytes:
        self._refresh_tls_key_material()
        client_keys, server_keys = self._initial_keys()
        keys = client_keys if self.is_client else server_keys
        token_bytes = self._retry_token if token is None else token
        return self._encode_long(
            packet_type=QuicLongHeaderType.INITIAL,
            packet_space=PACKET_SPACE_INITIAL,
            frames=frames,
            token=token_bytes,
            keys=keys,
            is_pto_probe=is_pto_probe,
        )

    def _encode_handshake(self, frames: list[object], *, is_pto_probe: bool = False) -> bytes:
        return self._encode_long(
            packet_type=QuicLongHeaderType.HANDSHAKE,
            packet_space=PACKET_SPACE_HANDSHAKE,
            frames=frames,
            keys=self._send_handshake_keys(),
            is_pto_probe=is_pto_probe,
        )

    def _encode_zero_rtt(self, frames: list[object], *, is_pto_probe: bool = False) -> bytes:
        return self._encode_long(
            packet_type=QuicLongHeaderType.ZERO_RTT,
            packet_space=PACKET_SPACE_ZERO_RTT,
            frames=frames,
            keys=self._send_0rtt_keys(),
            is_pto_probe=is_pto_probe,
        )

    def _encode_short(self, frames: list[object], *, is_pto_probe: bool = False) -> bytes:
        validate_frames_for_packet_space(frames, PACKET_SPACE_APPLICATION, is_client=self.is_client)
        if self.remote_cid is None:
            self.remote_cid = self.local_cid
        state = self._space_state(PACKET_SPACE_APPLICATION)
        packet_number = state.send
        pn_bytes = packet_number.to_bytes(4, 'big')
        plaintext = b''.join(encode_frame(frame) for frame in frames)
        packet = QuicShortHeaderPacket(
            destination_connection_id=self.remote_cid,
            packet_number=pn_bytes,
            payload=b'\x00' * (len(plaintext) + 16),
            key_phase=bool(self._send_key_phase),
        )
        raw = protect_quic_packet(
            packet.header_bytes(),
            plaintext,
            packet_number=packet_number,
            pn_offset=packet.pn_offset,
            keys=self._send_1rtt_keys,
        )
        state.send += 1
        self._sync_packet_number_snapshot()
        self._record_packet_send(
            packet_space=PACKET_SPACE_APPLICATION,
            packet_number=packet_number,
            raw=raw,
            frames=frames,
            is_pto_probe=is_pto_probe,
        )
        return raw

    def send_frames(
        self,
        frames: list[object],
        *,
        packet_space: str = PACKET_SPACE_APPLICATION,
        token: bytes | None = None,
        is_pto_probe: bool = False,
    ) -> bytes:
        if packet_space == PACKET_SPACE_INITIAL:
            return self._encode_initial(frames, token=token, is_pto_probe=is_pto_probe)
        if packet_space == PACKET_SPACE_HANDSHAKE:
            return self._encode_handshake(frames, is_pto_probe=is_pto_probe)
        if packet_space == PACKET_SPACE_ZERO_RTT:
            return self._encode_zero_rtt(frames, is_pto_probe=is_pto_probe)
        return self._encode_short(frames, is_pto_probe=is_pto_probe)

    def build_coalesced_datagrams(
        self,
        packet_specs: Iterable[tuple[str, list[object], bytes | None] | tuple[str, list[object]]],
    ) -> list[bytes]:
        encoded_packets: list[tuple[str, bytes]] = []
        for spec in packet_specs:
            if len(spec) == 3:  # type: ignore[arg-type]
                packet_space, frames, token = spec  # type: ignore[misc]
            else:
                packet_space, frames = spec  # type: ignore[misc]
                token = None
            encoded_packets.append((packet_space, self.send_frames(frames, packet_space=packet_space, token=token)))
        return self._pack_encoded_packets(encoded_packets)

    def build_initial(self, *, token: bytes | None = None) -> bytes:
        self.state = 'establishing'
        return self._encode_initial([FRAME_PING], token=token)

    def _prepare_stream_window(self, stream_id: int) -> None:
        self.flow.ensure_stream(stream_id)

    def _queue_streams_blocked_if_needed(self, stream_id: int) -> None:
        bidirectional = not stream_is_unidirectional(stream_id)
        if stream_is_local_initiated(stream_id, local_is_client=self.is_client):
            limit = self.streams.peer_stream_limit(bidirectional=bidirectional)
            self._pending_handshake_datagrams.append(self.send_streams_blocked(limit, bidirectional=bidirectional))

    def _queue_flow_blocked_frames(self, stream_id: int, amount: int) -> None:
        self.flow.ensure_stream(stream_id)
        if self.flow.connection_bytes_sent + amount > self.flow.connection_window:
            self._pending_handshake_datagrams.append(self.send_data_blocked())
        if self.flow.stream_bytes_sent[stream_id] + amount > self.flow.stream_windows[stream_id]:
            self._pending_handshake_datagrams.append(self.send_stream_data_blocked(stream_id))

    def _maybe_queue_max_stream_credit(self, stream_id: int) -> None:
        frame = self.streams.maybe_release_peer_stream_credit(stream_id)
        if frame is not None:
            self._pending_handshake_datagrams.append(self._encode_short([frame]))

    def send_stream_data(self, stream_id: int, data: bytes, *, fin: bool = False) -> bytes:
        try:
            stream_state = self.streams.ensure_send_stream(stream_id)
        except ProtocolError:
            self._queue_streams_blocked_if_needed(stream_id)
            raise
        self._prepare_stream_window(stream_id)
        if len(data) and not self.flow.can_send(stream_id, len(data)):
            self._queue_flow_blocked_frames(stream_id, len(data))
            raise ProtocolError('insufficient QUIC flow-control credit')
        offset = stream_state.reserve_send(data, fin=fin)
        if len(data):
            self.flow.consume_send(stream_id, len(data))
        frame = QuicStreamFrame(stream_id=stream_id, offset=offset, data=data, fin=fin)
        self.state = 'established'
        packet = self._encode_short([frame])
        self._maybe_queue_max_stream_credit(stream_id)
        return packet

    def send_early_stream_data(self, stream_id: int, data: bytes, *, fin: bool = False) -> bytes:
        stream_state = self.streams.ensure_send_stream(stream_id)
        self._prepare_stream_window(stream_id)
        if len(data) and not self.flow.can_send(stream_id, len(data)):
            raise ProtocolError('insufficient QUIC flow-control credit')
        offset = stream_state.reserve_send(data, fin=fin)
        if len(data):
            self.flow.consume_send(stream_id, len(data))
        frame = QuicStreamFrame(stream_id=stream_id, offset=offset, data=data, fin=fin)
        self.state = 'establishing'
        packet = self._encode_zero_rtt([frame])
        self._maybe_queue_max_stream_credit(stream_id)
        return packet

    def send_crypto_data(self, data: bytes, *, offset: int | None = None, packet_space: str = PACKET_SPACE_INITIAL) -> bytes:
        state = self._space_state(packet_space)
        frame_offset = state.crypto_send_offset if offset is None else offset
        state.crypto_send_offset = max(state.crypto_send_offset, frame_offset + len(data))
        frame = QuicCryptoFrame(offset=frame_offset, data=data)
        self.state = 'establishing'
        return self.send_frames([frame], packet_space=packet_space)

    def _queue_handshake_payload(self, payload: bytes) -> bytes:
        if self.handshake_driver is None:
            return self.send_crypto_data(payload, packet_space=PACKET_SPACE_INITIAL)
        flights = self.handshake_driver.outbound_flights(payload)
        if not flights:
            return b''
        encoded_packets = [(flight.packet_space, self.send_crypto_data(flight.data, packet_space=flight.packet_space)) for flight in flights]
        datagrams = self._pack_encoded_packets(encoded_packets)
        first, *rest = datagrams
        self._pending_handshake_datagrams.extend(rest)
        return first

    def path_challenge(self, data: bytes) -> bytes:
        self.path_challenges.add(data)
        return self._encode_short([QuicPathChallengeFrame(data=data)])

    def path_response(self, data: bytes) -> bytes:
        return self._encode_short([QuicPathResponseFrame(data=data)])

    def handshake_done(self) -> bytes:
        self.state = 'established'
        self._handshake_done_sent = True
        return self._encode_short([QuicHandshakeDoneFrame()])

    def acknowledge(self, packet_number: int | None = None, *, packet_space: str = PACKET_SPACE_APPLICATION) -> bytes:
        if packet_number is not None:
            self._mark_received(packet_space, packet_number)
        frame = self._build_ack_frame(packet_space)
        if packet_space == PACKET_SPACE_INITIAL:
            return self._encode_initial([frame])
        if packet_space == PACKET_SPACE_HANDSHAKE:
            return self._encode_handshake([frame])
        return self._encode_short([frame])

    def credit_connection(self, amount: int) -> bytes:
        self.flow.expand_local_connection_limit(amount)
        return self._encode_short([QuicMaxDataFrame(maximum_data=self.flow.local_connection_window)])

    def credit_stream(self, stream_id: int, amount: int) -> bytes:
        self.flow.expand_local_stream_limit(stream_id, amount)
        return self._encode_short([QuicMaxStreamDataFrame(stream_id=stream_id, maximum_data=self.flow.receive_window_for_stream(stream_id))])

    def send_data_blocked(self) -> bytes:
        return self._encode_short([QuicDataBlockedFrame(limit=max(self.flow.connection_window, 0))])

    def send_stream_data_blocked(self, stream_id: int) -> bytes:
        self.flow.ensure_stream(stream_id)
        return self._encode_short([QuicStreamDataBlockedFrame(stream_id=stream_id, limit=max(self.flow.window_for_stream(stream_id), 0))])

    def send_streams_blocked(self, limit: int, *, bidirectional: bool = True) -> bytes:
        return self._encode_short([QuicStreamsBlockedFrame(limit=limit, bidirectional=bidirectional)])

    def reset_stream(self, stream_id: int, error_code: int) -> bytes:
        stream_state = self.streams.ensure_send_stream(stream_id)
        stream_state.mark_reset_sent(error_code, final_size=stream_state.send_offset)
        packet = self._encode_short([
            QuicResetStreamFrame(stream_id=stream_id, error_code=error_code, final_size=stream_state.send_final_size or stream_state.send_offset),
        ])
        self._maybe_queue_max_stream_credit(stream_id)
        return packet

    def stop_sending(self, stream_id: int, error_code: int) -> bytes:
        stream_state = self.streams.ensure_receive_stream(stream_id)
        stream_state.mark_stop_sending(error_code)
        return self._encode_short([QuicStopSendingFrame(stream_id=stream_id, error_code=error_code)])

    def _build_connection_close_frame(
        self,
        *,
        error_code: int,
        reason: str,
        application: bool,
        packet_space: str,
    ) -> QuicConnectionCloseFrame:
        if application and packet_space in {PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE}:
            return QuicConnectionCloseFrame(error_code=TRANSPORT_ERROR_APPLICATION_ERROR, reason='', application=False)
        return QuicConnectionCloseFrame(error_code=error_code, reason=reason, application=application)

    def close(
        self,
        error_code: int = 0,
        reason: str = '',
        *,
        application: bool = False,
        packet_space: str = PACKET_SPACE_APPLICATION,
    ) -> bytes:
        self.state = 'closing'
        frame = self._build_connection_close_frame(
            error_code=error_code,
            reason=reason,
            application=application,
            packet_space=packet_space,
        )
        return self.send_frames([frame], packet_space=packet_space)

    def configure_handshake(self, driver: QuicTlsHandshakeDriver) -> None:
        self.handshake_driver = driver
        self._update_local_transport_parameters()

    def start_handshake(self) -> bytes:
        self._refresh_tls_key_material()
        if self.handshake_driver is None:
            return self.build_initial()
        payload = self.handshake_driver.initiate()
        self._refresh_tls_key_material()
        return self._queue_handshake_payload(payload)

    def take_handshake_datagrams(self) -> list[bytes]:
        items = list(self._pending_handshake_datagrams)
        self._pending_handshake_datagrams.clear()
        return items

    def take_pending_datagrams(self) -> list[bytes]:
        return self.take_handshake_datagrams() + self.drain_scheduled_datagrams()

    def can_send_amplification_limited(self, size: int) -> bool:
        if self.address_validated or self.is_client:
            return True
        return self.bytes_sent + size <= (self.bytes_received * 3)

    def can_send_packet(self, size: int) -> bool:
        if not self.can_send_amplification_limited(size):
            return False
        return self.recovery.can_send(size)

    def issue_connection_id(self, *, sequence: int | None = None) -> tuple[int, bytes, bytes, bytes]:
        if sequence is None:
            sequence = self.connection_id_sequence
            self.connection_id_sequence += 1
        if len(self.issued_connection_ids) >= self._peer_active_connection_id_limit:
            raise ProtocolError('peer active_connection_id_limit would be exceeded')
        cid = generate_connection_id()
        token = derive_secret(cid + self.secret, b'stateless-reset', length=16)
        self.issued_connection_ids[sequence] = (cid, token)
        return sequence, cid, token, self._encode_short([
            QuicNewConnectionIdFrame(sequence=sequence, retire_prior_to=0, connection_id=cid, stateless_reset_token=token),
        ])

    def retire_connection_id(self, sequence: int) -> bytes:
        self.retire_connection_ids.append(sequence)
        self.issued_connection_ids.pop(sequence, None)
        return self._encode_short([QuicRetireConnectionIdFrame(sequence=sequence)])

    def issue_new_token(self, *, addr: tuple[str, int] | None) -> tuple[bytes, bytes]:
        if self.is_client:
            raise ProtocolError('only servers can issue NEW_TOKEN frames')
        token = self._issue_address_token(purpose=_TOKEN_PURPOSE_NEW_TOKEN, addr=addr)
        return token, self._encode_short([QuicNewTokenFrame(token=token)])

    def build_retry(
        self,
        initial: QuicLongHeaderPacket,
        *,
        client_addr: tuple[str, int] | None,
        source_connection_id: bytes | None = None,
    ) -> bytes:
        if self.is_client:
            raise ProtocolError('clients cannot send Retry packets')
        if initial.packet_type != QuicLongHeaderType.INITIAL:
            raise ProtocolError('Retry can only be sent in response to an Initial packet')
        retry_scid = source_connection_id or generate_connection_id()
        token = self._issue_address_token(
            purpose=_TOKEN_PURPOSE_RETRY,
            addr=client_addr,
            original_destination_connection_id=initial.destination_connection_id,
            retry_source_connection_id=retry_scid,
        )
        retry = QuicRetryPacket(
            version=initial.version,
            destination_connection_id=initial.source_connection_id,
            source_connection_id=retry_scid,
            token=token,
        )
        self._sent_retry = True
        self._retry_source_connection_id = retry_scid
        self._original_destination_connection_id = initial.destination_connection_id
        self._update_local_transport_parameters()
        return retry.encode(original_destination_connection_id=initial.destination_connection_id)

    def build_version_negotiation(
        self,
        *,
        destination_connection_id: bytes,
        source_connection_id: bytes | None = None,
        supported_versions: Sequence[int] | None = None,
    ) -> bytes:
        packet = QuicVersionNegotiationPacket(
            destination_connection_id=destination_connection_id,
            source_connection_id=source_connection_id if source_connection_id is not None else self.local_cid,
            supported_versions=list(supported_versions or self.supported_versions),
        )
        return packet.encode()

    def handle_version_negotiation(self, packet: QuicVersionNegotiationPacket) -> bool:
        if not self.is_client:
            return False
        if self.version in packet.supported_versions:
            return False
        for candidate in self.supported_versions:
            if candidate in packet.supported_versions:
                self.version = candidate
                self.state = 'version_negotiated'
                return True
        self.state = 'version_negotiation_failed'
        return False

    def build_stateless_reset(self, token: bytes) -> bytes:
        return QuicStatelessResetPacket(stateless_reset_token=token, unpredictable_bits=secrets.token_bytes(5)).encode()

    def _mark_received(self, packet_space: str, packet_number: int) -> None:
        state = self._space_state(packet_space)
        state.received_packets.add(packet_number)
        state.received_packet_times[packet_number] = time.monotonic()
        state.largest_received = max(state.largest_received, packet_number)
        self._sync_packet_number_snapshot()

    def _build_ack_frame(self, packet_space: str) -> QuicAckFrame:
        state = self._space_state(packet_space)
        if not state.received_packets:
            raise ProtocolError('no packets available to acknowledge')
        ordered = sorted(state.received_packets, reverse=True)
        ranges: list[tuple[int, int]] = []
        range_high = ordered[0]
        range_low = ordered[0]
        for packet_number in ordered[1:]:
            if packet_number == range_low - 1:
                range_low = packet_number
                continue
            ranges.append((range_low, range_high))
            range_high = packet_number
            range_low = packet_number
        ranges.append((range_low, range_high))
        largest_acked = ranges[0][1]
        first_ack_range = ranges[0][1] - ranges[0][0]
        ack_ranges: list[tuple[int, int]] = []
        previous_low = ranges[0][0]
        for range_low, range_high in ranges[1:]:
            gap = previous_low - range_high - 2
            ack_ranges.append((gap, range_high - range_low))
            previous_low = range_low
        local_ack_delay_exponent = self.local_transport_parameters.ack_delay_exponent if self.local_transport_parameters is not None else 3
        received_at = state.received_packet_times.get(largest_acked)
        ack_delay = 0
        if received_at is not None:
            delay_us = max(int((time.monotonic() - received_at) * 1_000_000), 0)
            ack_delay = delay_us // (1 << local_ack_delay_exponent)
        return QuicAckFrame(
            largest_acked=largest_acked,
            ack_delay=ack_delay,
            first_ack_range=first_ack_range,
            ack_ranges=ack_ranges,
        )

    def _parse_runtime_packet(self, data: bytes) -> tuple[Any, int, str]:
        if not data:
            raise ProtocolError('QUIC packet underflow')
        first_byte = data[0]
        if first_byte & 0x80:
            packet = decode_packet(data)
            if isinstance(packet, (QuicVersionNegotiationPacket, QuicRetryPacket, QuicStatelessResetPacket)):
                return packet, -1, PACKET_SPACE_INITIAL
            offset = 5
            dcid_len = data[offset]
            offset += 1 + dcid_len
            scid_len = data[offset]
            offset += 1 + scid_len
            packet_space = PACKET_SPACE_INITIAL
            if packet.packet_type == QuicLongHeaderType.INITIAL:
                token_length, offset = decode_quic_varint(data, offset)
                offset += token_length
                packet_space = PACKET_SPACE_INITIAL
            elif packet.packet_type == QuicLongHeaderType.HANDSHAKE:
                packet_space = PACKET_SPACE_HANDSHAKE
            elif packet.packet_type == QuicLongHeaderType.ZERO_RTT:
                packet_space = PACKET_SPACE_ZERO_RTT
            _payload_length, offset = decode_quic_varint(data, offset)
            return packet, offset, packet_space
        packet = decode_packet(data, destination_connection_id_length=max(len(self.local_cid), 1))
        return packet, 1 + len(packet.destination_connection_id), PACKET_SPACE_APPLICATION

    def _unprotect_short_packet(self, data: bytes, *, pn_offset: int) -> tuple[int, bytes, int]:
        current_keys = self._recv_1rtt_keys
        largest = self._space_state(PACKET_SPACE_APPLICATION).largest_received
        try:
            header, packet_number, plaintext = unprotect_quic_packet(
                data,
                pn_offset=pn_offset,
                keys=current_keys,
                largest_pn=largest,
            )
            observed_phase = 1 if (header[0] & 0x04) else 0
            if observed_phase != self._recv_key_phase:
                hash_name = self._tls_hash_name()
                updated_client_secret = update_quic_secret(self._client_application_secret, hash_name=hash_name)
                updated_server_secret = update_quic_secret(self._server_application_secret, hash_name=hash_name)
                candidate_recv_keys = self._derive_tls_packet_protection_keys(
                    updated_server_secret if self.is_client else updated_client_secret,
                    stage='application',
                )
                header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=candidate_recv_keys,
                    largest_pn=largest,
                )
                self._client_application_secret = updated_client_secret
                self._server_application_secret = updated_server_secret
                self.client_1rtt_keys = self._derive_tls_packet_protection_keys(self._client_application_secret, stage='application')
                self.server_1rtt_keys = self._derive_tls_packet_protection_keys(self._server_application_secret, stage='application')
                self._recv_key_phase = observed_phase
                self._send_key_phase = observed_phase
            return packet_number, plaintext, observed_phase
        except ProtocolError:
            hash_name = self._tls_hash_name()
            updated_client_secret = update_quic_secret(self._client_application_secret, hash_name=hash_name)
            updated_server_secret = update_quic_secret(self._server_application_secret, hash_name=hash_name)
            candidate_recv_keys = self._derive_tls_packet_protection_keys(
                updated_server_secret if self.is_client else updated_client_secret,
                stage='application',
            )
            header, packet_number, plaintext = unprotect_quic_packet(
                data,
                pn_offset=pn_offset,
                keys=candidate_recv_keys,
                largest_pn=largest,
            )
            self._client_application_secret = updated_client_secret
            self._server_application_secret = updated_server_secret
            self.client_1rtt_keys = self._derive_tls_packet_protection_keys(self._client_application_secret, stage='application')
            self.server_1rtt_keys = self._derive_tls_packet_protection_keys(self._server_application_secret, stage='application')
            self._recv_key_phase = 1 if (header[0] & 0x04) else 0
            self._send_key_phase = self._recv_key_phase
            return packet_number, plaintext, self._recv_key_phase

    def _decode_payload(self, data: bytes) -> tuple[Any, str, int, bytes]:
        packet, pn_offset, packet_space = self._parse_runtime_packet(data)
        if isinstance(packet, QuicVersionNegotiationPacket):
            return packet, packet_space, -1, b''
        if isinstance(packet, QuicRetryPacket):
            return packet, packet_space, -1, b''
        if isinstance(packet, QuicStatelessResetPacket):
            return packet, packet_space, -1, b''
        if isinstance(packet, QuicLongHeaderPacket):
            if packet.packet_type == QuicLongHeaderType.INITIAL:
                client_keys, server_keys = self._recv_initial_keys(packet)
                recv_keys = server_keys if self.is_client else client_keys
                _header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=recv_keys,
                    largest_pn=self._space_state(PACKET_SPACE_INITIAL).largest_received,
                )
                return packet, PACKET_SPACE_INITIAL, packet_number, plaintext
            if packet.packet_type == QuicLongHeaderType.HANDSHAKE:
                _header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=self._recv_handshake_keys(),
                    largest_pn=self._space_state(PACKET_SPACE_HANDSHAKE).largest_received,
                )
                return packet, PACKET_SPACE_HANDSHAKE, packet_number, plaintext
            if packet.packet_type == QuicLongHeaderType.ZERO_RTT:
                if self.is_client:
                    raise ProtocolError('clients must not receive 0-RTT packets')
                _header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=self._recv_0rtt_keys(),
                    largest_pn=self._space_state(PACKET_SPACE_APPLICATION).largest_received,
                )
                return packet, PACKET_SPACE_ZERO_RTT, packet_number, plaintext
            raise ProtocolError('unsupported QUIC long-header packet type')
        if isinstance(packet, QuicShortHeaderPacket):
            errors: list[Exception] = []
            for cid_length in self._short_header_destination_connection_id_lengths():
                try:
                    candidate = decode_packet(data, destination_connection_id_length=cid_length)
                    if not isinstance(candidate, QuicShortHeaderPacket):
                        continue
                    packet_number, plaintext, _key_phase = self._unprotect_short_packet(data, pn_offset=candidate.pn_offset)
                    return candidate, PACKET_SPACE_APPLICATION, packet_number, plaintext
                except ProtocolError as exc:
                    errors.append(exc)
                    continue
            raise ProtocolError(str(errors[-1]) if errors else 'failed to decode QUIC short-header packet')
        raise ProtocolError('unsupported QUIC packet')

    def _known_stateless_reset_tokens(self) -> set[bytes]:
        tokens = {token for _sequence, (_cid, token) in self.peer_connection_ids.items()}
        if self.peer_transport_parameters and self.peer_transport_parameters.stateless_reset_token is not None:
            tokens.add(self.peer_transport_parameters.stateless_reset_token)
        return tokens

    def _maybe_stateless_reset(self, data: bytes) -> QuicStatelessResetPacket | None:
        if len(data) < 21:
            return None
        token = data[-16:]
        if token not in self._known_stateless_reset_tokens():
            return None
        return QuicStatelessResetPacket(stateless_reset_token=token, unpredictable_bits=data[:-16])

    def _observe_path(self, addr: tuple[str, int] | None) -> QuicEvent | None:
        if addr is None:
            return None
        if self._path_addr is None:
            self._path_addr = addr
            self._activate_path(self._path_key_for_addr(addr))
            return None
        if self._path_addr == addr:
            self._activate_path(self._path_key_for_addr(addr))
            return None
        if self.local_transport_parameters and self.local_transport_parameters.disable_active_migration and self.address_validated:
            raise ProtocolError('peer changed address despite disable_active_migration')
        previous = self._path_addr
        self._path_addr = addr
        self._activate_path(self._path_key_for_addr(addr))
        return QuicEvent(kind='path_migrated', detail={'from': previous, 'to': addr})

    def _short_header_destination_connection_id_lengths(self) -> tuple[int, ...]:
        lengths: list[int] = []
        for candidate in (
            self.local_cid,
            self.remote_cid,
            *(cid for cid, _token in self.issued_connection_ids.values()),
            *(cid for cid, _token in self.peer_connection_ids.values()),
        ):
            if candidate:
                length = len(candidate)
                if 1 <= length <= 20 and length not in lengths:
                    lengths.append(length)
        if not lengths:
            lengths.append(1)
        return tuple(lengths)

    def _peek_packet(self, data: bytes) -> Any:
        if not data:
            raise ProtocolError('QUIC packet underflow')
        if data[0] & 0x80:
            return decode_packet(data)
        return decode_packet(data, destination_connection_id_length=self._short_header_destination_connection_id_lengths()[0])

    def _server_maybe_handle_token_or_retry(
        self,
        packet: QuicLongHeaderPacket,
        *,
        addr: tuple[str, int] | None,
    ) -> list[QuicEvent] | None:
        if self.is_client or packet.packet_type != QuicLongHeaderType.INITIAL:
            return None
        if self._original_destination_connection_id is None:
            self._original_destination_connection_id = packet.destination_connection_id
        if self._peer_initial_source_connection_id is None:
            self._peer_initial_source_connection_id = packet.source_connection_id
        self._update_local_transport_parameters()
        if packet.token:
            token_info = self._validate_address_token(packet.token, addr=addr)
            if token_info is None:
                close_packet = self.close(
                    error_code=TRANSPORT_ERROR_INVALID_TOKEN,
                    reason='invalid token',
                    packet_space=PACKET_SPACE_INITIAL,
                )
                self._pending_handshake_datagrams.append(close_packet)
                return [
                    QuicEvent(
                        kind='close',
                        packet_space=PACKET_SPACE_INITIAL,
                        detail=QuicConnectionCloseFrame(error_code=TRANSPORT_ERROR_INVALID_TOKEN, reason='invalid token'),
                    )
                ]
            if token_info.purpose == _TOKEN_PURPOSE_RETRY:
                if token_info.original_destination_connection_id != self._original_destination_connection_id:
                    raise ProtocolError('Retry token original destination connection id mismatch')
                if self._retry_source_connection_id is not None and token_info.retry_source_connection_id not in {b'', self._retry_source_connection_id}:
                    raise ProtocolError('Retry token source connection id mismatch')
                self.address_validated = True
            elif token_info.purpose == _TOKEN_PURPOSE_NEW_TOKEN:
                self.address_validated = True
            else:
                raise ProtocolError('unknown QUIC token purpose')
            return None
        if self.require_retry and not self.address_validated:
            retry = self.build_retry(packet, client_addr=addr)
            self._pending_handshake_datagrams.append(retry)
            return [QuicEvent(kind='retry', detail=decode_packet(retry))]
        return None

    def _handle_retry_packet(self, packet: QuicRetryPacket) -> list[QuicEvent]:
        if not self.is_client:
            raise ProtocolError('servers must not process Retry packets for an active connection')
        if self._received_retry:
            return [QuicEvent(kind='retry_ignored', detail=packet)]
        if not packet.token:
            raise ProtocolError('received Retry packet without a token')
        original_destination_connection_id = self._original_destination_connection_id or self.remote_cid
        if not packet.validate(original_destination_connection_id=original_destination_connection_id):
            raise ProtocolError('invalid Retry integrity tag')
        self._received_retry = True
        self._retry_token = packet.token
        self._retry_source_connection_id = packet.source_connection_id
        self.remote_cid = packet.source_connection_id
        self.recovery.discard_space(PACKET_SPACE_INITIAL)
        self._update_local_transport_parameters()
        return [QuicEvent(kind='retry', detail=packet)]

    def _receive_single_packet(self, data: bytes, *, addr: tuple[str, int] | None) -> list[QuicEvent]:
        try:
            peek = self._peek_packet(data)
        except ProtocolError:
            stateless_reset = self._maybe_stateless_reset(data)
            if stateless_reset is not None:
                self.state = 'closed'
                return [QuicEvent(kind='stateless_reset', detail=stateless_reset)]
            return [QuicEvent(kind='integrity_error')]

        if isinstance(peek, QuicVersionNegotiationPacket):
            self.handle_version_negotiation(peek)
            return [QuicEvent(kind='version_negotiation', detail=peek)]

        if isinstance(peek, QuicLongHeaderPacket) and peek.version not in self.supported_versions:
            if not self.is_client and peek.packet_type in {QuicLongHeaderType.INITIAL, QuicLongHeaderType.ZERO_RTT}:
                version_negotiation = self.build_version_negotiation(
                    destination_connection_id=peek.source_connection_id,
                    source_connection_id=peek.destination_connection_id,
                )
                self._pending_handshake_datagrams.append(version_negotiation)
                detail = decode_packet(version_negotiation)
                return [QuicEvent(kind='version_negotiation_sent', detail=detail)]
            return [QuicEvent(kind='version_negotiation', detail=peek.version)]

        if isinstance(peek, QuicRetryPacket):
            return self._handle_retry_packet(peek)

        if isinstance(peek, QuicLongHeaderPacket):
            maybe_retry = self._server_maybe_handle_token_or_retry(peek, addr=addr)
            if maybe_retry is not None:
                return maybe_retry

        try:
            packet, packet_space, packet_number, plaintext = self._decode_payload(data)
        except ProtocolError:
            stateless_reset = self._maybe_stateless_reset(data)
            if stateless_reset is not None:
                self.state = 'closed'
                return [QuicEvent(kind='stateless_reset', detail=stateless_reset)]
            return [QuicEvent(kind='integrity_error')]

        if isinstance(packet, QuicVersionNegotiationPacket):
            self.handle_version_negotiation(packet)
            return [QuicEvent(kind='version_negotiation', detail=packet)]
        if isinstance(packet, QuicRetryPacket):
            return self._handle_retry_packet(packet)
        if isinstance(packet, QuicStatelessResetPacket):
            self.state = 'closed'
            return [QuicEvent(kind='stateless_reset', detail=packet)]

        if isinstance(packet, QuicLongHeaderPacket):
            if self.is_client and packet.source_connection_id and self._first_server_source_connection_id is None:
                self._first_server_source_connection_id = packet.source_connection_id
            elif not self.is_client and packet.source_connection_id and self._peer_initial_source_connection_id is None:
                self._peer_initial_source_connection_id = packet.source_connection_id
            self.remote_cid = packet.source_connection_id or self.remote_cid
            if not self.is_client:
                self.local_cid = packet.destination_connection_id or self.local_cid
                if self.handshake_driver is not None:
                    self._update_local_transport_parameters()
        self._mark_received(packet_space, packet_number)
        events: list[QuicEvent] = [QuicEvent(kind='packet', packet_number=packet_number, packet_space=packet_space, detail=packet)]
        ack_eliciting_received = False
        offset = 0
        while offset < len(plaintext):
            frame, offset = decode_frame(plaintext, offset)
            validate_frame_for_packet_space(frame, packet_space, is_client=not self.is_client)
            if frame == FRAME_PING:
                ack_eliciting_received = True
                self.state = 'established'
                events.append(QuicEvent(kind='ping', packet_number=packet_number, packet_space=packet_space))
                continue
            if frame == FRAME_PADDING:
                continue
            if isinstance(frame, QuicAckFrame):
                self._handle_ack_frame(frame, packet_space=packet_space)
                events.append(QuicEvent(kind='ack', packet_number=frame.largest_acked, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicCryptoFrame):
                ack_eliciting_received = True
                crypto_data = self._space_state(packet_space).crypto_receive.apply(frame.offset, frame.data)
                should_process_crypto = bool(
                    crypto_data
                    and self.handshake_driver is not None
                    and (not self.handshake_driver.complete or self.is_client)
                )
                if should_process_crypto:
                    was_complete = bool(self.handshake_driver.complete)
                    try:
                        outbound = self.handshake_driver.receive(crypto_data)
                    except ProtocolError as exc:
                        self.state = 'closing'
                        error_code = int(getattr(exc, 'quic_error_code', TRANSPORT_ERROR_PROTOCOL_VIOLATION))
                        self._pending_handshake_datagrams.insert(
                            0,
                            self.close(error_code=error_code, reason=str(exc), packet_space=packet_space),
                        )
                        events.append(QuicEvent(kind='close', packet_space=packet_space, detail=QuicConnectionCloseFrame(error_code=error_code, reason=str(exc))))
                        break
                    self._refresh_tls_key_material()
                    self._apply_peer_transport_parameters()
                    if outbound:
                        first = self._queue_handshake_payload(outbound)
                        if first:
                            self._pending_handshake_datagrams.insert(0, first)
                    if self.handshake_driver.complete:
                        self.address_validated = True
                        self.recovery.discard_space(PACKET_SPACE_INITIAL)
                        if not self.is_client and not self._handshake_done_sent:
                            self._pending_handshake_datagrams.append(self.handshake_done())
                        if not was_complete:
                            events.append(QuicEvent(kind='handshake_complete', packet_number=packet_number, packet_space=packet_space))
                        if self.is_client and self._peer_preferred_address is not None:
                            events.append(QuicEvent(kind='preferred_address', detail=self._peer_preferred_address, packet_space=PACKET_SPACE_APPLICATION))
                events.append(QuicEvent(kind='crypto', data=frame.data, packet_number=packet_number, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicNewTokenFrame):
                ack_eliciting_received = True
                self._peer_new_tokens.append(frame.token)
                events.append(QuicEvent(kind='new_token', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicMaxDataFrame):
                ack_eliciting_received = True
                self.flow.update_send_limit_connection(frame.maximum_data)
                events.append(QuicEvent(kind='max_data', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicMaxStreamDataFrame):
                ack_eliciting_received = True
                self.flow.update_send_limit_stream(frame.stream_id, frame.maximum_data)
                events.append(QuicEvent(kind='max_stream_data', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicMaxStreamsFrame):
                ack_eliciting_received = True
                self.streams.update_peer_max_streams(frame.maximum_streams, bidirectional=frame.bidirectional)
                events.append(QuicEvent(kind='max_streams', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicDataBlockedFrame):
                ack_eliciting_received = True
                events.append(QuicEvent(kind='data_blocked', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicStreamDataBlockedFrame):
                ack_eliciting_received = True
                events.append(QuicEvent(kind='stream_data_blocked', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicStreamsBlockedFrame):
                ack_eliciting_received = True
                events.append(QuicEvent(kind='streams_blocked', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicNewConnectionIdFrame):
                ack_eliciting_received = True
                if frame.retire_prior_to > frame.sequence:
                    raise ProtocolError('invalid retire_prior_to in NEW_CONNECTION_ID')
                if len(self.peer_connection_ids) >= self._peer_active_connection_id_limit and frame.sequence not in self.peer_connection_ids:
                    raise ProtocolError('peer exceeded active_connection_id_limit')
                self.peer_connection_ids[frame.sequence] = (frame.connection_id, frame.stateless_reset_token)
                for sequence in [sequence for sequence in self.peer_connection_ids if sequence < frame.retire_prior_to]:
                    self.peer_connection_ids.pop(sequence, None)
                    self.retire_connection_ids.append(sequence)
                events.append(QuicEvent(kind='new_connection_id', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicRetireConnectionIdFrame):
                ack_eliciting_received = True
                self.issued_connection_ids.pop(frame.sequence, None)
                events.append(QuicEvent(kind='retire_connection_id', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicPathChallengeFrame):
                ack_eliciting_received = True
                self._pending_handshake_datagrams.append(self.path_response(frame.data))
                events.append(QuicEvent(kind='path_challenge', data=frame.data, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicPathResponseFrame):
                ack_eliciting_received = True
                if frame.data in self.path_challenges:
                    self.address_validated = True
                    self.path_challenges.discard(frame.data)
                events.append(QuicEvent(kind='path_response', data=frame.data, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicHandshakeDoneFrame):
                ack_eliciting_received = True
                self.state = 'established'
                self.address_validated = True
                self.recovery.discard_space(PACKET_SPACE_HANDSHAKE)
                events.append(QuicEvent(kind='handshake_done', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicResetStreamFrame):
                ack_eliciting_received = True
                self.flow.validate_receive(frame.stream_id, final_size=frame.final_size)
                self.streams.apply_reset(frame)
                self.flow.commit_receive(frame.stream_id, final_size=frame.final_size)
                self._maybe_queue_max_stream_credit(frame.stream_id)
                events.append(QuicEvent(kind='reset_stream', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicStopSendingFrame):
                ack_eliciting_received = True
                stream_state = self.streams.ensure_send_stream(frame.stream_id)
                stream_state.mark_stop_sending(frame.error_code)
                if not stream_state.send_terminal:
                    self._pending_handshake_datagrams.append(self.reset_stream(frame.stream_id, frame.error_code))
                events.append(QuicEvent(kind='stop_sending', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicConnectionCloseFrame):
                self.state = 'draining'
                events.append(QuicEvent(kind='application_close' if frame.application else 'transport_close', packet_space=packet_space, detail=frame))
                events.append(QuicEvent(kind='close', packet_space=packet_space, detail=frame))
                break
            if isinstance(frame, QuicStreamFrame):
                ack_eliciting_received = True
                final_size = frame.offset + len(frame.data) if frame.fin else None
                self.flow.validate_receive(frame.stream_id, end_offset=frame.offset + len(frame.data), final_size=final_size)
                stream_state = self.streams.ensure_receive_stream(frame.stream_id)
                data_chunk, _delta = stream_state.apply_with_metrics(frame)
                self.flow.commit_receive(frame.stream_id, end_offset=frame.offset + len(frame.data), final_size=final_size)
                self._maybe_queue_max_stream_credit(frame.stream_id)
                self.state = 'established'
                events.append(
                    QuicEvent(
                        kind='stream',
                        stream_id=frame.stream_id,
                        data=data_chunk,
                        fin=stream_state.received_final,
                        packet_number=packet_number,
                        packet_space=packet_space,
                        detail=frame,
                    )
                )
                continue
        if ack_eliciting_received:
            self._schedule_ack(packet_space, immediate=packet_space in {PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE})
        self._run_loss_detection()
        return events

    def receive_datagram(self, data: bytes, *, addr: tuple[str, int] | None = None) -> list[QuicEvent]:
        self.bytes_received += len(data)
        try:
            path_event = self._observe_path(addr)
        except ProtocolError as exc:
            self.state = 'closing'
            self._pending_handshake_datagrams.append(
                self.close(error_code=TRANSPORT_ERROR_PROTOCOL_VIOLATION, reason=str(exc))
            )
            return [QuicEvent(kind='close', detail=QuicConnectionCloseFrame(error_code=TRANSPORT_ERROR_PROTOCOL_VIOLATION, reason=str(exc)))]
        try:
            packets = split_coalesced_packets(data, destination_connection_id_length=max(len(self.local_cid), 1))
        except ProtocolError:
            stateless_reset = self._maybe_stateless_reset(data)
            if stateless_reset is not None:
                self.state = 'closed'
                return [QuicEvent(kind='stateless_reset', detail=stateless_reset)]
            return [QuicEvent(kind='integrity_error')]
        events: list[QuicEvent] = []
        if path_event is not None:
            events.append(path_event)
        for packet in packets:
            events.extend(self._receive_single_packet(packet, addr=addr))
        return events

    def next_pto_deadline(self) -> float | None:
        deadline: float | None = None
        for path_state in self._path_states.values():
            candidate = path_state.recovery.next_pto_deadline()
            if candidate is None:
                continue
            deadline = candidate if deadline is None else min(deadline, candidate)
        return deadline

    def detect_lost_packets(self) -> list[int]:
        lost: list[int] = []
        at = time.monotonic()
        for path_key, path_state in self._path_states.items():
            for packet_space in tuple(path_state.recovery.spaces):
                lost_numbers = path_state.recovery.detect_lost_packets(now=at, packet_space=packet_space)
                if lost_numbers:
                    self._on_packets_lost(path_key=path_key, packet_space=packet_space, lost_numbers=lost_numbers)
                    lost.extend(lost_numbers)
        self._update_runtime_timers(now=at)
        return sorted(set(lost))

    def loss_recovery_snapshot(self):
        return self.recovery.snapshot()
