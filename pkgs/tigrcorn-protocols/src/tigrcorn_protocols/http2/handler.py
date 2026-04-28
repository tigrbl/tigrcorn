from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import urlsplit

from tigrcorn_asgi.receive import HTTPRequestReceive, apply_request_trailer_policy
from tigrcorn_asgi.scopes.http import build_http_scope
from tigrcorn_asgi.send import HTTPResponseCollector, iter_response_body_segments, response_body_segments_have_bytes
from tigrcorn_config.model import ServerConfig
from tigrcorn_protocols.flow.keepalive import KeepAlivePolicy, KeepAliveRuntime
from tigrcorn_core.constants import H2_PREFACE
from tigrcorn_core.errors import ProtocolError
from tigrcorn_observability.metrics import Metrics
from tigrcorn_observability.logging import AccessLogger
from tigrcorn_http.alt_svc import configured_alt_svc_values
from tigrcorn_http.entity import apply_response_entity_semantics, plan_file_backed_response_entity_semantics
from tigrcorn_protocols.http1.parser import ParsedRequest
from tigrcorn_protocols.http2.codec import (
    DEFAULT_SETTINGS,
    H2_CONNECT_ERROR,
    FLAG_ACK,
    FLAG_END_HEADERS,
    FLAG_END_STREAM,
    FRAME_CONTINUATION,
    FRAME_DATA,
    FRAME_GOAWAY,
    FRAME_HEADERS,
    FRAME_PING,
    FRAME_PRIORITY,
    FRAME_PUSH_PROMISE,
    FRAME_RST_STREAM,
    FRAME_SETTINGS,
    FRAME_WINDOW_UPDATE,
    FrameBuffer,
    FrameWriter,
    HTTP2Frame,
    decode_settings,
    headers_payload_fragment,
    parse_goaway,
    parse_priority,
    parse_push_promise,
    parse_window_update,
    serialize_goaway,
    serialize_ping,
    serialize_push_promise,
    serialize_rst_stream,
    serialize_settings,
    serialize_settings_ack,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_ENABLE_PUSH,
    SETTING_INITIAL_WINDOW_SIZE,
    SETTING_MAX_CONCURRENT_STREAMS,
    SETTING_MAX_FRAME_SIZE,
    SETTING_MAX_HEADER_LIST_SIZE,
    serialize_window_update,
    strip_padding,
)
from tigrcorn_protocols.http2.flow import FlowWaiter, next_adaptive_window_target
from tigrcorn_protocols.http2.hpack import HPACKDecoder, HPACKEncoder
from tigrcorn_protocols.http2.state import H2ConnectionState, H2StreamLifecycle, H2StreamState
from tigrcorn_protocols.scheduler.runtime import ProductionScheduler, WorkLease
from tigrcorn_protocols.http2.streams import H2StreamRegistry
from tigrcorn_protocols.connect import close_tcp_writer, half_close_tcp_writer, is_connect_allowed, parse_connect_authority
from tigrcorn_protocols.http2.websocket import H2WebSocketSession
from tigrcorn_core.types import ASGIApp
from tigrcorn_core.utils.authority import authority_allowed
from tigrcorn_core.utils.headers import apply_response_header_policy, sanitize_early_hints_headers, strip_connection_specific_headers


