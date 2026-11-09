from __future__ import annotations

from .imports import *


class HTTP2FlowControlMixin:
    async def _consume_receive_flow(self, stream_id: int, amount: int) -> None:
        if amount <= 0:
            return
        self.state.connection_receive_window.consume(amount)
        if self.state.connection_receive_window.available < 0:
            raise ProtocolError("HTTP/2 connection flow-control window exceeded")
        state = self.streams.find(stream_id)
        if state is None:
            raise ProtocolError("HTTP/2 stream flow-control used after closure")
        state.receive_window.consume(amount)
        if state.receive_window.available < 0:
            raise ProtocolError("HTTP/2 stream flow-control window exceeded")


    async def _maybe_replenish_receive_credit(self, stream_id: int, amount: int) -> None:
        if amount <= 0:
            return
        updates: list[bytes] = []
        self.state.connection_receive_consumed_since_update += amount
        connection_increment = 0
        if self.config.http.http2_adaptive_window:
            new_connection_target = next_adaptive_window_target(
                self.state.connection_receive_window_target,
                max(amount, self.state.connection_receive_consumed_since_update),
            )
            if new_connection_target > self.state.connection_receive_window_target:
                delta_target = new_connection_target - self.state.connection_receive_window_target
                self.state.connection_receive_window_target = new_connection_target
                self.state.connection_receive_window.increase(delta_target)
                connection_increment += delta_target
        connection_threshold = max(1, self.state.connection_receive_window_target // 2)
        if (
            self.state.connection_receive_window.available <= connection_threshold
            or self.state.connection_receive_consumed_since_update >= connection_threshold
        ):
            increment = self.state.connection_receive_consumed_since_update
            self.state.connection_receive_consumed_since_update = 0
            self.state.connection_receive_window.increase(increment)
            connection_increment += increment
        if connection_increment > 0:
            updates.append(serialize_window_update(0, connection_increment))
        state = self.streams.find(stream_id)
        if state is None:
            for update in updates:
                await self._write_raw(update)
            return
        state.receive_consumed_since_update += amount
        stream_increment = 0
        if self.config.http.http2_adaptive_window:
            new_stream_target = next_adaptive_window_target(
                state.receive_window_target,
                max(amount, state.receive_consumed_since_update),
            )
            if new_stream_target > state.receive_window_target:
                delta_target = new_stream_target - state.receive_window_target
                state.receive_window_target = new_stream_target
                state.receive_window.increase(delta_target)
                stream_increment += delta_target
        stream_threshold = max(1, state.receive_window_target // 2)
        if state.receive_window.available <= stream_threshold or state.receive_consumed_since_update >= stream_threshold:
            increment = state.receive_consumed_since_update
            state.receive_consumed_since_update = 0
            state.receive_window.increase(increment)
            stream_increment += increment
        if stream_increment > 0:
            updates.append(serialize_window_update(stream_id, stream_increment))
        for update in updates:
            await self._write_raw(update)


    async def _handle_data(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0:
            raise ProtocolError("DATA must use a stream id")
        if self.streams.is_closed(frame.stream_id):
            return
        state = self.streams.find(frame.stream_id)
        if state is None:
            raise ProtocolError("DATA on idle HTTP/2 stream")
        if state.awaiting_continuation:
            raise ProtocolError("DATA received before END_HEADERS")
        if not state.headers_complete:
            raise ProtocolError("DATA before HEADERS")
        if state.trailers_complete or state.end_stream_received or state.closed:
            raise ProtocolError("DATA on half-closed HTTP/2 stream")
        payload = strip_padding(frame.payload, frame.flags)
        await self._consume_receive_flow(frame.stream_id, len(payload))
        if state.websocket_session is not None:
            await state.websocket_session.feed_data(payload, end_stream=bool(frame.flags & FLAG_END_STREAM))
        elif state.connect_tunnel is not None:
            await state.connect_tunnel.feed_client_data(payload, end_stream=bool(frame.flags & FLAG_END_STREAM))
        elif payload:
            if state.buffered_body_size + len(payload) > self.config.max_body_size:
                raise ProtocolError("request body exceeds configured max_body_size")
            if state.request_receive is not None:
                await state.request_receive.put_body(payload, more_body=not bool(frame.flags & FLAG_END_STREAM))
            else:
                state.append_body(payload)
            if (
                state.expected_content_length is not None
                and state.buffered_body_size > state.expected_content_length
            ):
                raise ProtocolError("request body exceeds content-length")
        if frame.flags & FLAG_END_STREAM:
            state.receive_end_stream()
            if state.request_receive is not None and not payload:
                await state.request_receive.finish_body()
            await self._maybe_dispatch(frame.stream_id)
            self._finalize_stream_if_complete(frame.stream_id)


    async def _handle_window_update(self, frame: HTTP2Frame) -> None:
        increment = parse_window_update(frame.payload)
        if frame.stream_id == 0:
            self.state.connection_send_window.increase(increment)
            self._notify_waiter(0)
            return
        if self.streams.is_closed(frame.stream_id):
            return
        state = self.streams.find(frame.stream_id)
        if state is None:
            raise ProtocolError("WINDOW_UPDATE on idle HTTP/2 stream")
        state.send_window.increase(increment)
        self._notify_waiter(frame.stream_id)


    async def _wait_for_credit(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.closed:
            raise ProtocolError("attempted to wait for flow-control credit on a closed stream")
        waiter = self.waiters.setdefault(stream_id, FlowWaiter(state.send_window))
        waiter.notify()
        while self.state.connection_send_window.available <= 0 or state.send_window.available <= 0:
            await waiter.wait()
            state = self.streams.find(stream_id)
            if state is None or state.closed:
                raise ProtocolError("stream closed while waiting for flow-control credit")


    def _notify_waiter(self, stream_id: int) -> None:
        if stream_id == 0:
            for waiter in self.waiters.values():
                waiter.notify()
            return
        waiter = self.waiters.get(stream_id)
        if waiter is not None:
            waiter.notify()

