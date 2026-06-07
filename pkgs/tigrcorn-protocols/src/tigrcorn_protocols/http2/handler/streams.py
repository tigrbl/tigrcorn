from __future__ import annotations

from .imports import *


class HTTP2StreamsMixin:
    async def _maybe_dispatch(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.dispatched or not state.headers_complete:
            return
        protocol = self._extended_connect_protocol(state.headers)
        is_ws = self._is_extended_connect_websocket(state.headers)
        is_connect = self._is_generic_connect_tunnel(state.headers)
        if protocol is not None and (protocol != b"websocket" or not self.config.websocket.enabled):
            request = self._build_request(state)
            if not self._admit_stream_work(stream_id):
                await self._send_response(stream_id, 503, [(b"content-type", b"text/plain")], b"scheduler overloaded")
                self.access_logger.log_http(self.client, request.method, request.path, 503, "HTTP/2")
                self._release_stream_work_lease(stream_id)
                self._cancel_stream(stream_id)
                self.streams.close(stream_id)
                self._maybe_finish_after_goaway()
                return
            state.dispatched = True
            await self._send_response(
                stream_id,
                501,
                [(b"content-type", b"text/plain")],
                b"unsupported extended connect protocol",
            )
            self.access_logger.log_http(self.client, request.method, request.path, 501, "HTTP/2")
            self._release_stream_work_lease(stream_id)
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()
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



    def _finalize_stream_if_complete(self, stream_id: int) -> None:
        state = self.streams.find(stream_id)
        if state is None or state.websocket_session is not None or state.connect_tunnel is not None:
            return
        if state.local_closed and state.end_stream_received:
            self._release_stream_work_lease(stream_id)
            self._cancel_stream(stream_id)
            self.streams.close(stream_id)
            self._maybe_finish_after_goaway()


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
            if state.end_stream_received:
                status, headers, body, trailers, informational, body_segments, cleanup = await self._run_http_app(stream_id, request, allow_push=True)
                for interim_status, interim_headers in informational:
                    await self._send_stream_headers(stream_id, interim_status, sanitize_early_hints_headers(interim_headers), end_stream=False)
                try:
                    await self._send_response(stream_id, status, headers, body, trailers, body_segments=body_segments)
                finally:
                    if cleanup is not None:
                        cleanup()
            else:
                status = await self._run_http_app_live(stream_id, request, allow_push=True)
            self.access_logger.log_http(self.client, request.method, request.path, status, "HTTP/2")
            if self.streams.find(stream_id) is not None:
                self._finalize_stream_if_complete(stream_id)
            self._maybe_finish_after_goaway()
        finally:
            self._release_stream_work_lease(stream_id)


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

