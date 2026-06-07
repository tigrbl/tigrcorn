from __future__ import annotations

from .imports import *


class HTTP2FrameDispatchMixin:
    def _check_frame_header(self, frame: HTTP2Frame) -> None:
        if frame.length > self.state.local_settings[0x5]:
            raise ProtocolError("received HTTP/2 frame exceeds local MAX_FRAME_SIZE")
        if not self.state.remote_settings_seen and frame.frame_type != FRAME_SETTINGS:
            raise ProtocolError("HTTP/2 first frame after preface must be SETTINGS")
        if self._continuation_stream_id is not None and (
            frame.frame_type != FRAME_CONTINUATION or frame.stream_id != self._continuation_stream_id
        ):
            raise ProtocolError("unexpected frame while CONTINUATION is pending")


    async def _handle_frame(self, frame: HTTP2Frame) -> None:
        self._check_frame_header(frame)
        self._record_keepalive_activity()
        if frame.frame_type == FRAME_SETTINGS:
            await self._handle_settings(frame)
            return
        if frame.frame_type == FRAME_HEADERS:
            await self._handle_headers(frame)
            return
        if frame.frame_type == FRAME_CONTINUATION:
            await self._handle_continuation(frame)
            return
        if frame.frame_type == FRAME_DATA:
            await self._handle_data(frame)
            return
        if frame.frame_type == FRAME_WINDOW_UPDATE:
            await self._handle_window_update(frame)
            return
        if frame.frame_type == FRAME_PING:
            await self._handle_ping(frame)
            return
        if frame.frame_type == FRAME_PRIORITY:
            self._handle_priority(frame)
            return
        if frame.frame_type == FRAME_PUSH_PROMISE:
            self._handle_push_promise(frame)
            return
        if frame.frame_type == FRAME_RST_STREAM:
            await self._handle_rst_stream(frame)
            return
        if frame.frame_type == FRAME_GOAWAY:
            self._handle_goaway(frame)
            return
        # Unknown extension frames are ignored unless a CONTINUATION sequence is pending.


    async def _handle_settings(self, frame: HTTP2Frame) -> None:
        if frame.stream_id != 0:
            raise ProtocolError("SETTINGS must use stream 0")
        if frame.flags & FLAG_ACK:
            if not self.state.remote_settings_seen:
                raise ProtocolError("HTTP/2 peer must send initial SETTINGS before ACK")
            if frame.payload:
                raise ProtocolError("ACK SETTINGS must have empty payload")
            return
        self.state.remote_settings_seen = True
        settings = decode_settings(frame.payload)
        if 0x1 in settings:
            self.hpack_encoder.set_max_table_size(settings[0x1])
        old_initial_window = self.state.remote_settings.get(0x4, DEFAULT_SETTINGS[0x4])
        self.state.remote_settings.update(settings)
        new_initial_window = self.state.remote_settings.get(0x4, DEFAULT_SETTINGS[0x4])
        delta = new_initial_window - old_initial_window
        if delta:
            self.streams.apply_window_delta(delta)
            if delta > 0:
                self._notify_waiter(0)
        self.frame_writer.max_frame_size = self.state.max_frame_size
        await self._write_raw(serialize_settings_ack())


    async def _handle_ping(self, frame: HTTP2Frame) -> None:
        if frame.stream_id != 0:
            raise ProtocolError("PING must use stream 0")
        if len(frame.payload) != 8:
            raise ProtocolError("PING payload must be 8 bytes")
        if frame.flags & FLAG_ACK:
            if self.keepalive is not None:
                self.keepalive.acknowledge_pong(frame.payload)
            return
        await self._write_raw(serialize_ping(frame.payload, ack=True))


    def _handle_priority(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0:
            raise ProtocolError("PRIORITY must use a stream id")
        _exclusive, dependency, _weight = parse_priority(frame.payload)
        if dependency == frame.stream_id:
            raise ProtocolError("HTTP/2 PRIORITY stream dependency cannot depend on itself")


    def _handle_push_promise(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0:
            raise ProtocolError("PUSH_PROMISE must use a stream id")
        raise ProtocolError("clients must not send PUSH_PROMISE to an HTTP/2 server")


    async def _handle_rst_stream(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0 or len(frame.payload) != 4:
            raise ProtocolError("invalid RST_STREAM frame")
        if self.streams.is_closed(frame.stream_id):
            return
        state = self.streams.find(frame.stream_id)
        if state is None or (not state.opened and not state.reserved_local and not state.reserved_remote):
            raise ProtocolError("RST_STREAM on idle HTTP/2 stream")
        if state.websocket_session is not None:
            await state.websocket_session.abort()
        if state.connect_tunnel is not None:
            await state.connect_tunnel.abort()
        self._cancel_stream(frame.stream_id)
        state.mark_reset_received()
        self.streams.close(frame.stream_id)
        self._notify_waiter(frame.stream_id)
        self._maybe_finish_after_goaway()


    def _handle_goaway(self, frame: HTTP2Frame) -> None:
        if frame.stream_id != 0:
            raise ProtocolError("GOAWAY must use stream 0")
        last_stream_id, _error_code, _debug_data = parse_goaway(frame.payload)
        if self.state.peer_goaway_received and self.state.peer_last_stream_id is not None:
            if last_stream_id > self.state.peer_last_stream_id:
                raise ProtocolError("HTTP/2 GOAWAY last_stream_id must not increase")
        self.state.peer_goaway_received = True
        self.state.peer_last_stream_id = last_stream_id
        self.state.shutdown = True
        self._maybe_finish_after_goaway()


    def _should_finish_after_peer_goaway(self) -> bool:
        return (
            self.state.peer_goaway_received
            and self._continuation_stream_id is None
            and not self.streams.streams
            and not self.stream_tasks
        )


    def _maybe_finish_after_goaway(self) -> None:
        if self._should_finish_after_peer_goaway():
            self.running = False

