from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tigrcorn_core.errors import ProtocolError
from .frames import QuicResetStreamFrame, QuicStreamFrame

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

