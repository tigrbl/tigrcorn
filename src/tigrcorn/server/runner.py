from __future__ import annotations

import asyncio
from contextlib import suppress


from tigrcorn.asgi.receive import HTTPRequestReceive, HTTPStreamingRequestReceive
from tigrcorn.asgi.scopes.http import build_http_scope
from tigrcorn.asgi.send import HTTPResponseWriter
from tigrcorn.compat.asgi3 import assert_asgi3_app
from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.constants import H2_PREFACE
from tigrcorn.listeners.inproc import InProcListener
from tigrcorn.listeners.pipe import PipeListener
from tigrcorn.listeners.tcp import TCPListener
from tigrcorn.listeners.udp import UDPListener
from tigrcorn.listeners.unix import UnixListener
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http1.parser import ParsedRequestHead, read_http11_request_head
from tigrcorn.protocols.http1.serializer import serialize_http11_response_whole
from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.protocols.lifespan.driver import LifespanManager
from tigrcorn.protocols.rawframed.handler import RawFramedApplicationHandler
from tigrcorn.protocols.websocket.handler import WebSocketConnectionHandler
from tigrcorn.scheduler import ProductionScheduler, SchedulerPolicy
from tigrcorn.security.tls import build_server_ssl_context, tls_extension_payload
from tigrcorn.server.state import ServerState
from tigrcorn.transports.tcp.reader import PrebufferedReader
from tigrcorn.types import ASGIApp, StreamReaderLike
from tigrcorn.utils.net import peer_parts


