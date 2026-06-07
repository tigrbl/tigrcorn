from __future__ import annotations

from typing import Iterable

from tigrcorn_core.errors import ProtocolError
from .constants import *
from .constants import (
    _PACKET_SPACE_APPLICATION,
    _PACKET_SPACE_HANDSHAKE,
    _PACKET_SPACE_INITIAL,
    _PACKET_SPACE_ZERO_RTT,
)
from .frames import *

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
    FRAME_DATAGRAM: 'DATAGRAM',
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
        FRAME_DATAGRAM,
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
        FRAME_DATAGRAM,
    }),
}

QUIC_PACKET_SPACE_ALLOWED_FRAMES = _ALLOWED_FRAME_TYPES_BY_PACKET_SPACE


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
    if isinstance(frame, QuicDatagramFrame):
        return FRAME_DATAGRAM
    if isinstance(frame, QuicConnectionCloseFrame):
        return FRAME_CONNECTION_CLOSE_APP if frame.application else FRAME_CONNECTION_CLOSE
    raise TypeError(f'unsupported QUIC frame: {type(frame)!r}')


def validate_frame_for_packet_space(
    frame: QuicFrame,
    packet_space: str,
    *,
    is_client: bool | None = None,
) -> None:
    normalized = (
        _PACKET_SPACE_APPLICATION
        if packet_space == _PACKET_SPACE_ZERO_RTT
        else packet_space
        if packet_space in _ALLOWED_FRAME_TYPES_BY_PACKET_SPACE
        else packet_space
    )
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


