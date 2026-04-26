from __future__ import annotations

import asyncio
import random
from contextlib import suppress
from typing import Any

from tigrcorn_asgi.receive import HTTPRequestReceive, HTTPStreamingRequestReceive
from tigrcorn_asgi.scopes.http import build_http_scope
from tigrcorn_asgi.send import FileBodySegment, HTTPResponseCollector, iter_response_body_segments, response_body_segments_have_bytes
from tigrcorn_runtime.app_interfaces import resolve_app_dispatch
from tigrcorn_core.errors import ProtocolError
from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_core.constants import H2_PREFACE
from tigrcorn_transports.listeners.inproc import InProcListener
from tigrcorn_transports.listeners.pipe import PipeListener
from tigrcorn_transports.listeners.tcp import TCPListener
from tigrcorn_transports.listeners.udp import UDPListener
from tigrcorn_transports.listeners.unix import UnixListener
from tigrcorn_observability.logging import AccessLogger, configure_logging, resolve_logging_config
from tigrcorn_observability.metrics import StatsdExporter
from tigrcorn_observability.tracing import OtelExporter, span
from tigrcorn_protocols.connect import is_connect_allowed, parse_connect_authority
from tigrcorn_http.alt_svc import configured_alt_svc_values
from tigrcorn_http.entity import apply_response_entity_semantics, plan_file_backed_response_entity_semantics
from tigrcorn_protocols.http1.keepalive import apply_keep_alive_policy
from tigrcorn_protocols.http1.parser import ParsedRequestHead, read_http11_request_head
from tigrcorn_protocols.http1.serializer import finalize_chunked_body, serialize_http11_response_chunk, serialize_http11_response_head, serialize_http11_response_whole
from tigrcorn_protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn_protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn_protocols.lifespan.driver import LifespanManager
from tigrcorn_protocols.rawframed.handler import RawFramedApplicationHandler
from tigrcorn_protocols.websocket.handler import WebSocketConnectionHandler
from tigrcorn_protocols.scheduler import ProductionScheduler, SchedulerPolicy
from tigrcorn_security.tls import build_server_ssl_context, tls_extension_payload
from tigrcorn_runtime.server.hooks import run_async_hooks
from tigrcorn_runtime.server.state import ServerState
from tigrcorn_transports.tcp.reader import PrebufferedReader
from tigrcorn_core.types import ASGIApp, StreamReaderLike
from tigrcorn_core.utils.authority import authority_allowed
from tigrcorn_core.utils.headers import get_header
from tigrcorn_core.utils.net import peer_parts
from tigrcorn_core.utils.proxy import resolve_proxy_view


