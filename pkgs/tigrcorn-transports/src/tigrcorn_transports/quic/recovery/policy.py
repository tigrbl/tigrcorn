from __future__ import annotations

from enum import Enum

from tigrcorn_transports.quic.streams import (
    FRAME_ACK,
    FRAME_CONNECTION_CLOSE,
    FRAME_CONNECTION_CLOSE_APP,
    FRAME_CRYPTO,
    FRAME_DATA_BLOCKED,
    FRAME_DATAGRAM,
    FRAME_HANDSHAKE_DONE,
    FRAME_MAX_DATA,
    FRAME_MAX_STREAM_DATA,
    FRAME_MAX_STREAMS_BIDI,
    FRAME_MAX_STREAMS_UNI,
    FRAME_NEW_CONNECTION_ID,
    FRAME_NEW_TOKEN,
    FRAME_PADDING,
    FRAME_PATH_CHALLENGE,
    FRAME_PATH_RESPONSE,
    FRAME_PING,
    FRAME_RESET_STREAM,
    FRAME_RESET_STREAM_AT,
    FRAME_RETIRE_CONNECTION_ID,
    FRAME_STOP_SENDING,
    FRAME_STREAM,
    FRAME_STREAM_DATA_BLOCKED,
    FRAME_STREAMS_BLOCKED_BIDI,
    FRAME_STREAMS_BLOCKED_UNI,
    QuicFrame,
    frame_type_value,
)


class RecoveryDisposition(str, Enum):
    """Action taken when a packet carrying a frame is declared lost."""

    RETRANSMIT_DATA = "retransmit_data"
    REGENERATE_STATE = "regenerate_state"
    ABANDON = "abandon"


_RETRANSMIT_DATA = frozenset(
    {
        FRAME_PING,
        FRAME_RESET_STREAM,
        FRAME_RESET_STREAM_AT,
        FRAME_STOP_SENDING,
        FRAME_CRYPTO,
        FRAME_NEW_TOKEN,
        FRAME_STREAM,
        FRAME_NEW_CONNECTION_ID,
        FRAME_RETIRE_CONNECTION_ID,
        FRAME_PATH_CHALLENGE,
        FRAME_HANDSHAKE_DONE,
    }
)

_REGENERATE_STATE = frozenset(
    {
        FRAME_MAX_DATA,
        FRAME_MAX_STREAM_DATA,
        FRAME_MAX_STREAMS_BIDI,
        FRAME_MAX_STREAMS_UNI,
        FRAME_DATA_BLOCKED,
        FRAME_STREAM_DATA_BLOCKED,
        FRAME_STREAMS_BLOCKED_BIDI,
        FRAME_STREAMS_BLOCKED_UNI,
    }
)

_ABANDON = frozenset(
    {
        FRAME_PADDING,
        FRAME_ACK,
        FRAME_PATH_RESPONSE,
        FRAME_CONNECTION_CLOSE,
        FRAME_CONNECTION_CLOSE_APP,
        FRAME_DATAGRAM,
    }
)

SUPPORTED_RECOVERY_FRAME_TYPES = frozenset(
    _RETRANSMIT_DATA | _REGENERATE_STATE | _ABANDON
)


def recovery_disposition(frame: QuicFrame) -> RecoveryDisposition:
    """Return an exhaustive recovery policy for a supported QUIC frame."""

    frame_type = frame_type_value(frame)
    if frame_type in _RETRANSMIT_DATA:
        return RecoveryDisposition.RETRANSMIT_DATA
    if frame_type in _REGENERATE_STATE:
        return RecoveryDisposition.REGENERATE_STATE
    if frame_type in _ABANDON:
        return RecoveryDisposition.ABANDON
    raise ValueError(f"QUIC frame type 0x{frame_type:x} has no recovery policy")


def frame_is_ack_eliciting(frame: QuicFrame) -> bool:
    """RFC 9000/9221 ACK-eliciting classification, independent of recovery."""

    return frame_type_value(frame) not in {
        FRAME_PADDING,
        FRAME_ACK,
        FRAME_CONNECTION_CLOSE,
        FRAME_CONNECTION_CLOSE_APP,
    }


__all__ = [
    "RecoveryDisposition",
    "SUPPORTED_RECOVERY_FRAME_TYPES",
    "frame_is_ack_eliciting",
    "recovery_disposition",
]