class TigrCornServer:
    def __init__(self, app: ASGIApp, config: ServerConfig) -> None:
        assert_asgi3_app(app)
        self.app = app
        self.config = config
        self.logger = configure_logging(config.log_level)
        self.access_logger = AccessLogger(self.logger, enabled=config.access_log)
        self.state = ServerState()
        self.lifespan = LifespanManager(app, mode=config.lifespan)
        self._listeners: list[TCPListener | UDPListener | UnixListener | PipeListener | InProcListener] = []
        self._should_exit = asyncio.Event()
        self._started = False
        self.scheduler = ProductionScheduler(SchedulerPolicy())

    async def start(self) -> None:
        if self._started:
            return
        await self.lifespan.startup()
        for listener_cfg in self.config.listeners:
            listener = await self._make_listener(listener_cfg)
            await listener.start(self._make_client_handler(listener_cfg))
            self._listeners.append(listener)
            self.logger.info('listening on %s', listener_cfg.label)
        self._started = True

    async def serve_forever(self) -> None:
        await self.start()
        try:
            await self._should_exit.wait()
        finally:
            await self.close()

    def request_shutdown(self) -> None:
        self._should_exit.set()

    async def close(self) -> None:
        if self.state.shutting_down:
            return
        self.state.shutting_down = True
        for listener in self._listeners:
            with suppress(Exception):
                await listener.close()
        self._listeners.clear()
        with suppress(Exception):
            await self.scheduler.close()
        with suppress(Exception):
            await self.lifespan.shutdown()

    async def _make_listener(self, cfg: ListenerConfig):
        if cfg.kind == 'tcp':
            ssl_ctx = build_server_ssl_context(cfg)
            return TCPListener(cfg.host, cfg.port, cfg.backlog, ssl=ssl_ctx, reuse_port=cfg.reuse_port)
        if cfg.kind == 'udp':
            return UDPListener(cfg.host, cfg.port, reuse_port=cfg.reuse_port)
        if cfg.kind == 'unix':
            ssl_ctx = build_server_ssl_context(cfg)
            return UnixListener(cfg.path or '', cfg.backlog, ssl=ssl_ctx)
        if cfg.kind == 'pipe':
            return PipeListener(cfg.path or '')
        return InProcListener()

    def _make_client_handler(self, listener_cfg: ListenerConfig):
        if listener_cfg.kind == 'udp':
            h3_handler = HTTP3DatagramHandler(
                app=self.app,
                config=self.config,
                listener=listener_cfg,
                access_logger=self.access_logger,
            )

            async def udp_handler(packet, endpoint) -> None:
                sessions_before = len(h3_handler.sessions)
                responses_before = sum(len(session.responded_streams) for session in h3_handler.sessions.values())
                await h3_handler.handle_packet(packet, endpoint)
                if len(h3_handler.sessions) > sessions_before:
                    self.state.metrics.connections_opened += 1
                responses_after = sum(len(session.responded_streams) for session in h3_handler.sessions.values())
                if responses_after > responses_before:
                    self.state.metrics.requests_served += responses_after - responses_before

            return udp_handler

        if listener_cfg.kind == 'pipe':
            raw_handler = RawFramedApplicationHandler(
                app=self.app,
                config=self.config,
                listener=listener_cfg,
                access_logger=self.access_logger,
            )

            async def pipe_handler(connection, data) -> None:
                handled = await raw_handler.feed_bytes(connection, data, path=listener_cfg.path)
                self.state.metrics.requests_served += handled

            return pipe_handler

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await self._handle_client(reader, writer, listener_cfg)

        return handler

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        listener_cfg: ListenerConfig,
    ) -> None:
        lease = self.scheduler.acquire_connection()
        if lease is None:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
            return
        self.state.metrics.connections_opened += 1
        peername = writer.get_extra_info('peername')
        sockname = writer.get_extra_info('sockname')
        ssl_obj = writer.get_extra_info('ssl_object')
        selected_alpn = ssl_obj.selected_alpn_protocol() if ssl_obj else None
        tls_payload = tls_extension_payload(writer)
        scope_tls_extensions = {'tls': tls_payload} if tls_payload is not None else None
        client_host, client_port = peer_parts(peername)
        server_host, server_port = peer_parts(sockname)
        client = (client_host, client_port) if client_host is not None and client_port is not None else None
        server = (server_host or '', server_port)
        scheme = 'https' if ssl_obj else (listener_cfg.scheme or 'http')
        ws_scheme = 'wss' if ssl_obj else 'ws'
        try:
            if selected_alpn == 'h2' and '2' in listener_cfg.http_versions:
                h2_handler = HTTP2ConnectionHandler(
                    app=self.app,
                    config=self.config,
                    access_logger=self.access_logger,
                    reader=reader,
                    writer=writer,
                    client=client,
                    server=server,
                    scheme=scheme,
                    scope_extensions=scope_tls_extensions,
                )
                await h2_handler.handle()
                return

            initial = b''
            if '2' in listener_cfg.http_versions and self.config.enable_h2c:
                initial = await self._read_preface_probe(reader)
                if initial == H2_PREFACE:
                    h2_handler = HTTP2ConnectionHandler(
                        app=self.app,
                        config=self.config,
                        access_logger=self.access_logger,
                        reader=reader,
                        writer=writer,
                        client=client,
                        server=server,
                        scheme=scheme,
                        prebuffer=initial,
                        scope_extensions=scope_tls_extensions,
                    )
                    await h2_handler.handle()
                    return

            buffered_reader: StreamReaderLike = PrebufferedReader(reader, initial)
            await self._handle_http11_connection(
                buffered_reader,
                writer,
                listener_cfg,
                client=client,
                server=server,
                scheme=scheme,
                ws_scheme=ws_scheme,
                scope_extensions=scope_tls_extensions,
            )
        finally:
            lease.release()
            self.state.metrics.connections_closed += 1
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def _read_preface_probe(self, reader: asyncio.StreamReader) -> bytes:
        data = await reader.read(len(H2_PREFACE))
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
    ) -> None:
        keep_handling = True
        while keep_handling and not self.state.shutting_down:
            try:
                request = await asyncio.wait_for(
                    read_http11_request_head(
                        reader,
                        max_body_size=self.config.max_body_size,
                        max_header_size=self.config.max_header_size,
                    ),
                    timeout=self.config.read_timeout,
                )
            except asyncio.TimeoutError:
                break
            except Exception as exc:
                self.logger.warning('protocol error from %s: %s', client, exc)
                await self._write_error(writer, 400, b'bad request', keep_alive=False)
                break
            if request is None:
                break

            if request.method.upper() == 'CONNECT':
                await self._handle_http11_connect_tunnel(reader, writer, request, client=client)
                keep_handling = False
                break

            if request.websocket_upgrade:
                if not listener_cfg.websocket:
                    await self._write_error(writer, 426, b'websocket not enabled', keep_alive=False)
                    break
                handler = WebSocketConnectionHandler(
                    app=self.app,
                    config=self.config,
                    access_logger=self.access_logger,
                    request=request,
                    reader=reader,
                    writer=writer,
                    client=client,
                    server=server,
                    scheme=ws_scheme,
                    scope_extensions=scope_extensions,
                )
                try:
                    await handler.handle()
                    self.state.metrics.websocket_connections += 1
                finally:
                    keep_handling = False
                break

            keep_handling = await self._serve_http11_request(
                reader,
                writer,
                request,
                client=client,
                server=server,
                scheme=scheme,
                scope_extensions=scope_extensions,
            )

    async def _write_continue(self, writer: asyncio.StreamWriter) -> None:
        writer.write(b'HTTP/1.1 100 Continue\r\n\r\n')
        await writer.drain()

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
        )

    def _http11_scope_extensions(self, request: ParsedRequestHead, *, scope_extensions: dict | None = None) -> dict:
        extensions: dict = dict(scope_extensions or {})
        if request.body_kind == 'chunked':
            extensions['tigrcorn.http.request_trailers'] = {}
        if request.method.upper() == 'CONNECT':
            extensions['tigrcorn.http.connect'] = {'authority': request.target}
        return extensions

    @staticmethod
    def _parse_connect_authority(authority: str) -> tuple[str, int]:
        if authority.startswith('['):
            end = authority.find(']')
            if end == -1 or end + 2 > len(authority) or authority[end + 1] != ':':
                raise ValueError('invalid CONNECT authority-form target')
            host = authority[1:end]
            port_text = authority[end + 2:]
        else:
            if authority.count(':') != 1:
                raise ValueError('invalid CONNECT authority-form target')
            host, port_text = authority.rsplit(':', 1)
        port = int(port_text)
        if not host or port <= 0 or port > 65535:
            raise ValueError('invalid CONNECT authority-form target')
        return host, port

    async def _relay_stream(self, reader: StreamReaderLike, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def _handle_http11_connect_tunnel(
        self,
        reader: StreamReaderLike,
        writer: asyncio.StreamWriter,
        request: ParsedRequestHead,
        *,
        client: tuple[str, int] | None,
    ) -> None:
        try:
            host, port = self._parse_connect_authority(request.target)
        except Exception:
            await self._write_error(writer, 400, b'bad connect target', keep_alive=False)
            return
        if request.body_kind != 'none':
            await self._write_error(writer, 400, b'connect request body not supported', keep_alive=False)
            return
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=getattr(self.config, 'read_timeout', 5.0))
        except Exception:
            await self._write_error(writer, 502, b'bad gateway', keep_alive=False)
            return
        writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        await writer.drain()
        self.access_logger.log_http(client, 'CONNECT', request.target, 200, f'HTTP/{request.http_version}')
        relay_up = self.scheduler.spawn(self._relay_stream(reader, upstream_writer), owner=f'connect:{request.target}:up')
        relay_down = self.scheduler.spawn(self._relay_stream(upstream_reader, writer), owner=f'connect:{request.target}:down')
        done, pending = await asyncio.wait({relay_up, relay_down}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
            with suppress(Exception):
                await task
        for task in done:
            with suppress(Exception):
                await task

    async def _serve_http11_request(
        self,
        reader: StreamReaderLike,
        writer: asyncio.StreamWriter,
        request: ParsedRequestHead,
        *,
        client: tuple[str, int] | None,
        server: tuple[str, int] | tuple[str, None] | None,
        scheme: str,
        scope_extensions: dict | None = None,
    ) -> bool:
        scope = build_http_scope(
            request,
            client=client,
            server=server,
            scheme=scheme,
            extensions=self._http11_scope_extensions(request, scope_extensions=scope_extensions),
        )
        receive = self._build_http11_receive(reader, writer, request)
        send = HTTPResponseWriter(
            writer,
            keep_alive=request.keep_alive,
            server_header=self.config.server_header_value,
            method=request.method,
            request_headers=request.headers,
        )
        status = 500
        try:
            await self.app(scope, receive, send)
            await send.ensure_complete()
            status = send.status or 500
            self.state.metrics.requests_served += 1
        except Exception:
            self.logger.exception('application error')
            if not send.started:
                await self._write_error(writer, 500, b'internal server error', keep_alive=False)
            return False
        self.access_logger.log_http(client, request.method, request.path, status, f'HTTP/{request.http_version}')
        body_complete = getattr(receive, 'body_complete', True)
        return request.keep_alive and body_complete

    async def _write_error(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        body: bytes,
        *,
        keep_alive: bool,
    ) -> None:
        writer.write(
            serialize_http11_response_whole(
                status=status,
                headers=[(b'content-type', b'text/plain; charset=utf-8')],
                body=body,
                keep_alive=keep_alive,
                server_header=self.config.server_header_value,
            )
        )
        await writer.drain()
