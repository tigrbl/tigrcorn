from __future__ import annotations

from dataclasses import dataclass, field

from tigrcorn_core.errors import ProtocolError

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
class QuicDatagramFrame:
    data: bytes


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
    | QuicDatagramFrame
    | QuicConnectionCloseFrame
    | int
)