class TigrCornServer:
    def __init__(self, app: ASGIApp, config: ServerConfig) -> None:
        selection = resolve_app_dispatch(app, config.app.interface)
        self.app = selection.app
        self.app_interface = selection.interface
        self.config = config
        self._resolved_logging = resolve_logging_config(config.log_level, config=config.logging)
        self.logger = configure_logging(config.log_level, config=config.logging)
        self.access_logger = AccessLogger(
            self.logger,
            enabled=self._resolved_logging.access_log,
            fmt=self._resolved_logging.access_log_format,
        )
        self.state = ServerState()
        self.lifespan = LifespanManager(app, mode=config.lifespan)
        self._listeners: list[TCPListener | UDPListener | UnixListener | PipeListener | InProcListener] = []
        self._should_exit = asyncio.Event()
        self._started = False
        self._metrics_server: asyncio.AbstractServer | None = None
        self._request_budget_task: asyncio.Task[None] | None = None
        self._statsd_exporter = StatsdExporter(config.metrics.statsd_host, logger=self.logger) if config.metrics.statsd_host else None
        self._otel_exporter = OtelExporter(config.metrics.otel_endpoint, logger=self.logger) if config.metrics.otel_endpoint else None
        policy = SchedulerPolicy()
        if config.scheduler.max_connections is not None:
            policy.max_connections = config.scheduler.max_connections
        if config.scheduler.max_tasks is not None:
            policy.max_tasks = config.scheduler.max_tasks
        if config.scheduler.max_streams is not None:
            policy.max_streams_per_session = config.scheduler.max_streams
        if config.scheduler.limit_concurrency is not None:
            policy.limit_concurrency = config.scheduler.limit_concurrency
        self.scheduler = ProductionScheduler(policy)
        self._request_budget = None
        if config.process.limit_max_requests is not None:
            jitter = max(0, config.process.max_requests_jitter)
            self._request_budget = config.process.limit_max_requests + (random.randint(0, jitter) if jitter else 0)

    async def start(self) -> None:
        if self._started:
            return
        with span('server.start', attrs={'listener_count': len(self.config.listeners)}, sink=self._otel_exporter.record_span if self._otel_exporter is not None else None):
            await self.lifespan.startup()
            await run_async_hooks(self.config.hooks.on_startup, self)
            for listener_cfg in self.config.listeners:
                listener = await self._make_listener(listener_cfg)
                await listener.start(self._make_client_handler(listener_cfg))
                self._sync_listener_bound_address(listener_cfg, listener)
                self._listeners.append(listener)
                self.logger.info('listening on %s', listener_cfg.label)
            if self.config.metrics.enabled and self.config.metrics.bind:
                self._metrics_server = await self._start_metrics_endpoint(self.config.metrics.bind)
            if self._statsd_exporter is not None:
                await self._statsd_exporter.start(self.state.metrics)
            if self._otel_exporter is not None:
                await self._otel_exporter.start(self.state.metrics)
            if self._request_budget is not None:
                self._request_budget_task = asyncio.create_task(self._monitor_request_budget(), name='tigrcorn-request-budget')
        self._started = True

    async def serve_forever(self) -> None:
        await self.start()
        try:
            await self._should_exit.wait()
        finally:
            await self.close()

    @staticmethod
    def _sync_listener_bound_address(cfg: ListenerConfig, listener: Any) -> None:
        server = getattr(listener, 'server', None)
        sockets = getattr(server, 'sockets', None) if server is not None else None
        if sockets:
            sockname = sockets[0].getsockname()
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                cfg.host = str(sockname[0])
                cfg.port = int(sockname[1])
                return
            if isinstance(sockname, str):
                cfg.path = sockname
                return
        transport = getattr(listener, 'transport', None)
        if transport is not None:
            sockname = transport.get_extra_info('sockname')
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                cfg.host = str(sockname[0])
                cfg.port = int(sockname[1])
                return
            if isinstance(sockname, str):
                cfg.path = sockname
                return

    def request_shutdown(self) -> None:
        self._should_exit.set()

    async def close(self) -> None:
        if self.state.shutting_down:
            return
        self.state.shutting_down = True
        with span('server.shutdown', attrs={'active_listeners': len(self._listeners)}, sink=self._otel_exporter.record_span if self._otel_exporter is not None else None):
            if self._request_budget_task is not None:
                self._request_budget_task.cancel()
                with suppress(Exception):
                    await self._request_budget_task
            if self._metrics_server is not None:
                self._metrics_server.close()
                with suppress(Exception):
                    await self._metrics_server.wait_closed()
                self._metrics_server = None
            for listener in self._listeners:
                with suppress(Exception):
                    await listener.close()
            self._listeners.clear()
            with suppress(Exception):
                await asyncio.wait_for(self.scheduler.close(), timeout=self.config.http.shutdown_timeout)
            with suppress(Exception):
                await self.lifespan.shutdown()
            with suppress(Exception):
                await run_async_hooks(self.config.hooks.on_shutdown, self)
        if self._statsd_exporter is not None:
            with suppress(Exception):
                await self._statsd_exporter.stop(self.state.metrics)
        if self._otel_exporter is not None:
            with suppress(Exception):
                await self._otel_exporter.stop(self.state.metrics)

    async def _make_listener(self, cfg: ListenerConfig):
        if cfg.kind == 'tcp':
            ssl_ctx = build_server_ssl_context(cfg)
            return TCPListener(
                cfg.host,
                cfg.port,
                cfg.backlog,
                ssl=ssl_ctx,
                reuse_port=cfg.reuse_port,
                reuse_address=cfg.reuse_address,
                nodelay=cfg.nodelay,
                fd=cfg.fd,
            )
        if cfg.kind == 'udp':
            return UDPListener(cfg.host, cfg.port, reuse_port=cfg.reuse_port, fd=cfg.fd)
        if cfg.kind == 'unix':
            ssl_ctx = build_server_ssl_context(cfg)
            return UnixListener(cfg.path or '', cfg.backlog, ssl=ssl_ctx, fd=cfg.fd)
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
                scheduler=self.scheduler,
                metrics=self.state.metrics,
            )

            async def udp_handler(packet, endpoint) -> None:
                sessions_before = len(h3_handler.sessions)
                responses_before = sum(len(session.responded_streams) for session in h3_handler.sessions.values())
                await h3_handler.handle_packet(packet, endpoint)
                if len(h3_handler.sessions) > sessions_before:
                    self.state.metrics.connection_opened()
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
                self.state.metrics.bytes_received += len(data)

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
        self.state.metrics.connection_opened()
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
                    scheduler=self.scheduler,
                    metrics=self.state.metrics,
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
                        scheduler=self.scheduler,
                        metrics=self.state.metrics,
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
            self.state.metrics.connection_closed()
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

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
                await self._handle_http11_connect_tunnel(reader, writer, request, client=request_client)
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
                try:
                    self.state.metrics.websocket_opened()
                    await handler.handle()
                finally:
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
                keep_handling = await self._serve_http11_request(
                reader,
                writer,
                request,
                client=request_client,
                server=request_server,
                scheme=request_scheme,
                scope_extensions=scope_extensions,
            )
            finally:
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

    async def _try_http11_sendfile(self, writer: asyncio.StreamWriter, segment: FileBodySegment) -> bool:
        if segment.count is not None and segment.count <= 0:
            return True
        if writer.get_extra_info('ssl_object') is not None or writer.get_extra_info('sslcontext') is not None:
            return False
        transport = getattr(writer, 'transport', None) or getattr(writer, '_transport', None)
        if transport is None:
            return False
        loop = asyncio.get_running_loop()
        try:
            with open(segment.path, 'rb') as handle:
                await loop.sendfile(transport, handle, offset=segment.offset, count=segment.count, fallback=False)
            return True
        except Exception:
            return False

    async def _send_http11_body_segments(self, writer: asyncio.StreamWriter, body_segments: list, *, chunked: bool = False) -> None:
        if not chunked and len(body_segments) == 1 and isinstance(body_segments[0], FileBodySegment):
            if await self._try_http11_sendfile(writer, body_segments[0]):
                return
        async for chunk in iter_response_body_segments(body_segments):
            self.state.metrics.bytes_sent += len(chunk)
            if chunked:
                writer.write(serialize_http11_response_chunk(chunk))
            else:
                writer.write(chunk)
            if len(chunk) >= 64 * 1024:
                await self._drain_writer(writer)
        await self._drain_writer(writer)

    async def _send_http11_streamed_response(
        self,
        writer: asyncio.StreamWriter,
        *,
        request: ParsedRequestHead,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body_segments: list,
        trailers: list[tuple[bytes, bytes]],
    ) -> None:
        has_body = response_body_segments_have_bytes(body_segments)
        if trailers:
            writer.write(
                serialize_http11_response_head(
                    status=status,
                    headers=headers,
                    keep_alive=request.keep_alive,
                    server_header=self.config.server_header_value,
                    chunked=True,
                    include_date_header=self.config.include_date_header,
                    default_headers=self.config.default_response_headers,
                    alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                )
            )
            await self._drain_writer(writer)
            if has_body:
                await self._send_http11_body_segments(writer, body_segments, chunked=True)
            writer.write(finalize_chunked_body(trailers))
            await self._drain_writer(writer)
            return
        if not has_body:
            writer.write(
                serialize_http11_response_whole(
                    status=status,
                    headers=headers,
                    body=b'',
                    keep_alive=request.keep_alive,
                    server_header=self.config.server_header_value,
                    include_date_header=self.config.include_date_header,
                    default_headers=self.config.default_response_headers,
                    alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                )
            )
            await self._drain_writer(writer)
            return
        writer.write(
            serialize_http11_response_head(
                status=status,
                headers=headers,
                keep_alive=request.keep_alive,
                server_header=self.config.server_header_value,
                chunked=False,
                include_date_header=self.config.include_date_header,
                default_headers=self.config.default_response_headers,
                alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
            )
        )
        await self._drain_writer(writer)
        await self._send_http11_body_segments(writer, body_segments, chunked=False)

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
        if self.config.http.connect_policy == 'deny':
            await self._write_error(writer, 403, b'connect denied', keep_alive=False)
            return
        if self.config.http.connect_policy == 'allowlist' and not is_connect_allowed(host, port, self.config.http.connect_allow):
            await self._write_error(writer, 403, b'connect denied', keep_alive=False)
            return
        if request.body_kind != 'none':
            await self._write_error(writer, 400, b'connect request body not supported', keep_alive=False)
            return
        work_lease = self.scheduler.acquire_work()
        if work_lease is None:
            self.state.metrics.scheduler_task_rejected()
            await self._write_error(writer, 503, b'scheduler overloaded', keep_alive=False)
            return
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=self.config.http.read_timeout)
        except Exception:
            work_lease.release()
            await self._write_error(writer, 502, b'bad gateway', keep_alive=False)
            return
        writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        await self._drain_writer(writer)
        self.access_logger.log_http(client, 'CONNECT', request.target, 200, f'HTTP/{request.http_version}')
        try:
            self.state.metrics.scheduler_task_spawned()
            relay_up = self.scheduler.spawn(self._relay_stream(reader, upstream_writer), owner=f'connect:{request.target}:up')
            self.state.metrics.scheduler_task_spawned()
            relay_down = self.scheduler.spawn(self._relay_stream(upstream_reader, writer), owner=f'connect:{request.target}:down')
        except RuntimeError:
            self.state.metrics.scheduler_task_rejected()
            await self._write_error(writer, 503, b'scheduler overloaded', keep_alive=False)
            return
        try:
            done, pending = await asyncio.wait({relay_up, relay_down}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                with suppress(Exception):
                    await task
            for task in done:
                with suppress(Exception):
                    await task
        finally:
            work_lease.release()

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
        host_header = get_header(request.headers, b'host')
        if self.config.allowed_server_names and not authority_allowed(host_header, self.config.allowed_server_names):
            await self._write_error(writer, 421, b'misdirected request', keep_alive=False)
            return False
        scope = build_http_scope(
            request,
            client=client,
            server=server,
            scheme=scheme,
            extensions=self._http11_scope_extensions(request, scope_extensions=scope_extensions),
            root_path=self.config.proxy.root_path,
            proxy=self.config.proxy,
        )
        receive = self._build_http11_receive(reader, writer, request)
        send = HTTPResponseCollector()
        status = 500
        trailers: list[tuple[bytes, bytes]] = []
        try:
            await self.app(scope, receive, send)
            send.finalize()
            assert send.status is not None
            status = send.status
            headers = list(send.headers)
            trailers = list(send.trailers)
            body = b''
            body_segments = list(send.body_segments) if send.uses_streamed_body else None
            for interim_status, interim_headers in send.informational_responses:
                writer.write(
                    serialize_http11_response_head(
                        status=interim_status,
                        headers=interim_headers,
                        keep_alive=request.keep_alive,
                        server_header=self.config.server_header_value,
                        chunked=False,
                        include_date_header=self.config.include_date_header,
                        default_headers=self.config.default_response_headers,
                        alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                    )
                )
            if body_segments is None and send.has_spooled_body():
                spooled_segments = send.spooled_body_segments()
                spooled_path = ''
                if spooled_segments:
                    first_segment = spooled_segments[0]
                    if isinstance(first_segment, FileBodySegment):
                        spooled_path = first_segment.path
                planned = plan_file_backed_response_entity_semantics(
                    method=request.method,
                    request_headers=request.headers,
                    response_headers=headers,
                    status=status,
                    body_path=spooled_path,
                    body_length=send.body_length,
                    generated_etag=send.generated_entity_tag(),
                    apply_content_coding=True,
                    trailers_present=bool(trailers) and request.method.upper() != 'HEAD',
                )
                if planned.requires_materialization:
                    body = await send.materialize_body()
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
                        trailers_present=bool(trailers) and request.method.upper() != 'HEAD',
                    )
                    status = processed.status
                    headers = processed.headers
                    body = processed.body
                    if processed.head_response:
                        trailers = []
                elif planned.use_body_segments:
                    status = planned.status
                    headers = planned.headers
                    body_segments = list(planned.body_segments)
                    body = b''
                else:
                    status = planned.status
                    headers = planned.headers
                    body = planned.body
                    trailers = []
            elif body_segments is None:
                body = await send.materialize_body()
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
                    trailers_present=bool(trailers) and request.method.upper() != 'HEAD',
                )
                status = processed.status
                headers = processed.headers
                body = processed.body
                if processed.head_response:
                    trailers = []
            if body_segments is None:
                if trailers:
                    writer.write(
                        serialize_http11_response_head(
                            status=status,
                            headers=headers,
                            keep_alive=request.keep_alive,
                            server_header=self.config.server_header_value,
                            chunked=True,
                            include_date_header=self.config.include_date_header,
                            default_headers=self.config.default_response_headers,
                            alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                        )
                    )
                    if body:
                        writer.write(serialize_http11_response_chunk(body))
                    writer.write(finalize_chunked_body(trailers))
                    await self._drain_writer(writer)
                else:
                    writer.write(
                        serialize_http11_response_whole(
                            status=status,
                            headers=headers,
                            body=body,
                            keep_alive=request.keep_alive,
                            server_header=self.config.server_header_value,
                            include_date_header=self.config.include_date_header,
                            default_headers=self.config.default_response_headers,
                            alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                        )
                    )
                    await self._drain_writer(writer)
            else:
                await self._send_http11_streamed_response(
                    writer,
                    request=request,
                    status=status,
                    headers=headers,
                    body_segments=body_segments,
                    trailers=trailers,
                )
            self.state.metrics.requests_served += 1
        except ProtocolError:
            self.state.metrics.requests_failed += 1
            await self._write_error(writer, 400, b'bad request trailers', keep_alive=False)
            return False
        except Exception:
            self.state.metrics.requests_failed += 1
            self.logger.exception('application error')
            await self._write_error(writer, 500, b'internal server error', keep_alive=False)
            return False
        finally:
            send.cleanup()
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
                include_date_header=self.config.include_date_header,
                default_headers=self.config.default_response_headers,
                alt_svc_values=configured_alt_svc_values(self.config, request_http_version='1.1'),
            )
        )
        await self._drain_writer(writer)

    async def _start_metrics_endpoint(self, bind: str) -> asyncio.AbstractServer:
        host, port = self._parse_bind_target(bind)
        server = await asyncio.start_server(self._handle_metrics_request, host=host, port=port)
        self.logger.info('metrics endpoint listening on %s', bind)
        return server

    async def _handle_metrics_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        with suppress(Exception):
            await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=1.0)
        payload = self.state.metrics.render_prometheus().encode('utf-8')
        response = serialize_http11_response_whole(
            status=200,
            headers=[(b'content-type', b'text/plain; version=0.0.4')],
            body=payload,
            keep_alive=False,
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
        )
        writer.write(response)
        with suppress(Exception):
            await writer.drain()
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

    @staticmethod
    def _parse_bind_target(bind: str) -> tuple[str, int]:
        if bind.startswith('[') and ']:' in bind:
            host, port = bind.rsplit(':', 1)
            return host[1:-1], int(port)
        host, port = bind.rsplit(':', 1)
        return host, int(port)

    async def _monitor_request_budget(self) -> None:
        assert self._request_budget is not None
        while not self._should_exit.is_set() and not self.state.shutting_down:
            if self.state.metrics.requests_served >= self._request_budget:
                self.logger.info('request budget reached, shutting down worker')
                self.request_shutdown()
                return
            await asyncio.sleep(0.1)
