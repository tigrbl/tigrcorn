from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint, pack_varbytes, unpack_varbytes

FRAME_PADDING = 0x00
FRAME_PING = 0x01
FRAME_ACK = 0x02
FRAME_RESET_STREAM = 0x04
FRAME_STOP_SENDING = 0x05
FRAME_CRYPTO = 0x06
FRAME_NEW_TOKEN = 0x07
FRAME_STREAM = 0x08
FRAME_MAX_DATA = 0x10
FRAME_MAX_STREAM_DATA = 0x11
FRAME_MAX_STREAMS_BIDI = 0x12
FRAME_MAX_STREAMS_UNI = 0x13
FRAME_DATA_BLOCKED = 0x14
FRAME_STREAM_DATA_BLOCKED = 0x15
FRAME_STREAMS_BLOCKED_BIDI = 0x16
FRAME_STREAMS_BLOCKED_UNI = 0x17
FRAME_NEW_CONNECTION_ID = 0x18
FRAME_RETIRE_CONNECTION_ID = 0x19
FRAME_PATH_CHALLENGE = 0x1A
FRAME_PATH_RESPONSE = 0x1B
FRAME_CONNECTION_CLOSE = 0x1C
FRAME_CONNECTION_CLOSE_APP = 0x1D
FRAME_HANDSHAKE_DONE = 0x1E

_PACKET_SPACE_INITIAL = 'initial'
_PACKET_SPACE_HANDSHAKE = 'handshake'
_PACKET_SPACE_APPLICATION = 'application'
_PACKET_SPACE_ZERO_RTT = '0rtt'


@dataclass(slots=True)
class QuicStreamFrame:
    stream_id: int
    offset: int = 0
    fin: bool = False
    data: bytes = b''


@dataclass(slots=True)
class QuicAckFrame:
    largest_acked: int
    ack_delay: int = 0
    first_ack_range: int = 0
    ack_ranges: list[tuple[int, int]] = field(default_factory=list)

    def acknowledged_packets(self) -> list[int]:
        packets = list(range(self.largest_acked - self.first_ack_range, self.largest_acked + 1))
        smallest = self.largest_acked - self.first_ack_range
        for gap, ack_range_length in self.ack_ranges:
            range_high = smallest - gap - 2
            range_low = range_high - ack_range_length
            packets.extend(range(range_low, range_high + 1))
            smallest = range_low
        return sorted({packet for packet in packets if packet >= 0})


@dataclass(slots=True)
class QuicResetStreamFrame:
    stream_id: int
    error_code: int
    final_size: int


@dataclass(slots=True)
class QuicStopSendingFrame:
    stream_id: int
    error_code: int


@dataclass(slots=True)
class QuicCryptoFrame:
    offset: int
    data: bytes


@dataclass(slots=True)
class QuicNewTokenFrame:
    token: bytes


@dataclass(slots=True)
class QuicMaxDataFrame:
    maximum_data: int


@dataclass(slots=True)
class QuicMaxStreamDataFrame:
    stream_id: int
    maximum_data: int


@dataclass(slots=True)
class QuicMaxStreamsFrame:
    maximum_streams: int
    bidirectional: bool = True


@dataclass(slots=True)
class QuicDataBlockedFrame:
    limit: int


@dataclass(slots=True)
class QuicStreamDataBlockedFrame:
    stream_id: int
    limit: int


@dataclass(slots=True)
class QuicStreamsBlockedFrame:
    limit: int
    bidirectional: bool = True


@dataclass(slots=True)
class QuicNewConnectionIdFrame:
    sequence: int
    retire_prior_to: int
    connection_id: bytes
    stateless_reset_token: bytes


@dataclass(slots=True)
class QuicRetireConnectionIdFrame:
    sequence: int


@dataclass(slots=True)
class QuicPathChallengeFrame:
    data: bytes

    def __post_init__(self) -> None:
        if len(self.data) != 8:
            raise ProtocolError('PATH_CHALLENGE data must be 8 bytes')


@dataclass(slots=True)
class QuicPathResponseFrame:
    data: bytes

    def __post_init__(self) -> None:
        if len(self.data) != 8:
            raise ProtocolError('PATH_RESPONSE data must be 8 bytes')


@dataclass(slots=True)
class QuicHandshakeDoneFrame:
    pass


@dataclass(slots=True)
class QuicConnectionCloseFrame:
    error_code: int
    frame_type: int = 0
    reason: str = ''
    application: bool = False


QuicFrame = (
    QuicStreamFrame
    | QuicAckFrame
    | QuicResetStreamFrame
    | QuicStopSendingFrame
    | QuicCryptoFrame
    | QuicNewTokenFrame
    | QuicMaxDataFrame
    | QuicMaxStreamDataFrame
    | QuicMaxStreamsFrame
    | QuicDataBlockedFrame
    | QuicStreamDataBlockedFrame
    | QuicStreamsBlockedFrame
    | QuicNewConnectionIdFrame
    | QuicRetireConnectionIdFrame
    | QuicPathChallengeFrame
    | QuicPathResponseFrame
    | QuicHandshakeDoneFrame
    | QuicConnectionCloseFrame
    | int
)