class _HTTP2ConnectTunnel:
    def __init__(
        self,
        *,
        handler: HTTP2ConnectionHandler,
        stream_id: int,
        authority: str,
        upstream_reader: asyncio.StreamReader,
        upstream_writer: asyncio.StreamWriter,
        work_lease: WorkLease | None = None,
    ) -> None:
        self.handler = handler
        self.stream_id = stream_id
        self.authority = authority
        self.upstream_reader = upstream_reader
        self.upstream_writer = upstream_writer
        self.work_lease = work_lease
        self.relay_task: asyncio.Task[None] | None = None
        self.client_input_closed = False
        self.server_output_closed = False
        self.closed = False

    async def start(self) -> None:
        try:
            await self.handler._send_stream_headers(self.stream_id, 200, [], end_stream=False)
        except Exception:
            await close_tcp_writer(self.upstream_writer)
            raise
        self.relay_task = asyncio.create_task(
            self._relay_upstream_to_client(),
            name=f'tigrcorn-h2-connect-{self.stream_id}',
        )

    async def feed_client_data(self, data: bytes, *, end_stream: bool) -> None:
        if self.closed:
            return
        try:
            if data:
                self.upstream_writer.write(data)
                await self.upstream_writer.drain()
            if end_stream and not self.client_input_closed:
                self.client_input_closed = True
                await half_close_tcp_writer(self.upstream_writer)
        except Exception:
            await self.handler._reset_connect_stream(self.stream_id)
            await self.abort()
            return
        await self._finish_if_complete()

    async def abort(self) -> None:
        if self.closed:
            return
        self.closed = True
        current = asyncio.current_task()
        if self.relay_task is not None and self.relay_task is not current:
            self.relay_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.relay_task
        state = self.handler.streams.find(self.stream_id)
        if state is not None and state.connect_tunnel is self:
            state.connect_tunnel = None
        if self.work_lease is not None:
            self.work_lease.release()
        await close_tcp_writer(self.upstream_writer)
        self.handler._finalize_stream_if_complete(self.stream_id)

    async def _relay_upstream_to_client(self) -> None:
        reset_stream = False
        try:
            while True:
                chunk = await asyncio.wait_for(self.upstream_reader.read(65536), timeout=self.handler.config.http.idle_timeout)
                if not chunk:
                    break
                await self.handler._send_stream_data(self.stream_id, chunk, end_stream=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            reset_stream = True
        else:
            try:
                await self.handler._send_stream_data(self.stream_id, b'', end_stream=True)
            except Exception:
                pass
        finally:
            self.server_output_closed = True
            if reset_stream:
                with suppress(Exception):
                    await self.handler._reset_connect_stream(self.stream_id)
            await self._finish_if_complete()

    async def _finish_if_complete(self) -> None:
        if self.client_input_closed and self.server_output_closed:
            await self.abort()


class HTTP2ConnectionHandler:
    def __init__(
        self,
        *,
        app: ASGIApp,
        config: ServerConfig,
        access_logger: AccessLogger,
        scheduler: ProductionScheduler | None = None,
        metrics: Metrics | None = None,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client: tuple[str, int] | None,
        server: tuple[str, int] | tuple[str, None] | None,
        scheme: str,
        prebuffer: bytes = b"",
        scope_extensions: dict | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.access_logger = access_logger
        self.scheduler = scheduler
        self.metrics = metrics
        self.reader = reader
        self.writer = writer
        self.client = client
        self.server = server
        self.scheme = scheme
        self.prebuffer = prebuffer
        self.scope_extensions = dict(scope_extensions or {})
        self.state = H2ConnectionState()
        self.state.local_settings[SETTING_MAX_CONCURRENT_STREAMS] = self.config.http.http2_max_concurrent_streams
        self.state.local_settings[SETTING_MAX_HEADER_LIST_SIZE] = self.config.http.http2_max_headers_size
        self.state.local_settings[SETTING_MAX_FRAME_SIZE] = self.config.http.http2_max_frame_size
        self.state.local_settings[SETTING_INITIAL_WINDOW_SIZE] = self.config.http.http2_initial_stream_window_size
        self.state.connection_receive_window_target = self.config.http.http2_initial_connection_window_size
        self._initial_connection_window_increment = max(
            0,
            self.state.connection_receive_window_target - DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE],
        )
        if self._initial_connection_window_increment:
            self.state.connection_receive_window.increase(self._initial_connection_window_increment)
        self.streams = H2StreamRegistry()
        self.stream_tasks: dict[int, asyncio.Task[None]] = {}
        self.stream_work_leases: dict[int, WorkLease] = {}
        self.frame_buffer = FrameBuffer()
        self.frame_writer = FrameWriter(self.state.max_frame_size)
        self.writer_lock = asyncio.Lock()
        self.waiters: dict[int, FlowWaiter] = {}
        self.hpack_decoder = HPACKDecoder(
            max_table_size=DEFAULT_SETTINGS[0x1],
            max_header_list_size=self.state.max_header_list_size,
            max_header_block_size=self.config.http.http2_max_headers_size,
        )
        self.hpack_encoder = HPACKEncoder(max_table_size=DEFAULT_SETTINGS[0x1])
        self.keepalive_policy = KeepAlivePolicy(
            idle_timeout=self.config.http.idle_timeout,
            ping_interval=self.config.http.http2_keep_alive_interval,
            ping_timeout=self.config.http.http2_keep_alive_timeout,
        )
        self.keepalive = KeepAliveRuntime(self.keepalive_policy) if self.keepalive_policy.enabled else None
        self.keepalive_task: asyncio.Task[None] | None = None
        self.running = True
        self._continuation_stream_id: int | None = None

    def _record_keepalive_activity(self) -> None:
        if self.keepalive is not None:
            self.keepalive.record_activity()

    async def _keepalive_loop(self) -> None:
        while self.running and not self.writer.is_closing():
            await asyncio.sleep(0.05)
            if self.keepalive is None or not self.running:
                return
            if not self.state.remote_settings_seen:
                continue
            if self.keepalive.ping_timed_out():
                self.running = False
                self.writer.close()
                with suppress(Exception):
                    await self.writer.wait_closed()
                return
            payload = self.keepalive.next_ping_payload()
            if payload is None:
                continue
            await self._write_raw(serialize_ping(payload, ack=False), record_activity=False)

    async def handle(self) -> None:
        await self._ensure_preface()
        try:
            await self._write_raw(serialize_settings(self.state.local_settings))
            if self._initial_connection_window_increment:
                await self._write_raw(serialize_window_update(0, self._initial_connection_window_increment))
            if self.keepalive is not None:
                self.keepalive_task = asyncio.create_task(self._keepalive_loop(), name='tigrcorn-h2-keepalive')
            while self.running:
                if self._should_finish_after_peer_goaway():
                    break
                frames = self.frame_buffer.pop_all()
                if frames:
                    for frame in frames:
                        await self._handle_frame(frame)
                    continue
                data = await asyncio.wait_for(self.reader.read(65535), timeout=self.config.http.read_timeout)
                if not data:
                    break
                self.frame_buffer.feed(data)
        finally:
            if self.keepalive_task is not None:
                self.keepalive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.keepalive_task
            await self._shutdown_streams()

    async def _ensure_preface(self) -> None:
        if self.prebuffer == H2_PREFACE:
            self.state.preface_seen = True
            return
        if self.prebuffer:
            raise ProtocolError("unexpected HTTP/2 prebuffer state")
        received = await self.reader.readexactly(len(H2_PREFACE))
        if received != H2_PREFACE:
            raise ProtocolError("invalid HTTP/2 client preface")
        self.state.preface_seen = True

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

    def _validate_new_remote_stream(self, stream_id: int) -> None:
        if stream_id % 2 == 0:
            raise ProtocolError("client-initiated HTTP/2 streams must use odd stream ids")
        if stream_id <= self.state.highest_remote_stream_id:
            raise ProtocolError("HTTP/2 stream ids must increase")
        if self.state.peer_goaway_received or self.state.local_goaway_sent:
            raise ProtocolError("HTTP/2 new stream received after GOAWAY")
        if self.streams.active_remote_stream_count() >= self.state.max_concurrent_streams:
            raise ProtocolError("HTTP/2 maximum concurrent streams exceeded")
        self.state.highest_remote_stream_id = stream_id
        self.state.last_stream_id = max(self.state.last_stream_id, stream_id)

    def _append_header_fragment(self, state: H2StreamState, fragment: bytes) -> None:
        next_size = state.header_block_bytes + len(fragment)
        if next_size > self.config.http.http2_max_headers_size:
            raise ProtocolError("request head exceeds configured http2_max_headers_size")
        state.header_block_bytes = next_size
        state.header_fragments.append(fragment)

    def _validate_header_list_size(self, headers: list[tuple[bytes, bytes]]) -> None:
        size = sum(len(name) + len(value) + 32 for name, value in headers)
        if size > self.state.max_header_list_size:
            raise ProtocolError("HTTP/2 header list exceeds configured maximum")

    def _validate_trailer_headers(self, headers: list[tuple[bytes, bytes]]) -> None:
        for name, value in headers:
            if any(65 <= byte <= 90 for byte in name):
                raise ProtocolError("uppercase header field name forbidden in HTTP/2")
            if name.startswith(b":"):
                raise ProtocolError("trailer pseudo-header forbidden in HTTP/2")
            if name in {b"connection", b"upgrade", b"proxy-connection", b"transfer-encoding"}:
                raise ProtocolError("connection-specific header forbidden in HTTP/2")
            if name == b"te" and value.lower() != b"trailers":
                raise ProtocolError("invalid TE header for HTTP/2")

    async def _handle_headers(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0:
            raise ProtocolError("HEADERS must use a stream id")
        if self._continuation_stream_id not in (None, frame.stream_id):
            raise ProtocolError("unexpected HEADERS while CONTINUATION is pending")
        state = self.streams.find(frame.stream_id)
        is_new_stream = state is None
        if is_new_stream:
            if self.streams.is_closed(frame.stream_id):
                raise ProtocolError("HEADERS on closed HTTP/2 stream")
            self._validate_new_remote_stream(frame.stream_id)
            state = self.streams.activate_remote(
                frame.stream_id,
                send_window=self.state.initial_window_size,
                receive_window=self.state.local_initial_window_size,
            )
            state.current_header_block_is_trailers = False
            state.open_remote(end_stream=bool(frame.flags & FLAG_END_STREAM))
        else:
            if state.closed:
                raise ProtocolError("HEADERS on closed HTTP/2 stream")
            if not state.headers_complete:
                raise ProtocolError("duplicate HTTP/2 initial HEADERS block")
            if state.awaiting_continuation:
                raise ProtocolError("unexpected HEADERS while CONTINUATION is pending")
            if state.lifecycle not in {H2StreamLifecycle.OPEN, H2StreamLifecycle.HALF_CLOSED_LOCAL}:
                raise ProtocolError("HEADERS not permitted in current HTTP/2 stream state")
            if state.end_stream_received or state.trailers_complete:
                raise ProtocolError("trailing HEADERS not permitted after end of stream")
            if not (frame.flags & FLAG_END_STREAM):
                raise ProtocolError("trailing HTTP/2 HEADERS must carry END_STREAM")
            state.current_header_block_is_trailers = True
            state.receive_end_stream()
        self._append_header_fragment(state, headers_payload_fragment(frame.payload, frame.flags))
        state.awaiting_continuation = not bool(frame.flags & FLAG_END_HEADERS)
        if state.awaiting_continuation:
            self._continuation_stream_id = frame.stream_id
            return
        self._continuation_stream_id = None
        self._finish_headers(state)
        await self._maybe_dispatch(frame.stream_id)

    async def _handle_continuation(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0:
            raise ProtocolError("CONTINUATION must use a stream id")
        if self._continuation_stream_id != frame.stream_id:
            raise ProtocolError("unexpected CONTINUATION stream")
        state = self.streams.find(frame.stream_id)
        if state is None:
            raise ProtocolError("CONTINUATION for unknown stream")
        self._append_header_fragment(state, frame.payload)
        state.awaiting_continuation = not bool(frame.flags & FLAG_END_HEADERS)
        if state.awaiting_continuation:
            return
        self._continuation_stream_id = None
        self._finish_headers(state)
        await self._maybe_dispatch(frame.stream_id)

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
            state.append_body(payload)
        await self._maybe_replenish_receive_credit(frame.stream_id, len(payload))
        if frame.flags & FLAG_END_STREAM:
            state.receive_end_stream()
            await self._maybe_dispatch(frame.stream_id)
            self._finalize_stream_if_complete(frame.stream_id)

    def _finish_headers(self, state: H2StreamState) -> None:
        block = b"".join(state.header_fragments)
        headers = self.hpack_decoder.decode_header_block(block)
        self._validate_header_list_size(headers)
        if state.current_header_block_is_trailers:
            self._validate_trailer_headers(headers)
            state.trailers = headers
            state.trailers_complete = True
        else:
            state.headers = headers
            state.headers_complete = True
        state.header_fragments.clear()
        state.header_block_bytes = 0
        state.awaiting_continuation = False
        state.current_header_block_is_trailers = False

    async def _maybe_dispatch(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.dispatched or not state.headers_complete:
            return
        is_ws = self._is_extended_connect_websocket(state.headers)
        is_connect = self._is_generic_connect_tunnel(state.headers)
        if not is_ws and not is_connect and not state.end_stream_received:
            return
        if not self._admit_stream_work(stream_id):
            request = self._build_request(state)
            await self._send_response(stream_id, 503, [(b"content-type", b"text/plain")], b"scheduler overloaded")
            self.access_logger.log_http(self.client, request.method, request.path, 503, "HTTP/2")
            self._release_stream_work_lease(stream_id)
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
            return
        state.dispatched = True
        if is_ws:
            await self._start_websocket_stream(stream_id)
            return
        if is_connect:
            await self._start_connect_tunnel(stream_id)
            return
        self.state.last_stream_id = max(self.state.last_stream_id, stream_id)
        task = asyncio.create_task(self._run_stream(stream_id), name=f"tigrcorn-h2-stream-{stream_id}")
        self.stream_tasks[stream_id] = task

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

    def _pseudo_headers(self, headers: list[tuple[bytes, bytes]]) -> dict[bytes, bytes]:
        return {k: v for k, v in headers if k.startswith(b":")}

    def _is_extended_connect_websocket(self, headers: list[tuple[bytes, bytes]]) -> bool:
        pseudo = self._pseudo_headers(headers)
        return pseudo.get(b":method") == b"CONNECT" and pseudo.get(b":protocol") == b"websocket"

    def _is_generic_connect_tunnel(self, headers: list[tuple[bytes, bytes]]) -> bool:
        pseudo = self._pseudo_headers(headers)
        return pseudo.get(b":method") == b"CONNECT" and pseudo.get(b":protocol") is None
    def _release_stream_work_lease(self, stream_id: int) -> None:
        lease = self.stream_work_leases.pop(stream_id, None)
        if lease is not None:
            lease.release()

    def _on_websocket_stream_closed(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is not None:
            state.websocket_session = None
        self._release_stream_work_lease(stream_id)
        self._finalize_stream_if_complete(stream_id)

    def _admit_stream_work(self, stream_id: int) -> bool:
        if self.scheduler is None:
            return True
        lease = self.scheduler.acquire_work()
        if lease is None:
            if self.metrics is not None:
                self.metrics.scheduler_task_rejected()
            return False
        self.stream_work_leases[stream_id] = lease
        return True


    def _next_local_push_stream_id(self) -> int:
        max_local_streams = self.state.remote_settings.get(0x3)
        if max_local_streams is not None and self.streams.active_local_stream_count() >= max_local_streams:
            raise ProtocolError("HTTP/2 peer refused additional server-initiated streams")
        stream_id = self.state.next_local_stream_id
        while self.streams.find(stream_id) is not None or self.streams.is_closed(stream_id):
            stream_id += 2
        if stream_id > 0x7FFFFFFF:
            raise ProtocolError("exhausted HTTP/2 server-initiated stream identifiers")
        self.state.next_local_stream_id = stream_id + 2
        return stream_id

    def _build_push_request(self, parent_stream_id: int, message: dict) -> ParsedRequest:
        state = self.streams.find(parent_stream_id)
        if state is None:
            raise ProtocolError("cannot create HTTP/2 server push from an unknown stream")
        if self._is_extended_connect_websocket(state.headers) or self._is_generic_connect_tunnel(state.headers):
            raise ProtocolError("HTTP/2 server push is not available on CONNECT streams")
        pseudo = self._pseudo_headers(state.headers)
        path = message.get("path")
        if not path:
            raise ProtocolError("http.response.push requires a path")
        if isinstance(path, bytes):
            target = path.decode("ascii", "strict")
        else:
            target = str(path)
        method = message.get("method", "GET")
        if isinstance(method, bytes):
            method_text = method.decode("ascii", "strict").upper()
        else:
            method_text = str(method).upper()
        authority = message.get("authority")
        if authority is None:
            authority_bytes = pseudo.get(b":authority", b"")
        elif isinstance(authority, bytes):
            authority_bytes = authority
        else:
            authority_bytes = str(authority).encode("ascii", "strict")
        scheme = message.get("scheme")
        if scheme is None:
            scheme_bytes = pseudo.get(b":scheme", self.scheme.encode("ascii"))
        elif isinstance(scheme, bytes):
            scheme_bytes = scheme
        else:
            scheme_bytes = str(scheme).encode("ascii", "strict")
        extra_headers = [
            (bytes(name).lower(), bytes(value))
            for name, value in message.get("headers", [])
            if not bytes(name).startswith(b":")
        ]
        split = urlsplit(target)
        path_text = split.path or "/"
        raw_path = path_text.encode("utf-8")
        query_string = split.query.encode("ascii")
        pseudo_headers = [
            (b":method", method_text.encode("ascii")),
            (b":path", target.encode("utf-8")),
            (b":scheme", scheme_bytes),
            (b":authority", authority_bytes),
        ]
        return ParsedRequest(
            method=method_text,
            target=target,
            path=path_text,
            raw_path=raw_path,
            query_string=query_string,
            http_version="2",
            headers=extra_headers,
            body=b"",
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=False,
        ), pseudo_headers + extra_headers

    async def _run_http_app(self, stream_id: int, request: ParsedRequest, *, allow_push: bool) -> tuple[int, list[tuple[bytes, bytes]], bytes, list[tuple[bytes, bytes]], list[tuple[int, list[tuple[bytes, bytes]]]], list | None, object | None]:
        extensions = dict(self.scope_extensions)
        state = self.streams.find(stream_id)
        raw_request_trailers = list(state.trailers) if state is not None else []
        try:
            request_trailers = apply_request_trailer_policy(raw_request_trailers, self.config.http.trailer_policy)
        except ProtocolError:
            return 400, [(b"content-type", b"text/plain")], b"bad request trailers", [], [], None, None
        if request.method.upper() == "CONNECT":
            extensions["tigrcorn.http.connect"] = {"authority": request.target}
        if request_trailers and self.config.http.trailer_policy != 'drop':
            extensions["tigrcorn.http.request_trailers"] = {}
        if allow_push and self.state.client_allows_push:
            extensions["http.response.push"] = {}
        extensions['tigrcorn.http.response.file'] = {'protocol': 'http/2', 'streaming': True, 'sendfile': False}
        extensions['http.response.pathsend'] = {}
        scope = build_http_scope(request, client=self.client, server=self.server, scheme=self.scheme, extensions=extensions, root_path=self.config.proxy.root_path, proxy=self.config.proxy)
        receive = HTTPRequestReceive(request.body, trailers=request_trailers, trailer_policy=self.config.http.trailer_policy)
        collector = HTTPResponseCollector()

        async def send(message: dict) -> None:
            if message.get("type") == "http.response.push":
                if not allow_push or not self.state.client_allows_push:
                    raise ProtocolError("HTTP/2 server push is not available on this stream")
                await self._send_push_promise(stream_id, message)
                return
            await collector(message)

        status = 500
        cleanup: object | None = None
        try:
            await self.app(scope, receive, send)
            collector.finalize()
            assert collector.status is not None
            status = collector.status
            headers = list(collector.headers)
            trailers = list(collector.trailers)
            informational = list(collector.informational_responses)
            body_segments = list(collector.body_segments) if collector.uses_streamed_body else None
            if body_segments is not None:
                cleanup = collector.cleanup if collector.has_spooled_body() else None
                return status, headers, b'', trailers, informational, body_segments, cleanup
            if collector.has_spooled_body():
                spooled_segments = collector.spooled_body_segments()
                spooled_path = ''
                if spooled_segments:
                    first_segment = spooled_segments[0]
                    spooled_path = getattr(first_segment, 'path', '')
                planned = plan_file_backed_response_entity_semantics(
                    method=request.method,
                    request_headers=request.headers,
                    response_headers=headers,
                    status=status,
                    body_path=spooled_path,
                    body_length=collector.body_length,
                    generated_etag=collector.generated_entity_tag(),
                    apply_content_coding=True,
                    trailers_present=bool(trailers) and request.method.upper() != 'HEAD',
                )
                cleanup = collector.cleanup
                if planned.requires_materialization:
                    body = await collector.materialize_body()
                    processed = apply_response_entity_semantics(
                        method=request.method,
                        request_headers=request.headers,
                        response_headers=headers,
                        body=body,
                        status=status,
                        content_coding_policy=self.config.http.content_coding_policy,
                        supported_codings=tuple(self.config.http.content_codings),
                        apply_content_coding=True,
                        generate_etag=True,
                    )
                    return processed.status, processed.headers, processed.body, ([] if processed.head_response else trailers), informational, None, cleanup
                if planned.use_body_segments:
                    return planned.status, planned.headers, b'', trailers, informational, list(planned.body_segments), cleanup
                return planned.status, planned.headers, planned.body, [], informational, None, cleanup
            body = await collector.materialize_body()
        except Exception:
            collector.cleanup()
            status, headers, body, trailers = 500, [(b"content-type", b"text/plain")], b"internal server error", []
            informational = []
            body_segments = None
            cleanup = None
        processed = apply_response_entity_semantics(
            method=request.method,
            request_headers=request.headers,
            response_headers=headers,
            body=body,
            status=status,
            content_coding_policy=self.config.http.content_coding_policy,
            supported_codings=tuple(self.config.http.content_codings),
            apply_content_coding=True,
            generate_etag=True,
        )
        return processed.status, processed.headers, processed.body, ([] if processed.head_response else trailers), informational, None, cleanup

    async def _send_push_promise(self, parent_stream_id: int, message: dict) -> None:
        if not self.state.client_allows_push:
            return
        promised_stream_id = self._next_local_push_stream_id()
        request, request_headers = self._build_push_request(parent_stream_id, message)
        header_block = self.hpack_encoder.encode_header_block(request_headers)
        await self._write_raw(self.frame_writer.push_promise(parent_stream_id, promised_stream_id, header_block))
        self.streams.reserve_local(
            promised_stream_id,
            send_window=self.state.initial_window_size,
            receive_window=self.state.local_initial_window_size,
        )
        self.state.last_stream_id = max(self.state.last_stream_id, promised_stream_id)
        status, headers, body, trailers, informational, body_segments, cleanup = await self._run_http_app(promised_stream_id, request, allow_push=False)
        for interim_status, interim_headers in informational:
            await self._send_stream_headers(promised_stream_id, interim_status, sanitize_early_hints_headers(interim_headers), end_stream=False)
        try:
            await self._send_response(promised_stream_id, status, headers, body, trailers, body_segments=body_segments)
        finally:
            if cleanup is not None:
                cleanup()
        if self.streams.find(promised_stream_id) is not None:
            self._cancel_stream(promised_stream_id)
            self.streams.close(promised_stream_id)

    def _finalize_stream_if_complete(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.websocket_session is not None or state.connect_tunnel is not None:
            return
        if state.local_closed and state.end_stream_received:
            self._release_stream_work_lease(stream_id)
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()

    async def _reset_connect_stream(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.closed:
            return
        if not state.reset_sent:
            with suppress(Exception):
                await self._write_raw(serialize_rst_stream(stream_id, H2_CONNECT_ERROR))
            state.mark_reset_sent()
        self._cancel_stream(stream_id)
        self.streams.close(stream_id)
        self._maybe_finish_after_goaway()

    async def _send_stream_data(self, stream_id: int, data: bytes, *, end_stream: bool = False) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.closed:
            raise ProtocolError("attempted to send DATA on a closed HTTP/2 stream")
        if not data and not end_stream:
            return
        if not data:
            await self._write_raw(self.frame_writer.data(stream_id, b"", end_stream=True))
            state.send_end_stream()
            return
        offset = 0
        while offset < len(data):
            chunk_size = min(self.state.max_frame_size, len(data) - offset)
            while self.state.connection_send_window.available <= 0 or state.send_window.available <= 0:
                await self._wait_for_credit(stream_id)
            allowed = min(chunk_size, self.state.connection_send_window.available, state.send_window.available)
            if allowed <= 0:
                await self._wait_for_credit(stream_id)
                continue
            chunk = data[offset : offset + allowed]
            offset += len(chunk)
            self.state.connection_send_window.consume(len(chunk))
            state.send_window.consume(len(chunk))
            final_chunk = end_stream and offset == len(data)
            await self._write_raw(self.frame_writer.data(stream_id, chunk, end_stream=final_chunk))
            if final_chunk:
                state.send_end_stream()

    async def _send_stream_headers(
        self,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        end_stream: bool,
    ) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.closed:
            raise ProtocolError("attempted to send HEADERS on a closed HTTP/2 stream")
        normalized_headers = sanitize_early_hints_headers(headers) if status == 103 else strip_connection_specific_headers(headers)
        policy_headers = apply_response_header_policy(
            normalized_headers,
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
            alt_svc_values=() if status < 200 else configured_alt_svc_values(self.config, request_http_version='2'),
        )
        header_block = self.hpack_encoder.encode_header_block([(b":status", str(status).encode("ascii")), *policy_headers])
        await self._write_raw(self.frame_writer.headers(stream_id, header_block, end_stream=end_stream))
        if end_stream:
            state.send_end_stream()

    async def _start_connect_tunnel(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None:
            raise ProtocolError("connect stream disappeared before dispatch")
        request = self._build_request(state)
        try:
            host, port = parse_connect_authority(request.target)
        except Exception:
            await self._send_response(stream_id, 400, [(b"content-type", b"text/plain")], b"bad connect target")
            self.access_logger.log_http(self.client, "CONNECT", request.target, 400, "HTTP/2")
            self._release_stream_work_lease(stream_id)
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
            return
        if self.config.http.connect_policy == 'deny':
            await self._send_response(stream_id, 403, [(b"content-type", b"text/plain")], b"connect denied")
            self.access_logger.log_http(self.client, "CONNECT", request.target, 403, "HTTP/2")
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
            return
        if self.config.http.connect_policy == 'allowlist' and not is_connect_allowed(host, port, self.config.http.connect_allow):
            await self._send_response(stream_id, 403, [(b"content-type", b"text/plain")], b"connect denied")
            self.access_logger.log_http(self.client, "CONNECT", request.target, 403, "HTTP/2")
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
            return
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=getattr(self.config, "read_timeout", 5.0),
            )
        except Exception:
            await self._send_response(stream_id, 502, [(b"content-type", b"text/plain")], b"bad gateway")
            self.access_logger.log_http(self.client, "CONNECT", request.target, 502, "HTTP/2")
            self._release_stream_work_lease(stream_id)
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
            return
        tunnel = _HTTP2ConnectTunnel(
            handler=self,
            stream_id=stream_id,
            authority=request.target,
            upstream_reader=upstream_reader,
            upstream_writer=upstream_writer,
            work_lease=self.stream_work_leases.get(stream_id),
        )
        state.connect_tunnel = tunnel
        self.state.last_stream_id = max(self.state.last_stream_id, stream_id)
        try:
            await tunnel.start()
        except Exception:
            state.connect_tunnel = None
            await close_tcp_writer(upstream_writer)
            raise
        if state.end_stream_received:
            await tunnel.feed_client_data(b'', end_stream=True)
        self.access_logger.log_http(self.client, "CONNECT", request.target, 200, "HTTP/2")

    async def _send_h2_websocket_headers(
        self,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        end_stream: bool,
    ) -> None:
        await self._send_stream_headers(stream_id, status, headers, end_stream)

    async def _start_websocket_stream(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None:
            raise ProtocolError("websocket stream disappeared before dispatch")
        request = self._build_request(state)
        authority = self._pseudo_headers(state.headers).get(b":authority")
        if self.config.allowed_server_names and not authority_allowed(authority, self.config.allowed_server_names):
            await self._send_response(stream_id, 421, [(b"content-type", b"text/plain")], b"misdirected request")
            self.access_logger.log_http(self.client, "CONNECT", request.path, 421, "HTTP/2")
            self._release_stream_work_lease(stream_id)
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
            return
        session = H2WebSocketSession(
            app=self.app,
            config=self.config,
            request=request,
            client=self.client,
            server=self.server,
            scheme=self.scheme,
            send_headers=lambda status, headers, end_stream: self._send_stream_headers(stream_id, status, headers, end_stream),
            send_data=lambda data, end_stream: self._send_stream_data(stream_id, data, end_stream=end_stream),
            metrics=self.metrics,
            on_close=lambda stream_id=stream_id: self._on_websocket_stream_closed(stream_id),
        )
        state.websocket_session = session
        self.state.last_stream_id = max(self.state.last_stream_id, stream_id)
        await session.start()

    def _validate_request_headers(self, headers: list[tuple[bytes, bytes]]) -> None:
        pseudo_seen: set[bytes] = set()
        regular_seen = False
        allowed_pseudo = {b":method", b":scheme", b":authority", b":path", b":protocol"}
        for name, value in headers:
            if any(65 <= byte <= 90 for byte in name):
                raise ProtocolError("uppercase header field name forbidden in HTTP/2")
            if name.startswith(b":"):
                if regular_seen:
                    raise ProtocolError("pseudo-header after regular header")
                if name not in allowed_pseudo:
                    raise ProtocolError("invalid request pseudo-header")
                if name in pseudo_seen:
                    raise ProtocolError("duplicate pseudo-header")
                pseudo_seen.add(name)
            else:
                regular_seen = True
                if name in {b"connection", b"upgrade", b"proxy-connection", b"transfer-encoding"}:
                    raise ProtocolError("connection-specific header forbidden in HTTP/2")
                if name == b"te" and value.lower() != b"trailers":
                    raise ProtocolError("invalid TE header for HTTP/2")
        if b":method" not in pseudo_seen:
            raise ProtocolError("missing :method pseudo-header")
        method = dict(headers).get(b":method", b"GET")
        protocol = dict(headers).get(b":protocol")
        if protocol is not None:
            if method != b"CONNECT":
                raise ProtocolError("extended CONNECT requires CONNECT method")
            if self.state.local_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL, 0) != 1:
                raise ProtocolError("extended CONNECT not enabled")
            if b":scheme" not in pseudo_seen or b":path" not in pseudo_seen or b":authority" not in pseudo_seen:
                raise ProtocolError("extended CONNECT missing required pseudo-headers")
            return
        if method == b"CONNECT":
            if b":authority" not in pseudo_seen:
                raise ProtocolError("CONNECT missing :authority pseudo-header")
            if b":scheme" in pseudo_seen or b":path" in pseudo_seen:
                raise ProtocolError("CONNECT must not include :scheme or :path pseudo-headers")
            return
        if b":scheme" not in pseudo_seen or b":path" not in pseudo_seen:
            raise ProtocolError("missing required request pseudo-header")

    def _build_request(self, state: H2StreamState) -> ParsedRequest:
        self._validate_request_headers(state.headers)
        pseudo = {k: v for k, v in state.headers if k.startswith(b":")}
        headers = [(k, v) for k, v in state.headers if not k.startswith(b":")]
        method = pseudo.get(b":method", b"GET").decode("ascii", "strict")
        if method.upper() == "CONNECT" and pseudo.get(b":protocol") != b"websocket":
            target = pseudo.get(b":authority", b"").decode("ascii", "strict")
            path = target
            raw_path = target.encode("ascii", "strict")
            query_string = b""
        else:
            target = pseudo.get(b":path", b"/").decode("ascii", "strict")
            split = urlsplit(target)
            path = split.path or "/"
            raw_path = path.encode("utf-8")
            query_string = split.query.encode("ascii")
        return ParsedRequest(
            method=method,
            target=target,
            path=path,
            raw_path=raw_path,
            query_string=query_string,
            http_version="2",
            headers=headers,
            body=state.body,
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=False,
        )

    async def _run_stream(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None:
            self._release_stream_work_lease(stream_id)
            return
        request = self._build_request(state)
        authority = self._pseudo_headers(state.headers).get(b":authority")
        try:
            if self.config.allowed_server_names and not authority_allowed(authority, self.config.allowed_server_names):
                await self._send_response(stream_id, 421, [(b"content-type", b"text/plain")], b"misdirected request")
                self.access_logger.log_http(self.client, request.method, request.path, 421, "HTTP/2")
                if self.streams.find(stream_id) is not None:
                    self._cancel_stream(stream_id)
                    self.streams.close(stream_id)
                self._maybe_finish_after_goaway()
                return
            status, headers, body, trailers, informational, body_segments, cleanup = await self._run_http_app(stream_id, request, allow_push=True)
            for interim_status, interim_headers in informational:
                await self._send_stream_headers(stream_id, interim_status, sanitize_early_hints_headers(interim_headers), end_stream=False)
            try:
                await self._send_response(stream_id, status, headers, body, trailers, body_segments=body_segments)
            finally:
                if cleanup is not None:
                    cleanup()
            self.access_logger.log_http(self.client, request.method, request.path, status, "HTTP/2")
            if self.streams.find(stream_id) is not None:
                self._cancel_stream(stream_id)
                self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
        finally:
            self._release_stream_work_lease(stream_id)

    async def _send_response(self, stream_id: int, status: int, headers: list[tuple[bytes, bytes]], body: bytes, trailers: list[tuple[bytes, bytes]] | None = None, *, body_segments: list | None = None) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.closed:
            raise ProtocolError("attempted to send response on a closed HTTP/2 stream")
        streamed_body = response_body_segments_have_bytes(body_segments or []) if body_segments is not None else False
        if state.reserved_local and not state.opened:
            state.open_local_reserved(end_stream=not body and not streamed_body and not bool(trailers))
        headers = apply_response_header_policy(
            strip_connection_specific_headers(headers),
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
            alt_svc_values=configured_alt_svc_values(self.config, request_http_version='2'),
        )
        header_block = self.hpack_encoder.encode_header_block([(b":status", str(status).encode("ascii")), *headers])
        trailers = list(trailers or [])
        end_after_headers = not body and not streamed_body and not trailers
        await self._write_raw(self.frame_writer.headers(stream_id, header_block, end_stream=end_after_headers))
        if body_segments is not None:
            if not streamed_body and not trailers:
                state.send_end_stream()
                self._finalize_stream_if_complete(stream_id)
                return
            if streamed_body:
                async for chunk in iter_response_body_segments(body_segments, chunk_size=self.state.max_frame_size):
                    await self._send_stream_data(stream_id, chunk, end_stream=False)
            if trailers:
                trailer_block = self.hpack_encoder.encode_header_block(trailers)
                await self._write_raw(self.frame_writer.headers(stream_id, trailer_block, end_stream=True))
                state.send_end_stream()
                self._finalize_stream_if_complete(stream_id)
                return
            await self._send_stream_data(stream_id, b'', end_stream=True)
            self._finalize_stream_if_complete(stream_id)
            return
        if not body and not trailers:
            state.send_end_stream()
            self._finalize_stream_if_complete(stream_id)
            return
        if not body and trailers:
            trailer_block = self.hpack_encoder.encode_header_block(trailers)
            await self._write_raw(self.frame_writer.headers(stream_id, trailer_block, end_stream=True))
            state.send_end_stream()
            self._finalize_stream_if_complete(stream_id)
            return
        offset = 0
        while offset < len(body):
            chunk_size = min(self.state.max_frame_size, len(body) - offset)
            while self.state.connection_send_window.available <= 0 or state.send_window.available <= 0:
                await self._wait_for_credit(stream_id)
            allowed = min(chunk_size, self.state.connection_send_window.available, state.send_window.available)
            if allowed <= 0:
                await self._wait_for_credit(stream_id)
                continue
            chunk = body[offset : offset + allowed]
            offset += len(chunk)
            self.state.connection_send_window.consume(len(chunk))
            state.send_window.consume(len(chunk))
            final_chunk = offset == len(body)
            end_stream = final_chunk and not trailers
            await self._write_raw(self.frame_writer.data(stream_id, chunk, end_stream=end_stream))
            if final_chunk and trailers:
                trailer_block = self.hpack_encoder.encode_header_block(trailers)
                await self._write_raw(self.frame_writer.headers(stream_id, trailer_block, end_stream=True))
                state.send_end_stream()
                self._finalize_stream_if_complete(stream_id)
            elif final_chunk:
                state.send_end_stream()
                self._finalize_stream_if_complete(stream_id)

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

    async def _write_raw(self, data: bytes, *, record_activity: bool = True) -> None:
        async with self.writer_lock:
            self.writer.write(data)
            await self.writer.drain()
        if record_activity:
            self._record_keepalive_activity()

    def _notify_waiter(self, stream_id: int) -> None:
        if stream_id == 0:
            for waiter in self.waiters.values():
                waiter.notify()
            return
        waiter = self.waiters.get(stream_id)
        if waiter is not None:
            waiter.notify()

    def _cancel_stream(self, stream_id: int) -> None:
        self._release_stream_work_lease(stream_id)
        task = self.stream_tasks.pop(stream_id, None)
        if task is not None:
            task.cancel()
        self.waiters.pop(stream_id, None)

    async def _shutdown_streams(self) -> None:
        for state in list(self.streams.streams.values()):
            if state.websocket_session is not None:
                with suppress(Exception):
                    await state.websocket_session.abort()
            if state.connect_tunnel is not None:
                with suppress(Exception):
                    await state.connect_tunnel.abort()
        for stream_id, task in list(self.stream_tasks.items()):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            self.stream_tasks.pop(stream_id, None)
        if not self.state.local_goaway_sent:
            self.state.local_goaway_sent = True
            self.state.local_goaway_last_stream_id = self.state.last_stream_id
            with suppress(Exception):
                await self._write_raw(serialize_goaway(self.state.last_stream_id))
