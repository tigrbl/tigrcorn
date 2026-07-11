from __future__ import annotations

from tigrcorn_core.errors import ProtocolError
from .frames import QuicMaxStreamsFrame, QuicResetStreamAtFrame, QuicResetStreamFrame, QuicStreamFrame
from .state import QuicStreamState

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

    def apply_reset_at(self, frame: QuicResetStreamAtFrame) -> None:
        state = self.ensure_receive_stream(frame.stream_id)
        if state.highest_received_offset < frame.reliable_size:
            raise ProtocolError('RESET_STREAM_AT reliable data has not been received')
        state.apply_reset(QuicResetStreamFrame(frame.stream_id, frame.error_code, frame.final_size))

    def maybe_release_peer_stream_credit(self, stream_id: int) -> QuicMaxStreamsFrame | None:
        state = self._streams.get(stream_id)
        if state is None or not state.peer_initiated or not state.closed or state.credit_released:
            return None
        state.credit_released = True
        bidirectional = not state.unidirectional
        self._local_max_streams_current[bidirectional] += 1
        return QuicMaxStreamsFrame(maximum_streams=self._local_max_streams_current[bidirectional], bidirectional=bidirectional)