@dataclass(slots=True)
class QuicStreamState:
    stream_id: int
    local_is_client: bool = True
    received: bytearray = field(default_factory=bytearray)
    pending: dict[int, bytes] = field(default_factory=dict)
    received_final: bool = False
    final_offset: int | None = None
    send_offset: int = 0
    reset: QuicResetStreamFrame | None = None
    highest_received_offset: int = 0
    send_final_size: int | None = None
    send_reset_error_code: int | None = None
    stop_sending_error_code: int | None = None
    send_state: 'QuicStreamSendState' = field(init=False)
    receive_state: 'QuicStreamReceiveState' = field(init=False)
    credit_released: bool = False

    def __post_init__(self) -> None:
        if self.stream_id < 0:
            raise ProtocolError('negative QUIC stream id')
        self.send_state = QuicStreamSendState.READY if self.can_send else QuicStreamSendState.DISABLED
        self.receive_state = QuicStreamReceiveState.RECV if self.can_receive else QuicStreamReceiveState.DISABLED

    @property
    def initiated_by_client(self) -> bool:
        return stream_is_client_initiated(self.stream_id)

    @property
    def unidirectional(self) -> bool:
        return stream_is_unidirectional(self.stream_id)

    @property
    def local_initiated(self) -> bool:
        return stream_is_local_initiated(self.stream_id, local_is_client=self.local_is_client)

    @property
    def peer_initiated(self) -> bool:
        return not self.local_initiated

    @property
    def can_send(self) -> bool:
        return not (self.unidirectional and self.peer_initiated)

    @property
    def can_receive(self) -> bool:
        return not (self.unidirectional and self.local_initiated)

    @property
    def send_terminal(self) -> bool:
        return self.send_state in {QuicStreamSendState.DATA_SENT, QuicStreamSendState.RESET_SENT, QuicStreamSendState.DISABLED}

    @property
    def receive_terminal(self) -> bool:
        return self.receive_state in {
            QuicStreamReceiveState.DATA_RECVD,
            QuicStreamReceiveState.DATA_READ,
            QuicStreamReceiveState.RESET_RECVD,
            QuicStreamReceiveState.RESET_READ,
            QuicStreamReceiveState.DISABLED,
        }

    @property
    def closed(self) -> bool:
        return self.send_terminal and self.receive_terminal

    def _append_contiguous(self, chunk: bytes, newly_available: bytearray) -> None:
        if not chunk:
            return
        self.received.extend(chunk)
        newly_available.extend(chunk)

    def _merge_pending(self, newly_available: bytearray) -> None:
        while True:
            start = len(self.received)
            chunk = self.pending.pop(start, None)
            if chunk is None:
                break
            self._append_contiguous(chunk, newly_available)

    def _store_pending(self, offset: int, data: bytes) -> None:
        existing = self.pending.get(offset)
        if existing is None or len(existing) < len(data):
            self.pending[offset] = data

    def reserve_send(self, data: bytes, *, fin: bool = False) -> int:
        if not self.can_send:
            raise ProtocolError('cannot send on a receive-only QUIC stream')
        if self.send_state in {QuicStreamSendState.DATA_SENT, QuicStreamSendState.RESET_SENT}:
            raise ProtocolError('QUIC stream send side is closed')
        offset = self.send_offset
        end_offset = offset + len(data)
        if self.send_final_size is not None:
            if end_offset > self.send_final_size:
                raise ProtocolError('local QUIC stream final size exceeded')
            if fin and end_offset != self.send_final_size:
                raise ProtocolError('inconsistent local QUIC final size')
            if not fin and end_offset == self.send_final_size:
                raise ProtocolError('cannot extend a finished QUIC stream')
        if fin:
            self.send_final_size = end_offset
            self.send_state = QuicStreamSendState.DATA_SENT
        elif len(data) or self.send_state == QuicStreamSendState.READY:
            self.send_state = QuicStreamSendState.SEND
        self.send_offset = end_offset
        return offset

    def mark_stop_sending(self, error_code: int) -> None:
        if not self.can_receive:
            raise ProtocolError('STOP_SENDING is invalid for send-only QUIC streams')
        self.stop_sending_error_code = error_code

    def mark_reset_sent(self, error_code: int, *, final_size: int | None = None) -> None:
        if not self.can_send:
            raise ProtocolError('RESET_STREAM is invalid for receive-only QUIC streams')
        effective_final_size = self.send_offset if final_size is None else final_size
        if effective_final_size < self.send_offset:
            raise ProtocolError('RESET_STREAM final size cannot be below sent data')
        if self.send_final_size is not None and self.send_final_size != effective_final_size:
            raise ProtocolError('inconsistent local QUIC final size')
        self.send_final_size = effective_final_size
        self.send_reset_error_code = error_code
        self.send_state = QuicStreamSendState.RESET_SENT

    def apply_with_metrics(self, frame: QuicStreamFrame) -> tuple[bytes, int]:
        if not self.can_receive:
            raise ProtocolError('received STREAM frame on send-only QUIC stream')
        if frame.offset < 0:
            raise ProtocolError('negative QUIC stream offset')
        end_offset = frame.offset + len(frame.data)
        if end_offset < frame.offset:
            raise ProtocolError('invalid QUIC stream offset arithmetic')
        if self.final_offset is not None and end_offset > self.final_offset:
            raise ProtocolError('QUIC stream data exceeds final size')
        if frame.fin:
            final_offset = end_offset
            if final_offset < self.highest_received_offset:
                raise ProtocolError('inconsistent QUIC final size')
            if self.final_offset is None:
                self.final_offset = final_offset
            elif self.final_offset != final_offset:
                raise ProtocolError('inconsistent QUIC final size')
            if self.receive_state == QuicStreamReceiveState.RECV:
                self.receive_state = QuicStreamReceiveState.SIZE_KNOWN
        if self.reset is not None:
            return b'', 0
        previous_highest = self.highest_received_offset
        if end_offset > self.highest_received_offset:
            self.highest_received_offset = end_offset
        contiguous = len(self.received)
        newly_available = bytearray()
        if frame.offset > contiguous:
            self._store_pending(frame.offset, bytes(frame.data))
        elif frame.offset < contiguous:
            overlap = contiguous - frame.offset
            if overlap < len(frame.data):
                suffix = frame.data[overlap:]
                self._append_contiguous(suffix, newly_available)
        else:
            self._append_contiguous(frame.data, newly_available)
        self._merge_pending(newly_available)
        if self.final_offset is not None and len(self.received) >= self.final_offset:
            self.received_final = True
            self.receive_state = QuicStreamReceiveState.DATA_RECVD
        elif self.final_offset is not None:
            self.receive_state = QuicStreamReceiveState.SIZE_KNOWN
        return bytes(newly_available), self.highest_received_offset - previous_highest

    def apply(self, frame: QuicStreamFrame) -> bytes:
        data, _delta = self.apply_with_metrics(frame)
        return data

    def apply_reset_with_delta(self, frame: QuicResetStreamFrame) -> int:
        if not self.can_receive:
            raise ProtocolError('received RESET_STREAM on send-only QUIC stream')
        if self.final_offset is not None and self.final_offset != frame.final_size:
            raise ProtocolError('inconsistent QUIC final size')
        if frame.final_size < self.highest_received_offset:
            raise ProtocolError('inconsistent QUIC final size')
        previous_accounted = max(self.highest_received_offset, self.final_offset or 0)
        self.final_offset = frame.final_size
        self.received_final = True
        self.reset = frame
        self.receive_state = QuicStreamReceiveState.RESET_RECVD
        return max(frame.final_size - previous_accounted, 0)

    def apply_reset(self, frame: QuicResetStreamFrame) -> None:
        self.apply_reset_with_delta(frame)

    def mark_data_read(self) -> None:
        if self.receive_state == QuicStreamReceiveState.DATA_RECVD:
            self.receive_state = QuicStreamReceiveState.DATA_READ
        elif self.receive_state == QuicStreamReceiveState.RESET_RECVD:
            self.receive_state = QuicStreamReceiveState.RESET_READ


