from __future__ import annotations

from dataclasses import dataclass, field

from tigrcorn_core.errors import ProtocolError
from tigrcorn_transports.quic.streams import stream_is_local_initiated, stream_is_unidirectional

FLOW_CONTROL_CERTIFICATION_SCOPES: tuple[str, ...] = (
    'credit-exhaustion',
    'replenishment',
    'stream-level-backpressure',
    'connection-level-backpressure',
)


def supported_flow_control_certification_scopes() -> tuple[str, ...]:
    return FLOW_CONTROL_CERTIFICATION_SCOPES



@dataclass(slots=True)
class QuicFlowControl:
    connection_window: int = 1_048_576
    local_connection_window: int = 1_048_576
    local_is_client: bool = True
    stream_windows: dict[int, int] = field(default_factory=dict)
    stream_receive_windows: dict[int, int] = field(default_factory=dict)
    connection_bytes_sent: int = 0
    connection_bytes_received: int = 0
    stream_bytes_sent: dict[int, int] = field(default_factory=dict)
    stream_bytes_received: dict[int, int] = field(default_factory=dict)
    peer_bidi_local_window: int = 65_535
    peer_bidi_remote_window: int = 65_535
    peer_uni_window: int = 65_535
    local_bidi_local_window: int = 65_535
    local_bidi_remote_window: int = 65_535
    local_uni_window: int = 65_535

    def _default_send_limit(self, stream_id: int) -> int:
        if stream_is_unidirectional(stream_id):
            return self.peer_uni_window
        if stream_is_local_initiated(stream_id, local_is_client=self.local_is_client):
            return self.peer_bidi_remote_window
        return self.peer_bidi_local_window

    def _default_receive_limit(self, stream_id: int) -> int:
        if stream_is_unidirectional(stream_id):
            return self.local_uni_window
        if stream_is_local_initiated(stream_id, local_is_client=self.local_is_client):
            return self.local_bidi_local_window
        return self.local_bidi_remote_window

    def ensure_stream(self, stream_id: int) -> None:
        self.stream_windows.setdefault(stream_id, self._default_send_limit(stream_id))
        self.stream_receive_windows.setdefault(stream_id, self._default_receive_limit(stream_id))
        self.stream_bytes_sent.setdefault(stream_id, 0)
        self.stream_bytes_received.setdefault(stream_id, 0)

    def configure_peer_initial_limits(
        self,
        *,
        max_data: int,
        max_stream_data_bidi_local: int,
        max_stream_data_bidi_remote: int,
        max_stream_data_uni: int,
    ) -> None:
        self.connection_window = max_data
        self.peer_bidi_local_window = max_stream_data_bidi_local
        self.peer_bidi_remote_window = max_stream_data_bidi_remote
        self.peer_uni_window = max_stream_data_uni
        for stream_id in list(self.stream_windows):
            self.stream_windows[stream_id] = max(self.stream_bytes_sent.get(stream_id, 0), self._default_send_limit(stream_id))

    def configure_local_initial_limits(
        self,
        *,
        max_data: int,
        max_stream_data_bidi_local: int,
        max_stream_data_bidi_remote: int,
        max_stream_data_uni: int,
    ) -> None:
        self.local_connection_window = max_data
        self.local_bidi_local_window = max_stream_data_bidi_local
        self.local_bidi_remote_window = max_stream_data_bidi_remote
        self.local_uni_window = max_stream_data_uni
        for stream_id in list(self.stream_receive_windows):
            self.stream_receive_windows[stream_id] = max(self.stream_bytes_received.get(stream_id, 0), self._default_receive_limit(stream_id))

    def window_for_stream(self, stream_id: int, default: int | None = None) -> int:
        self.ensure_stream(stream_id)
        if default is not None and default > self.stream_windows[stream_id]:
            self.stream_windows[stream_id] = default
        return self.stream_windows[stream_id]

    def receive_window_for_stream(self, stream_id: int) -> int:
        self.ensure_stream(stream_id)
        return self.stream_receive_windows[stream_id]

    def can_send(self, stream_id: int, amount: int) -> bool:
        self.ensure_stream(stream_id)
        if amount < 0:
            return False
        return (
            self.connection_bytes_sent + amount <= self.connection_window
            and self.stream_bytes_sent[stream_id] + amount <= self.stream_windows[stream_id]
        )

    def consume_send(self, stream_id: int, amount: int) -> None:
        if amount < 0:
            raise ValueError('amount must be non-negative')
        self.ensure_stream(stream_id)
        if not self.can_send(stream_id, amount):
            raise ProtocolError('insufficient QUIC flow-control credit')
        self.connection_bytes_sent += amount
        self.stream_bytes_sent[stream_id] += amount

    def credit_connection(self, amount: int) -> None:
        if amount < 0:
            raise ValueError('amount must be non-negative')
        self.connection_window += amount

    def credit_stream(self, stream_id: int, amount: int) -> None:
        if amount < 0:
            raise ValueError('amount must be non-negative')
        self.ensure_stream(stream_id)
        self.stream_windows[stream_id] += amount

    def expand_local_connection_limit(self, amount: int) -> None:
        if amount < 0:
            raise ValueError('amount must be non-negative')
        self.local_connection_window += amount

    def expand_local_stream_limit(self, stream_id: int, amount: int) -> None:
        if amount < 0:
            raise ValueError('amount must be non-negative')
        self.ensure_stream(stream_id)
        self.stream_receive_windows[stream_id] += amount

    def update_send_limit_connection(self, maximum_data: int) -> None:
        if maximum_data > self.connection_window:
            self.connection_window = maximum_data

    def update_send_limit_stream(self, stream_id: int, maximum_data: int) -> None:
        self.ensure_stream(stream_id)
        if maximum_data > self.stream_windows[stream_id]:
            self.stream_windows[stream_id] = maximum_data

    def validate_receive(self, stream_id: int, *, end_offset: int = 0, final_size: int | None = None) -> None:
        if end_offset < 0:
            raise ProtocolError('negative QUIC stream offset')
        if final_size is not None and final_size < 0:
            raise ProtocolError('negative QUIC final size')
        self.ensure_stream(stream_id)
        proposed = max(self.stream_bytes_received[stream_id], end_offset, final_size or 0)
        if proposed > self.stream_receive_windows[stream_id]:
            raise ProtocolError('stream flow control limit exceeded')
        additional = proposed - self.stream_bytes_received[stream_id]
        if self.connection_bytes_received + additional > self.local_connection_window:
            raise ProtocolError('connection flow control limit exceeded')

    def commit_receive(self, stream_id: int, *, end_offset: int = 0, final_size: int | None = None) -> int:
        self.ensure_stream(stream_id)
        proposed = max(self.stream_bytes_received[stream_id], end_offset, final_size or 0)
        additional = proposed - self.stream_bytes_received[stream_id]
        if additional > 0:
            self.stream_bytes_received[stream_id] = proposed
            self.connection_bytes_received += additional
        return additional
