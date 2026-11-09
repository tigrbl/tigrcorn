from __future__ import annotations

import pytest

from tigrcorn.transports.quic.connection import QuicConnection
from tigrcorn.transports.quic.recovery import (
    RecoveryDisposition,
    SUPPORTED_RECOVERY_FRAME_TYPES,
    frame_is_ack_eliciting,
    recovery_disposition,
)
from tigrcorn.transports.quic.streams import (
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
    QuicDatagramFrame,
    QuicStreamFrame,
)


ALL_SUPPORTED_FRAME_TYPES = {
    FRAME_PADDING,
    FRAME_PING,
    FRAME_ACK,
    FRAME_RESET_STREAM,
    FRAME_STOP_SENDING,
    FRAME_RESET_STREAM_AT,
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
}


def test_recovery_policy_is_exhaustive_for_supported_frames() -> None:
    assert SUPPORTED_RECOVERY_FRAME_TYPES == ALL_SUPPORTED_FRAME_TYPES
    assert all(recovery_disposition(frame) for frame in ALL_SUPPORTED_FRAME_TYPES)


def test_unknown_frame_fails_closed() -> None:
    with pytest.raises(ValueError, match="no recovery policy"):
        recovery_disposition(0xDEAD)


def test_datagram_is_ack_eliciting_but_abandoned() -> None:
    frame = QuicDatagramFrame(b"telemetry")
    assert frame_is_ack_eliciting(frame)
    assert recovery_disposition(frame) is RecoveryDisposition.ABANDON


def test_runtime_recovery_keeps_stream_and_discards_datagram() -> None:
    connection = QuicConnection(
        is_client=True,
        secret=b"shared",
        local_cid=b"cli1cli1",
        remote_cid=b"srv1srv1",
    )
    recovered = connection._recovery_frames(
        [QuicDatagramFrame(b"lost"), QuicStreamFrame(0, data=b"reliable")],
        record_abandonment=True,
    )
    assert recovered == [QuicStreamFrame(0, data=b"reliable")]
    assert connection.datagram_frames_abandoned_total == 1
    assert connection.stream_bytes_retransmitted_total == len(b"reliable")