class QuicStreamSendState(str, Enum):
    READY = 'ready'
    SEND = 'send'
    DATA_SENT = 'data_sent'
    RESET_SENT = 'reset_sent'
    DISABLED = 'disabled'


class QuicStreamReceiveState(str, Enum):
    RECV = 'recv'
    SIZE_KNOWN = 'size_known'
    DATA_RECVD = 'data_recvd'
    DATA_READ = 'data_read'
    RESET_RECVD = 'reset_recvd'
    RESET_READ = 'reset_read'
    DISABLED = 'disabled'


def stream_is_client_initiated(stream_id: int) -> bool:
    if stream_id < 0:
        raise ProtocolError('negative QUIC stream id')
    return (stream_id & 0x01) == 0


def stream_is_unidirectional(stream_id: int) -> bool:
    if stream_id < 0:
        raise ProtocolError('negative QUIC stream id')
    return (stream_id & 0x02) != 0


def stream_is_local_initiated(stream_id: int, *, local_is_client: bool) -> bool:
    return stream_is_client_initiated(stream_id) == local_is_client


class QuicStreamManager:
    def __init__(
        self,
        *,
        local_is_client: bool = True,
        peer_max_streams_bidi: int = 128,
        peer_max_streams_uni: int = 128,
        local_max_streams_bidi: int = 128,
        local_max_streams_uni: int = 128,
    ) -> None:
        self.local_is_client = local_is_client
        self._streams: dict[int, QuicStreamState] = {}
        self._next_stream_ids: dict[tuple[bool, bool], int] = {
            (True, False): 0,
            (False, False): 1,
            (True, True): 2,
            (False, True): 3,
        }
        self._peer_max_streams: dict[bool, int] = {
            True: max(peer_max_streams_bidi, 0),
            False: max(peer_max_streams_uni, 0),
        }
        self._local_max_streams_current: dict[bool, int] = {
            True: max(local_max_streams_bidi, 0),
            False: max(local_max_streams_uni, 0),
        }
        self._opened_local_ordinals: dict[bool, int] = {True: 0, False: 0}
        self._opened_peer_ordinals: dict[bool, int] = {True: 0, False: 0}

    def _stream_ordinal(self, stream_id: int) -> int:
        if stream_id < 0:
            raise ProtocolError('negative QUIC stream id')
        return (stream_id // 4) + 1

    def _create_state(self, stream_id: int) -> QuicStreamState:
        return QuicStreamState(stream_id=stream_id, local_is_client=self.local_is_client)

    def get(self, stream_id: int) -> QuicStreamState:
        return self._streams.setdefault(stream_id, self._create_state(stream_id))

    def configure_peer_initial_limits(self, *, bidirectional: int, unidirectional: int) -> None:
        self._peer_max_streams[True] = max(bidirectional, 0)
        self._peer_max_streams[False] = max(unidirectional, 0)

    def configure_local_initial_limits(self, *, bidirectional: int, unidirectional: int) -> None:
        self._local_max_streams_current[True] = max(bidirectional, self._opened_peer_ordinals[True])
        self._local_max_streams_current[False] = max(unidirectional, self._opened_peer_ordinals[False])

    def peer_stream_limit(self, *, bidirectional: bool) -> int:
        return self._peer_max_streams[bidirectional]

    def local_stream_limit(self, *, bidirectional: bool) -> int:
        return self._local_max_streams_current[bidirectional]

    def update_peer_max_streams(self, maximum_streams: int, *, bidirectional: bool) -> None:
        if maximum_streams > self._peer_max_streams[bidirectional]:
            self._peer_max_streams[bidirectional] = maximum_streams

    def next_stream_id(self, *, client: bool = False, unidirectional: bool = False) -> int:
        key = (client, unidirectional)
        stream_id = self._next_stream_ids[key]
        bidirectional = not unidirectional
        if client == self.local_is_client:
            ordinal = self._stream_ordinal(stream_id)
            if ordinal > self._peer_max_streams[bidirectional]:
                raise ProtocolError('peer stream limit prevents opening another QUIC stream')
            self._opened_local_ordinals[bidirectional] = max(self._opened_local_ordinals[bidirectional], ordinal)
        self._next_stream_ids[key] += 4
        return stream_id

    def ensure_send_stream(self, stream_id: int) -> QuicStreamState:
        state = self._streams.get(stream_id)
        if state is None:
            candidate = self._create_state(stream_id)
            bidirectional = not candidate.unidirectional
            ordinal = self._stream_ordinal(stream_id)
            if candidate.local_initiated:
                if ordinal > self._peer_max_streams[bidirectional]:
                    raise ProtocolError('peer stream limit exceeded')
                self._opened_local_ordinals[bidirectional] = max(self._opened_local_ordinals[bidirectional], ordinal)
                state = candidate
                self._streams[stream_id] = state
            else:
                raise ProtocolError('peer-initiated QUIC stream is not open')
        if not state.can_send:
            raise ProtocolError('cannot send on a receive-only QUIC stream')
        return state

    def ensure_receive_stream(self, stream_id: int) -> QuicStreamState:
        state = self._streams.get(stream_id)
        if state is None:
            candidate = self._create_state(stream_id)
            bidirectional = not candidate.unidirectional
            ordinal = self._stream_ordinal(stream_id)
            if candidate.peer_initiated:
                if ordinal > self._local_max_streams_current[bidirectional]:
                    raise ProtocolError('peer exceeded advertised QUIC stream limit')
                self._opened_peer_ordinals[bidirectional] = max(self._opened_peer_ordinals[bidirectional], ordinal)
                state = candidate
                self._streams[stream_id] = state
            else:
                if candidate.unidirectional:
                    raise ProtocolError('received STREAM data on a local unidirectional stream')
                if ordinal > self._opened_local_ordinals[bidirectional]:
                    raise ProtocolError('peer sent on a QUIC stream that was not opened locally')
                state = candidate
                self._streams[stream_id] = state
        if not state.can_receive:
            raise ProtocolError('received data on a send-only QUIC stream')
        return state

    def apply(self, frame: QuicStreamFrame) -> bytes:
        return self.ensure_receive_stream(frame.stream_id).apply(frame)

    def apply_reset(self, frame: QuicResetStreamFrame) -> None:
        self.ensure_receive_stream(frame.stream_id).apply_reset(frame)

    def maybe_release_peer_stream_credit(self, stream_id: int) -> QuicMaxStreamsFrame | None:
        state = self._streams.get(stream_id)
        if state is None or not state.peer_initiated or not state.closed or state.credit_released:
            return None
        state.credit_released = True
        bidirectional = not state.unidirectional
        self._local_max_streams_current[bidirectional] += 1
        return QuicMaxStreamsFrame(maximum_streams=self._local_max_streams_current[bidirectional], bidirectional=bidirectional)


QUIC_FRAME_TYPE_LABELS: dict[int, str] = {
    FRAME_PADDING: 'PADDING',
    FRAME_PING: 'PING',
    FRAME_ACK: 'ACK',
    FRAME_RESET_STREAM: 'RESET_STREAM',
    FRAME_STOP_SENDING: 'STOP_SENDING',
    FRAME_CRYPTO: 'CRYPTO',
    FRAME_NEW_TOKEN: 'NEW_TOKEN',
    FRAME_STREAM: 'STREAM',
    FRAME_MAX_DATA: 'MAX_DATA',
    FRAME_MAX_STREAM_DATA: 'MAX_STREAM_DATA',
    FRAME_MAX_STREAMS_BIDI: 'MAX_STREAMS_BIDI',
    FRAME_MAX_STREAMS_UNI: 'MAX_STREAMS_UNI',
    FRAME_DATA_BLOCKED: 'DATA_BLOCKED',
    FRAME_STREAM_DATA_BLOCKED: 'STREAM_DATA_BLOCKED',
    FRAME_STREAMS_BLOCKED_BIDI: 'STREAMS_BLOCKED_BIDI',
    FRAME_STREAMS_BLOCKED_UNI: 'STREAMS_BLOCKED_UNI',
    FRAME_NEW_CONNECTION_ID: 'NEW_CONNECTION_ID',
    FRAME_RETIRE_CONNECTION_ID: 'RETIRE_CONNECTION_ID',
    FRAME_PATH_CHALLENGE: 'PATH_CHALLENGE',
    FRAME_PATH_RESPONSE: 'PATH_RESPONSE',
    FRAME_CONNECTION_CLOSE: 'CONNECTION_CLOSE',
    FRAME_CONNECTION_CLOSE_APP: 'CONNECTION_CLOSE_APP',
    FRAME_HANDSHAKE_DONE: 'HANDSHAKE_DONE',
}

QUIC_PACKET_SPACE_PROHIBITIONS: tuple[dict[str, object], ...] = (
    {
        'packet_space': _PACKET_SPACE_INITIAL,
        'frame': 'CONNECTION_CLOSE_APP',
        'reason': 'application close is not permitted in Initial packets',
    },
    {
        'packet_space': _PACKET_SPACE_HANDSHAKE,
        'frame': 'CONNECTION_CLOSE_APP',
        'reason': 'application close is not permitted in Handshake packets',
    },
    {
        'packet_space': _PACKET_SPACE_ZERO_RTT,
        'frame': 'PATH_CHALLENGE|PATH_RESPONSE|NEW_CONNECTION_ID',
        'reason': 'path validation and connection id rotation are forbidden in 0-RTT packets',
    },
    {
        'packet_space': 'client-only',
        'frame': 'HANDSHAKE_DONE|NEW_TOKEN',
        'reason': 'clients must not send HANDSHAKE_DONE or NEW_TOKEN',
    },
)


_ALLOWED_FRAME_TYPES_BY_PACKET_SPACE: dict[str, frozenset[int]] = {
    _PACKET_SPACE_INITIAL: frozenset({
        FRAME_PADDING,
        FRAME_PING,
        FRAME_ACK,
        FRAME_CRYPTO,
        FRAME_CONNECTION_CLOSE,
    }),
    _PACKET_SPACE_HANDSHAKE: frozenset({
        FRAME_PADDING,
        FRAME_PING,
        FRAME_ACK,
        FRAME_CRYPTO,
        FRAME_CONNECTION_CLOSE,
    }),
    _PACKET_SPACE_ZERO_RTT: frozenset({
        FRAME_PADDING,
        FRAME_PING,
        FRAME_RESET_STREAM,
        FRAME_STOP_SENDING,
        FRAME_STREAM,
        FRAME_MAX_DATA,
        FRAME_MAX_STREAM_DATA,
        FRAME_MAX_STREAMS_BIDI,
        FRAME_MAX_STREAMS_UNI,
        FRAME_DATA_BLOCKED,
        FRAME_STREAM_DATA_BLOCKED,
        FRAME_STREAMS_BLOCKED_BIDI,
        FRAME_STREAMS_BLOCKED_UNI,
        FRAME_CONNECTION_CLOSE,
        FRAME_CONNECTION_CLOSE_APP,
    }),
    _PACKET_SPACE_APPLICATION: frozenset({
        FRAME_PADDING,
        FRAME_PING,
        FRAME_ACK,
        FRAME_RESET_STREAM,
        FRAME_STOP_SENDING,
        FRAME_CRYPTO,
        FRAME_NEW_TOKEN,
        FRAME_STREAM,
        FRAME_MAX_DATA,
        FRAME_MAX_STREAM_DATA,
        FRAME_MAX_STREAMS_BIDI,
        FRAME_MAX_STREAMS_UNI,
        FRAME_DATA_BLOCKED,
        FRAME_STREAM_DATA_BLOCKED,
        FRAME_STREAMS_BLOCKED_BIDI,
        FRAME_STREAMS_BLOCKED_UNI,
        FRAME_NEW_CONNECTION_ID,
        FRAME_RETIRE_CONNECTION_ID,
        FRAME_PATH_CHALLENGE,
        FRAME_PATH_RESPONSE,
        FRAME_CONNECTION_CLOSE,
        FRAME_CONNECTION_CLOSE_APP,
        FRAME_HANDSHAKE_DONE,
    }),
}


def frame_type_value(frame: QuicFrame) -> int:
    if isinstance(frame, int):
        return int(frame)
    if isinstance(frame, QuicStreamFrame):
        return FRAME_STREAM
    if isinstance(frame, QuicAckFrame):
        return FRAME_ACK
    if isinstance(frame, QuicResetStreamFrame):
        return FRAME_RESET_STREAM
    if isinstance(frame, QuicStopSendingFrame):
        return FRAME_STOP_SENDING
    if isinstance(frame, QuicCryptoFrame):
        return FRAME_CRYPTO
    if isinstance(frame, QuicNewTokenFrame):
        return FRAME_NEW_TOKEN
    if isinstance(frame, QuicMaxDataFrame):
        return FRAME_MAX_DATA
    if isinstance(frame, QuicMaxStreamDataFrame):
        return FRAME_MAX_STREAM_DATA
    if isinstance(frame, QuicMaxStreamsFrame):
        return FRAME_MAX_STREAMS_BIDI if frame.bidirectional else FRAME_MAX_STREAMS_UNI
    if isinstance(frame, QuicDataBlockedFrame):
        return FRAME_DATA_BLOCKED
    if isinstance(frame, QuicStreamDataBlockedFrame):
        return FRAME_STREAM_DATA_BLOCKED
    if isinstance(frame, QuicStreamsBlockedFrame):
        return FRAME_STREAMS_BLOCKED_BIDI if frame.bidirectional else FRAME_STREAMS_BLOCKED_UNI
    if isinstance(frame, QuicNewConnectionIdFrame):
        return FRAME_NEW_CONNECTION_ID
    if isinstance(frame, QuicRetireConnectionIdFrame):
        return FRAME_RETIRE_CONNECTION_ID
    if isinstance(frame, QuicPathChallengeFrame):
        return FRAME_PATH_CHALLENGE
    if isinstance(frame, QuicPathResponseFrame):
        return FRAME_PATH_RESPONSE
    if isinstance(frame, QuicHandshakeDoneFrame):
        return FRAME_HANDSHAKE_DONE
    if isinstance(frame, QuicConnectionCloseFrame):
        return FRAME_CONNECTION_CLOSE_APP if frame.application else FRAME_CONNECTION_CLOSE
    raise TypeError(f'unsupported QUIC frame: {type(frame)!r}')


def validate_frame_for_packet_space(frame: QuicFrame, packet_space: str, *, is_client: bool | None = None) -> None:
    normalized = _PACKET_SPACE_APPLICATION if packet_space == _PACKET_SPACE_ZERO_RTT else packet_space if packet_space in _ALLOWED_FRAME_TYPES_BY_PACKET_SPACE else packet_space
    if packet_space not in _ALLOWED_FRAME_TYPES_BY_PACKET_SPACE:
        raise ProtocolError(f'unknown QUIC packet space: {packet_space}')
    frame_type = frame_type_value(frame)
    if frame_type not in _ALLOWED_FRAME_TYPES_BY_PACKET_SPACE[packet_space]:
        raise ProtocolError(f'frame type 0x{frame_type:x} is not permitted in {packet_space} packets')
    if isinstance(frame, QuicHandshakeDoneFrame) and is_client is True:
        raise ProtocolError('clients must not send HANDSHAKE_DONE')
    if isinstance(frame, QuicNewTokenFrame) and is_client is True:
        raise ProtocolError('clients must not send NEW_TOKEN')
    if isinstance(frame, QuicConnectionCloseFrame) and frame.application and packet_space in {_PACKET_SPACE_INITIAL, _PACKET_SPACE_HANDSHAKE}:
        raise ProtocolError('application CONNECTION_CLOSE is not permitted in Initial or Handshake packets')
    if packet_space == _PACKET_SPACE_ZERO_RTT and isinstance(frame, (QuicPathChallengeFrame, QuicPathResponseFrame, QuicNewConnectionIdFrame)):
        raise ProtocolError(f'frame type 0x{frame_type:x} is not permitted in 0-RTT packets')


def validate_frames_for_packet_space(frames: Iterable[QuicFrame], packet_space: str, *, is_client: bool | None = None) -> None:
    for frame in frames:
        validate_frame_for_packet_space(frame, packet_space, is_client=is_client)


def quic_packet_space_legality_table() -> dict[str, tuple[str, ...]]:
    return {
        packet_space: tuple(QUIC_FRAME_TYPE_LABELS.get(frame_type, f'0x{frame_type:x}') for frame_type in sorted(frame_types))
        for packet_space, frame_types in _ALLOWED_FRAME_TYPES_BY_PACKET_SPACE.items()
    }



def quic_packet_space_prohibitions() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in QUIC_PACKET_SPACE_PROHIBITIONS)


