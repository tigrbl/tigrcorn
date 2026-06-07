from __future__ import annotations

from .imports import *


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


class HTTP2ConnectMixin:
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

