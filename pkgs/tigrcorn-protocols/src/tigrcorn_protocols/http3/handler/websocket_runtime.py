from __future__ import annotations

from .imports import *

class HTTP3WebSocketRuntimeMixin:
    async def _send_http3_websocket_headers(
        self,
        session: HTTP3Session,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        *,
        end_stream: bool,
        endpoint: UDPEndpoint,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._send_http3_websocket_headers(
                    session,
                    stream_id,
                    status,
                    headers,
                    end_stream=end_stream,
                    endpoint=endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        if stream_id not in session.websocket_sessions:
            return
        outbound = self._build_http3_response_datagrams_locked(
            session,
            stream_id,
            status,
            headers,
            b'',
            end_stream=end_stream,
        )
        if end_stream:
            session.websocket_sessions.pop(stream_id, None)
            self._release_stream_work_lease(session, stream_id)
            session.h3.abandon_stream(stream_id)
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _send_http3_websocket_data(
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
                await self._send_http3_websocket_data(
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
        if stream_id not in session.websocket_sessions:
            return
        outbound = self._build_http3_data_datagrams_locked(session, stream_id, data, end_stream=end_stream)
        if end_stream:
            session.websocket_sessions.pop(stream_id, None)
            self._release_stream_work_lease(session, stream_id)
            session.h3.abandon_stream(stream_id)
        self._queue_session_outbound_locked(session, outbound, endpoint)
    async def _reset_http3_websocket_stream(
        self,
        session: HTTP3Session,
        stream_id: int,
        endpoint: UDPEndpoint,
        *,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._reset_http3_websocket_stream(
                    session,
                    stream_id,
                    endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        session.websocket_sessions.pop(stream_id, None)
        self._release_stream_work_lease(session, stream_id)
        session.h3.abandon_stream(stream_id)
        outbound = self._flush_qpack_streams(session)
        outbound.append(session.quic.reset_stream(stream_id, H3_REQUEST_CANCELLED))
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _abort_session_websockets(self, session: HTTP3Session) -> None:
        for websocket in list(session.websocket_sessions.values()):
            with suppress(Exception):
                await websocket.abort()
        session.websocket_sessions.clear()
    async def _start_websocket_stream_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
        header_map: dict[bytes, bytes],
        endpoint: UDPEndpoint,
    ) -> list[bytes]:
        request = self._build_request(request_state, header_map)
        authority = header_map.get(b':authority')
        if self.config.allowed_server_names and not authority_allowed(authority, self.config.allowed_server_names):
            self.access_logger.log_http(session.addr, 'CONNECT', request.path, 421, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                421,
                [(b'content-type', b'text/plain')],
                b'misdirected request',
                end_stream=True,
            )
        local = endpoint.local_addr
        server = (local[0], local[1]) if isinstance(local, tuple) and len(local) >= 2 else ('', None)
        scheme = header_map.get(
            b':scheme',
            self.listener.scheme.encode('ascii', 'ignore') if self.listener.scheme else b'https',
        ).decode('ascii', 'replace')
        if not self._admit_stream_work(session, stream_id):
            self.access_logger.log_http(session.addr, 'CONNECT', request.path, 503, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                503,
                [(b'content-type', b'text/plain')],
                b'scheduler overloaded',
                end_stream=True,
            )
        try:
            websocket = H3WebSocketSession(
                app=self.app,
                config=self.config,
                request=request,
                client=session.addr,
                server=server,
                scheme=scheme,
                send_headers=lambda status, headers, end_stream: self._send_http3_websocket_headers(
                    session,
                    stream_id,
                    status,
                    headers,
                    end_stream=end_stream,
                    endpoint=endpoint,
                ),
                send_data=lambda data, end_stream: self._send_http3_websocket_data(
                    session,
                    stream_id,
                    data,
                    end_stream=end_stream,
                    endpoint=endpoint,
                ),
                metrics=self.metrics,
                on_close=lambda session=session, stream_id=stream_id: self._on_websocket_stream_closed(session, stream_id),
            )
        except ProtocolError:
            self._release_stream_work_lease(session, stream_id)
            self.access_logger.log_http(session.addr, 'CONNECT', request.path, 400, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                400,
                [(b'content-type', b'text/plain')],
                b'bad request',
                end_stream=True,
            )
        session.websocket_sessions[stream_id] = websocket
        await websocket.start()
        return []
    async def _drain_websocket_request_body_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
        endpoint: UDPEndpoint,
    ) -> None:
        websocket = session.websocket_sessions.get(stream_id)
        if websocket is None:
            return
        chunks = list(request_state.body_parts)
        request_state.body_parts.clear()
        try:
            await websocket.feed_data(b''.join(chunks), end_stream=request_state.ended)
        except Exception:
            await self._reset_http3_websocket_stream(
                session,
                stream_id,
                endpoint,
                already_locked=True,
            )
            await websocket.abort()