def encode_frame(frame: QuicFrame) -> bytes:
    if frame == FRAME_PADDING:
        return b'\x00'
    if frame == FRAME_PING:
        return encode_quic_varint(FRAME_PING)
    if isinstance(frame, QuicStreamFrame):
        flags = 0x02 | (0x01 if frame.fin else 0)
        payload = bytearray()
        payload.extend(encode_quic_varint(FRAME_STREAM | flags | (0x04 if frame.offset else 0x00)))
        payload.extend(encode_quic_varint(frame.stream_id))
        if frame.offset:
            payload.extend(encode_quic_varint(frame.offset))
        payload.extend(encode_quic_varint(len(frame.data)))
        payload.extend(frame.data)
        return bytes(payload)
    if isinstance(frame, QuicAckFrame):
        payload = bytearray()
        payload.extend(encode_quic_varint(FRAME_ACK))
        payload.extend(encode_quic_varint(frame.largest_acked))
        payload.extend(encode_quic_varint(frame.ack_delay))
        payload.extend(encode_quic_varint(len(frame.ack_ranges)))
        payload.extend(encode_quic_varint(frame.first_ack_range))
        for gap, ack_range_length in frame.ack_ranges:
            payload.extend(encode_quic_varint(gap))
            payload.extend(encode_quic_varint(ack_range_length))
        return bytes(payload)
    if isinstance(frame, QuicResetStreamFrame):
        return (
            encode_quic_varint(FRAME_RESET_STREAM)
            + encode_quic_varint(frame.stream_id)
            + encode_quic_varint(frame.error_code)
            + encode_quic_varint(frame.final_size)
        )
    if isinstance(frame, QuicStopSendingFrame):
        return encode_quic_varint(FRAME_STOP_SENDING) + encode_quic_varint(frame.stream_id) + encode_quic_varint(frame.error_code)
    if isinstance(frame, QuicCryptoFrame):
        return encode_quic_varint(FRAME_CRYPTO) + encode_quic_varint(frame.offset) + pack_varbytes(frame.data)
    if isinstance(frame, QuicNewTokenFrame):
        return encode_quic_varint(FRAME_NEW_TOKEN) + pack_varbytes(frame.token)
    if isinstance(frame, QuicMaxDataFrame):
        return encode_quic_varint(FRAME_MAX_DATA) + encode_quic_varint(frame.maximum_data)
    if isinstance(frame, QuicMaxStreamDataFrame):
        return encode_quic_varint(FRAME_MAX_STREAM_DATA) + encode_quic_varint(frame.stream_id) + encode_quic_varint(frame.maximum_data)
    if isinstance(frame, QuicMaxStreamsFrame):
        frame_type = FRAME_MAX_STREAMS_BIDI if frame.bidirectional else FRAME_MAX_STREAMS_UNI
        return encode_quic_varint(frame_type) + encode_quic_varint(frame.maximum_streams)
    if isinstance(frame, QuicDataBlockedFrame):
        return encode_quic_varint(FRAME_DATA_BLOCKED) + encode_quic_varint(frame.limit)
    if isinstance(frame, QuicStreamDataBlockedFrame):
        return encode_quic_varint(FRAME_STREAM_DATA_BLOCKED) + encode_quic_varint(frame.stream_id) + encode_quic_varint(frame.limit)
    if isinstance(frame, QuicStreamsBlockedFrame):
        frame_type = FRAME_STREAMS_BLOCKED_BIDI if frame.bidirectional else FRAME_STREAMS_BLOCKED_UNI
        return encode_quic_varint(frame_type) + encode_quic_varint(frame.limit)
    if isinstance(frame, QuicNewConnectionIdFrame):
        return (
            encode_quic_varint(FRAME_NEW_CONNECTION_ID)
            + encode_quic_varint(frame.sequence)
            + encode_quic_varint(frame.retire_prior_to)
            + pack_varbytes(frame.connection_id)
            + frame.stateless_reset_token
        )
    if isinstance(frame, QuicRetireConnectionIdFrame):
        return encode_quic_varint(FRAME_RETIRE_CONNECTION_ID) + encode_quic_varint(frame.sequence)
    if isinstance(frame, QuicPathChallengeFrame):
        return encode_quic_varint(FRAME_PATH_CHALLENGE) + frame.data
    if isinstance(frame, QuicPathResponseFrame):
        return encode_quic_varint(FRAME_PATH_RESPONSE) + frame.data
    if isinstance(frame, QuicHandshakeDoneFrame):
        return encode_quic_varint(FRAME_HANDSHAKE_DONE)
    if isinstance(frame, QuicConnectionCloseFrame):
        reason = frame.reason.encode('utf-8')
        frame_type = FRAME_CONNECTION_CLOSE_APP if frame.application else FRAME_CONNECTION_CLOSE
        return (
            encode_quic_varint(frame_type)
            + encode_quic_varint(frame.error_code)
            + encode_quic_varint(frame.frame_type)
            + pack_varbytes(reason)
        )
    raise TypeError(f'unsupported QUIC frame: {type(frame)!r}')


