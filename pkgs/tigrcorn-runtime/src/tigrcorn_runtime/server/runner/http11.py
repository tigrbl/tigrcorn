from __future__ import annotations

from .imports import *

class _TigrCornServerHTTP11Mixin:
    async def _read_preface_probe(self, reader: asyncio.StreamReader) -> bytes:
        data = await asyncio.wait_for(reader.read(len(H2_PREFACE)), timeout=self.config.http.read_timeout)
        if not data:
            return b''
        if H2_PREFACE.startswith(data) and data != H2_PREFACE:
            with suppress(Exception):
                data += await asyncio.wait_for(reader.readexactly(len(H2_PREFACE) - len(data)), timeout=0.05)
        return data

    async def _handle_http11_connection(
        self,
        reader: StreamReaderLike,
        writer: asyncio.StreamWriter,
        listener_cfg: ListenerConfig,
        *,
        client: tuple[str, int] | None,
        server: tuple[str, int] | tuple[str, None] | None,
        scheme: str,
        ws_scheme: str,
        scope_extensions: dict | None = None,
        connection_id: str | None = None,
    ) -> None:
        keep_handling = True
        handled_requests = 0
        while keep_handling and not self.state.shutting_down:
            request_timeout = self.config.http.keep_alive_timeout if handled_requests else self.config.http.read_timeout
            if self.config.http.http1_header_read_timeout is not None:
                request_timeout = min(request_timeout, self.config.http.http1_header_read_timeout)
            try:
                request = await asyncio.wait_for(
                    read_http11_request_head(
                        reader,
                        max_body_size=self.config.max_body_size,
                        max_header_size=self.config.max_header_size,
                        max_incomplete_event_size=self.config.http.http1_max_incomplete_event_size,
                        buffer_size=self.config.http.http1_buffer_size,
                    ),
                    timeout=request_timeout,
                )
            except asyncio.TimeoutError:
                break
            except Exception as exc:
                self.state.metrics.protocol_errors += 1
                self.logger.warning('protocol error from %s: %s', client, exc)
                await self._write_error(writer, 400, b'bad request', keep_alive=False)
                break
            if request is None:
                break

            proxy_view = resolve_proxy_view(
                request.headers,
                client=client,
                server=server,
                scheme=scheme,
                root_path=self.config.proxy.root_path,
                enabled=self.config.proxy.proxy_headers,
                forwarded_allow_ips=self.config.proxy.forwarded_allow_ips,
            )
            request_client = proxy_view.client
            request_server = proxy_view.server
            request_scheme = proxy_view.scheme
            request_ws_scheme = 'wss' if request_scheme == 'https' else 'ws'
            request.keep_alive = apply_keep_alive_policy(request.keep_alive, enabled=self.config.http.http1_keep_alive)

            if request.method.upper() == 'CONNECT':
                session_id = f"{connection_id}:connect:{handled_requests}" if connection_id else None
                if session_id is not None:
                    self._connection_inventory.open_session(
                        session_id,
                        connection_id=connection_id,
                        kind='connect-tunnel',
                        metadata={'authority': request.target, 'protocol': 'http1'},
                    )
                try:
                    await self._handle_http11_connect_tunnel(reader, writer, request, client=request_client)
                finally:
                    if session_id is not None:
                        self._connection_inventory.close_session(session_id, reason='connect-complete')
                keep_handling = False
                break

            if request.websocket_upgrade:
                if not listener_cfg.websocket:
                    await self._write_error(writer, 426, b'websocket not enabled', keep_alive=False)
                    break
                work_lease = self.scheduler.acquire_work()
                if work_lease is None:
                    self.state.metrics.scheduler_task_rejected()
                    await self._write_error(writer, 503, b'scheduler overloaded', keep_alive=False)
                    break
                handler = WebSocketConnectionHandler(
                    app=self.app,
                    config=self.config,
                    access_logger=self.access_logger,
                    request=request,
                    reader=reader,
                    writer=writer,
                    client=request_client,
                    server=request_server,
                    scheme=request_ws_scheme,
                    scope_extensions=scope_extensions,
                    metrics=self.state.metrics,
                )
                session_id = f"{connection_id}:websocket:{handled_requests}" if connection_id else None
                if session_id is not None:
                    self._connection_inventory.open_session(
                        session_id,
                        connection_id=connection_id,
                        kind='websocket',
                        metadata={'path': request.path, 'protocol': 'http1'},
                    )
                try:
                    self.state.metrics.websocket_opened()
                    await handler.handle()
                finally:
                    if session_id is not None:
                        self._connection_inventory.close_session(session_id, reason='websocket-complete')
                    work_lease.release()
                    self.state.metrics.websocket_closed()
                    keep_handling = False
                break

            work_lease = self.scheduler.acquire_work()
            if work_lease is None:
                self.state.metrics.scheduler_task_rejected()
                await self._write_error(writer, 503, b'scheduler overloaded', keep_alive=False)
                break
            try:
                session_id = f"{connection_id}:http1:{handled_requests}" if connection_id else None
                if session_id is not None:
                    self._connection_inventory.open_session(
                        session_id,
                        connection_id=connection_id,
                        kind='http-request',
                        metadata={'method': request.method, 'path': request.path, 'protocol': 'http1'},
                    )
                keep_handling = await self._serve_http11_request(
                reader,
                writer,
                request,
                client=request_client,
                server=request_server,
                scheme=request_scheme,
                scope_extensions=scope_extensions,
                connection_id=connection_id,
                session_id=session_id,
            )
            finally:
                if session_id is not None:
                    self._connection_inventory.close_session(session_id, reason='request-complete')
                work_lease.release()
            handled_requests += 1

    async def _drain_writer(self, writer: asyncio.StreamWriter) -> None:
        await asyncio.wait_for(writer.drain(), timeout=self.config.http.write_timeout)

    async def _write_continue(self, writer: asyncio.StreamWriter) -> None:
        writer.write(b'HTTP/1.1 100 Continue\r\n\r\n')
        await self._drain_writer(writer)

    def _build_http11_receive(
        self,
        reader: StreamReaderLike,
        writer: asyncio.StreamWriter,
        request: ParsedRequestHead,
    ) -> HTTPRequestReceive | HTTPStreamingRequestReceive:
        if request.body_kind == 'none':
            return HTTPRequestReceive(b'')
        return HTTPStreamingRequestReceive(
            reader=reader,
            content_length=request.content_length if request.body_kind == 'content-length' else None,
            chunked=request.body_kind == 'chunked',
            max_body_size=self.config.max_body_size,
            expect_continue=request.expect_continue,
            on_expect_continue=lambda: self._write_continue(writer),
            max_chunk_size=self.config.http.http1_buffer_size,
            trailer_policy=self.config.http.trailer_policy,
        )

    def _http11_scope_extensions(self, request: ParsedRequestHead, *, scope_extensions: dict | None = None) -> dict:
        extensions: dict = dict(scope_extensions or {})
        if request.body_kind == 'chunked' and self.config.http.trailer_policy != 'drop':
            extensions['tigrcorn.http.request_trailers'] = {}
        if request.method.upper() == 'CONNECT':
            extensions['tigrcorn.http.connect'] = {'authority': request.target}
        extensions['tigrcorn.http.response.file'] = {'protocol': 'http/1.1', 'streaming': True, 'sendfile': True}
        extensions['http.response.pathsend'] = {}
        return extensions

    @staticmethod
    @staticmethod
    def _parse_connect_authority(authority: str) -> tuple[str, int]:
        return parse_connect_authority(authority)

    async def _relay_stream(self, reader: StreamReaderLike, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=self.config.http.idle_timeout)
                if not chunk:
                    break
                writer.write(chunk)
                await self._drain_writer(writer)
                self.state.metrics.bytes_sent += len(chunk)
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

__all__ = [name for name in globals() if not name.startswith('__')]
