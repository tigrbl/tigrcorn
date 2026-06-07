from __future__ import annotations

from .imports import *

class _HTTP3ConnectTunnel:
    def __init__(
        self,
        *,
        handler: HTTP3DatagramHandler,
        session: HTTP3Session,
        stream_id: int,
        authority: str,
        endpoint: UDPEndpoint,
        upstream_reader: asyncio.StreamReader,
        upstream_writer: asyncio.StreamWriter,
        work_lease: object | None = None,
    ) -> None:
        self.handler = handler
        self.session = session
        self.stream_id = stream_id
        self.authority = authority
        self.endpoint = endpoint
        self.upstream_reader = upstream_reader
        self.upstream_writer = upstream_writer
        self.work_lease = work_lease
        self.relay_task: asyncio.Task[None] | None = None
        self.client_input_closed = False
        self.server_output_closed = False
        self.closed = False

    def start(self) -> None:
        self.relay_task = asyncio.create_task(
            self._relay_upstream_to_client(),
            name=f'tigrcorn-h3-connect-{self.stream_id}',
        )

    async def feed_client_data(self, chunks: list[bytes], *, end_stream: bool, already_locked: bool = False) -> None:
        if self.closed:
            return
        try:
            wrote = False
            for chunk in chunks:
                if not chunk:
                    continue
                self.upstream_writer.write(chunk)
                wrote = True
            if wrote:
                await self.upstream_writer.drain()
            if end_stream and not self.client_input_closed:
                self.client_input_closed = True
                await half_close_tcp_writer(self.upstream_writer)
        except Exception:
            await self.handler._reset_http3_tunnel_stream(
                self.session,
                self.stream_id,
                self.endpoint,
                already_locked=already_locked,
            )
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
        self.session.connect_tunnels.pop(self.stream_id, None)
        lease = self.session.stream_work_leases.pop(self.stream_id, None)
        if lease is not None:
            lease.release()
        elif self.work_lease is not None:
            self.work_lease.release()
        await close_tcp_writer(self.upstream_writer)

    async def _relay_upstream_to_client(self) -> None:
        reset_stream = False
        try:
            while True:
                chunk = await asyncio.wait_for(self.upstream_reader.read(65536), timeout=self.handler.config.http.idle_timeout)
                if not chunk:
                    break
                await self.handler._send_http3_tunnel_data(
                    self.session,
                    self.stream_id,
                    chunk,
                    end_stream=False,
                    endpoint=self.endpoint,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            reset_stream = True
        else:
            with suppress(Exception):
                await self.handler._send_http3_tunnel_data(
                    self.session,
                    self.stream_id,
                    b'',
                    end_stream=True,
                    endpoint=self.endpoint,
                )
        finally:
            self.server_output_closed = True
            if reset_stream:
                with suppress(Exception):
                    await self.handler._reset_http3_tunnel_stream(self.session, self.stream_id, self.endpoint)
            await self._finish_if_complete()

    async def _finish_if_complete(self) -> None:
        if self.client_input_closed and self.server_output_closed:
            await self.abort()


class HTTP3ConnectMixin:
    async def _send_http3_tunnel_data(
        self,
        session: HTTP3Session,
        stream_id: int,
        data: bytes,
        *,
        end_stream: bool,
        endpoint: UDPEndpoint,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._send_http3_tunnel_data(
                    session,
                    stream_id,
                    data,
                    end_stream=end_stream,
                    endpoint=endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        if stream_id not in session.connect_tunnels:
            return
        outbound = self._build_http3_data_datagrams_locked(session, stream_id, data, end_stream=end_stream)
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _reset_http3_tunnel_stream(
        self,
        session: HTTP3Session,
        stream_id: int,
        endpoint: UDPEndpoint,
        *,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._reset_http3_tunnel_stream(
                    session,
                    stream_id,
                    endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        self._release_stream_work_lease(session, stream_id)
        session.h3.abandon_stream(stream_id)
        outbound = self._flush_qpack_streams(session)
        outbound.append(session.quic.reset_stream(stream_id, H3_CONNECT_ERROR))
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _abort_session_tunnels(self, session: HTTP3Session) -> None:
        for tunnel in list(session.connect_tunnels.values()):
            with suppress(Exception):
                await tunnel.abort()
    async def _start_connect_tunnel_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
        header_map: dict[bytes, bytes],
        endpoint: UDPEndpoint,
    ) -> list[bytes]:
        authority = header_map.get(b':authority', b'').decode('ascii', 'replace')
        try:
            host, port = parse_connect_authority(authority)
        except Exception:
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 400, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                400,
                [(b'content-type', b'text/plain')],
                b'bad connect target',
                end_stream=True,
            )
        if self.config.http.connect_policy == 'deny':
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 403, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                403,
                [(b'content-type', b'text/plain')],
                b'connect denied',
                end_stream=True,
            )
        if self.config.http.connect_policy == 'allowlist' and not is_connect_allowed(host, port, self.config.http.connect_allow):
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 403, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                403,
                [(b'content-type', b'text/plain')],
                b'connect denied',
                end_stream=True,
            )
        if not self._admit_stream_work(session, stream_id):
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 503, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                503,
                [(b'content-type', b'text/plain')],
                b'scheduler overloaded',
                end_stream=True,
            )
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=getattr(self.config, 'read_timeout', 5.0),
            )
        except Exception:
            self._release_stream_work_lease(session, stream_id)
            self.access_logger.log_http(session.addr, 'CONNECT', authority, 502, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                502,
                [(b'content-type', b'text/plain')],
                b'bad gateway',
                end_stream=True,
            )
        tunnel = _HTTP3ConnectTunnel(
            handler=self,
            session=session,
            stream_id=stream_id,
            authority=authority,
            endpoint=endpoint,
            upstream_reader=upstream_reader,
            upstream_writer=upstream_writer,
            work_lease=session.stream_work_leases.get(stream_id),
        )
        session.connect_tunnels[stream_id] = tunnel
        tunnel.start()
        self.access_logger.log_http(session.addr, 'CONNECT', authority, 200, 'HTTP/3')
        return self._build_http3_response_datagrams_locked(session, stream_id, 200, [], b'', end_stream=False)
    async def _drain_connect_request_body_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
    ) -> None:
        tunnel = session.connect_tunnels.get(stream_id)
        if tunnel is None:
            return
        chunks = list(request_state.body_parts)
        request_state.body_parts.clear()
        await tunnel.feed_client_data(chunks, end_stream=request_state.ended, already_locked=True)