def decode_frame(data: bytes, offset: int = 0) -> tuple[QuicFrame, int]:
    frame_type, offset = decode_quic_varint(data, offset)
    if frame_type == FRAME_PADDING:
        return FRAME_PADDING, offset
    if frame_type == FRAME_PING:
        return FRAME_PING, offset
    if frame_type & 0xF8 == FRAME_STREAM:
        fin = bool(frame_type & 0x01)
        has_length = bool(frame_type & 0x02)
        has_offset = bool(frame_type & 0x04)
        stream_id, offset = decode_quic_varint(data, offset)
        frame_offset = 0
        if has_offset:
            frame_offset, offset = decode_quic_varint(data, offset)
        if has_length:
            length, offset = decode_quic_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise ProtocolError('truncated STREAM frame payload')
            payload = data[offset:end]
            offset = end
        else:
            payload = data[offset:]
            offset = len(data)
        return QuicStreamFrame(stream_id=stream_id, offset=frame_offset, fin=fin, data=payload), offset
    if frame_type == FRAME_ACK:
        largest_acked, offset = decode_quic_varint(data, offset)
        ack_delay, offset = decode_quic_varint(data, offset)
        ack_range_count, offset = decode_quic_varint(data, offset)
        first_ack_range, offset = decode_quic_varint(data, offset)
        ack_ranges: list[tuple[int, int]] = []
        for _ in range(ack_range_count):
            gap, offset = decode_quic_varint(data, offset)
            ack_range_length, offset = decode_quic_varint(data, offset)
            ack_ranges.append((gap, ack_range_length))
        return QuicAckFrame(largest_acked=largest_acked, ack_delay=ack_delay, first_ack_range=first_ack_range, ack_ranges=ack_ranges), offset
    if frame_type == FRAME_RESET_STREAM:
        stream_id, offset = decode_quic_varint(data, offset)
        error_code, offset = decode_quic_varint(data, offset)
        final_size, offset = decode_quic_varint(data, offset)
        return QuicResetStreamFrame(stream_id=stream_id, error_code=error_code, final_size=final_size), offset
    if frame_type == FRAME_STOP_SENDING:
        stream_id, offset = decode_quic_varint(data, offset)
        error_code, offset = decode_quic_varint(data, offset)
        return QuicStopSendingFrame(stream_id=stream_id, error_code=error_code), offset
    if frame_type == FRAME_CRYPTO:
        crypto_offset, offset = decode_quic_varint(data, offset)
        payload, offset = unpack_varbytes(data, offset)
        return QuicCryptoFrame(offset=crypto_offset, data=payload), offset
    if frame_type == FRAME_NEW_TOKEN:
        token, offset = unpack_varbytes(data, offset)
        return QuicNewTokenFrame(token=token), offset
    if frame_type == FRAME_MAX_DATA:
        maximum_data, offset = decode_quic_varint(data, offset)
        return QuicMaxDataFrame(maximum_data=maximum_data), offset
    if frame_type == FRAME_MAX_STREAM_DATA:
        stream_id, offset = decode_quic_varint(data, offset)
        maximum_data, offset = decode_quic_varint(data, offset)
        return QuicMaxStreamDataFrame(stream_id=stream_id, maximum_data=maximum_data), offset
    if frame_type == FRAME_MAX_STREAMS_BIDI:
        maximum_streams, offset = decode_quic_varint(data, offset)
        return QuicMaxStreamsFrame(maximum_streams=maximum_streams, bidirectional=True), offset
    if frame_type == FRAME_MAX_STREAMS_UNI:
        maximum_streams, offset = decode_quic_varint(data, offset)
        return QuicMaxStreamsFrame(maximum_streams=maximum_streams, bidirectional=False), offset
    if frame_type == FRAME_DATA_BLOCKED:
        limit, offset = decode_quic_varint(data, offset)
        return QuicDataBlockedFrame(limit=limit), offset
    if frame_type == FRAME_STREAM_DATA_BLOCKED:
        stream_id, offset = decode_quic_varint(data, offset)
        limit, offset = decode_quic_varint(data, offset)
        return QuicStreamDataBlockedFrame(stream_id=stream_id, limit=limit), offset
    if frame_type == FRAME_STREAMS_BLOCKED_BIDI:
        limit, offset = decode_quic_varint(data, offset)
        return QuicStreamsBlockedFrame(limit=limit, bidirectional=True), offset
    if frame_type == FRAME_STREAMS_BLOCKED_UNI:
        limit, offset = decode_quic_varint(data, offset)
        return QuicStreamsBlockedFrame(limit=limit, bidirectional=False), offset
    if frame_type == FRAME_NEW_CONNECTION_ID:
        sequence, offset = decode_quic_varint(data, offset)
        retire_prior_to, offset = decode_quic_varint(data, offset)
        connection_id, offset = unpack_varbytes(data, offset)
        if offset + 16 > len(data):
            raise ProtocolError('truncated NEW_CONNECTION_ID frame')
        token = data[offset:offset + 16]
        offset += 16
        return QuicNewConnectionIdFrame(sequence=sequence, retire_prior_to=retire_prior_to, connection_id=connection_id, stateless_reset_token=token), offset
    if frame_type == FRAME_RETIRE_CONNECTION_ID:
        sequence, offset = decode_quic_varint(data, offset)
        return QuicRetireConnectionIdFrame(sequence=sequence), offset
    if frame_type == FRAME_PATH_CHALLENGE:
        if offset + 8 > len(data):
            raise ProtocolError('truncated PATH_CHALLENGE frame')
        payload = data[offset:offset + 8]
        offset += 8
        return QuicPathChallengeFrame(payload), offset
    if frame_type == FRAME_PATH_RESPONSE:
        if offset + 8 > len(data):
            raise ProtocolError('truncated PATH_RESPONSE frame')
        payload = data[offset:offset + 8]
        offset += 8
        return QuicPathResponseFrame(payload), offset
    if frame_type == FRAME_HANDSHAKE_DONE:
        return QuicHandshakeDoneFrame(), offset
    if frame_type in {FRAME_CONNECTION_CLOSE, FRAME_CONNECTION_CLOSE_APP}:
        error_code, offset = decode_quic_varint(data, offset)
        frame_type_value_field, offset = decode_quic_varint(data, offset)
        reason, offset = unpack_varbytes(data, offset)
        return (
            QuicConnectionCloseFrame(
                error_code=error_code,
                frame_type=frame_type_value_field,
                reason=reason.decode('utf-8', 'replace'),
                application=(frame_type == FRAME_CONNECTION_CLOSE_APP),
            ),
            offset,
        )
    raise ProtocolError(f'unsupported QUIC frame type: {frame_type}')
