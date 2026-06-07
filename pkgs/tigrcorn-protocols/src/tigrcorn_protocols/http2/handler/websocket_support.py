from __future__ import annotations

from .imports import *


class HTTP2WebSocketSupportMixin:
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

