from __future__ import annotations

from dataclasses import dataclass, field

from tigrcorn_core.errors import ProtocolError
from tigrcorn_protocols.http2.state import FlowWindow, H2StreamState


@dataclass(slots=True)
class H2StreamRegistry:
    streams: dict[int, H2StreamState] = field(default_factory=dict)
    closed_stream_ids: set[int] = field(default_factory=set)

    def get(self, stream_id: int) -> H2StreamState:
        return self.streams.setdefault(stream_id, H2StreamState(stream_id=stream_id))

    def find(self, stream_id: int) -> H2StreamState | None:
        return self.streams.get(stream_id)

    def activate_remote(self, stream_id: int, *, send_window: int, receive_window: int) -> H2StreamState:
        if stream_id in self.closed_stream_ids:
            raise ProtocolError("HTTP/2 closed stream cannot be reopened")
        state = self.streams.get(stream_id)
        if state is None:
            state = H2StreamState(
                stream_id=stream_id,
                send_window=FlowWindow(send_window),
                receive_window=FlowWindow(receive_window),
                receive_window_target=receive_window,
            )
            self.streams[stream_id] = state
        else:
            state.send_window = FlowWindow(send_window)
            state.receive_window = FlowWindow(receive_window)
            state.receive_window_target = receive_window
        return state

    def reserve_local(self, stream_id: int, *, send_window: int, receive_window: int) -> H2StreamState:
        if stream_id in self.closed_stream_ids:
            raise ProtocolError("HTTP/2 closed stream cannot be reopened")
        if stream_id in self.streams:
            raise ProtocolError("HTTP/2 local stream is already active")
        state = H2StreamState(
            stream_id=stream_id,
            send_window=FlowWindow(send_window),
            receive_window=FlowWindow(receive_window),
            receive_window_target=receive_window,
        )
        state.reserve_local()
        self.streams[stream_id] = state
        return state

    def close(self, stream_id: int) -> None:
        state = self.streams.get(stream_id)
        if state is not None:
            state.local_closed = True
            state.end_stream_received = True
            state._sync_lifecycle()
            self.streams.pop(stream_id, None)
        self.closed_stream_ids.add(stream_id)

    def apply_window_delta(self, delta: int) -> None:
        for state in self.streams.values():
            state.send_window.adjust(delta)

    def active_ids(self) -> list[int]:
        return sorted(self.streams)

    def active_remote_stream_count(self) -> int:
        return sum(1 for stream_id, state in self.streams.items() if stream_id % 2 == 1 and not state.closed)

    def active_local_stream_count(self) -> int:
        return sum(1 for stream_id, state in self.streams.items() if stream_id % 2 == 0 and not state.closed)

    def is_closed(self, stream_id: int) -> bool:
        return stream_id in self.closed_stream_ids
