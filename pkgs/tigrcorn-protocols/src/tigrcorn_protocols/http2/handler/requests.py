from __future__ import annotations

from .imports import *


class HTTP2RequestsMixin:
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


    async def _run_http_app_live(self, stream_id: int, request: ParsedRequest, *, allow_push: bool) -> int:
        extensions = dict(self.scope_extensions)
        state = self.streams.find(stream_id)
        if state is None:
            return 500
        raw_request_trailers = list(state.trailers)
        try:
            request_trailers = apply_request_trailer_policy(raw_request_trailers, self.config.http.trailer_policy)
        except ProtocolError:
            await self._send_response(stream_id, 400, [(b"content-type", b"text/plain")], b"bad request trailers", [], body_segments=None)
            return 400
        if request.method.upper() == "CONNECT":
            extensions["tigrcorn.http.connect"] = {"authority": request.target}
        if request_trailers and self.config.http.trailer_policy != 'drop':
            extensions["tigrcorn.http.request_trailers"] = {}
        if allow_push and self.state.client_allows_push:
            extensions["http.response.push"] = {}
        extensions['tigrcorn.http.response.file'] = {'protocol': 'http/2', 'streaming': True, 'sendfile': False}
        extensions['http.response.pathsend'] = {}
        scope = build_http_scope(
            request,
            client=self.client,
            server=self.server,
            scheme=self.scheme,
            extensions=extensions,
            root_path=self.config.proxy.root_path,
            proxy=self.config.proxy,
        )
        receive = HTTP2QueuedRequestReceive(
            trailers=request_trailers,
            trailer_policy=self.config.http.trailer_policy,
            on_body_consumed=lambda amount: self._maybe_replenish_receive_credit(stream_id, amount),
        )
        state.request_receive = receive
        for part in state.body_parts:
            await receive.put_body(part, more_body=True)
        state.body_parts.clear()
        if state.end_stream_received:
            await receive.finish_body()

        response_started = False
        response_complete = False
        final_status = 500

        async def send(message: dict) -> None:
            nonlocal response_started, response_complete, final_status
            message_type = message.get("type")
            if message_type == "http.response.push":
                if not allow_push or not self.state.client_allows_push:
                    raise ProtocolError("HTTP/2 server push is not available on this stream")
                await self._send_push_promise(stream_id, message)
                return
            if message_type == "http.response.start":
                status = int(message["status"])
                headers = list(message.get("headers", []))
                if status < 200:
                    await self._send_stream_headers(stream_id, status, sanitize_early_hints_headers(headers), end_stream=False)
                    return
                if response_started:
                    raise ProtocolError("http.response.start sent more than once")
                response_started = True
                final_status = status
                await self._send_stream_headers(stream_id, status, headers, end_stream=False)
                return
            if message_type == "http.response.body":
                if response_complete:
                    raise ProtocolError("http.response.body sent after response completion")
                if not response_started:
                    response_started = True
                    final_status = 200
                    await self._send_stream_headers(stream_id, 200, [], end_stream=False)
                body = bytes(message.get("body", b""))
                more_body = bool(message.get("more_body", False))
                await self._send_stream_data(stream_id, body, end_stream=not more_body)
                if not more_body:
                    response_complete = True
                return
            raise ProtocolError(f"unsupported HTTP/2 ASGI send message: {message_type!r}")

        try:
            await self.app(scope, receive, send)
            if not response_complete:
                if not response_started:
                    response_started = True
                    final_status = 200
                    await self._send_stream_headers(stream_id, 200, [], end_stream=False)
                await self._send_stream_data(stream_id, b"", end_stream=True)
                response_complete = True
            return final_status
        except Exception:
            if not response_started and self.streams.find(stream_id) is not None:
                await self._send_response(stream_id, 500, [(b"content-type", b"text/plain")], b"internal server error")
            elif response_started and not response_complete and self.streams.find(stream_id) is not None:
                await self._send_stream_data(stream_id, b"", end_stream=True)
            return 500
        finally:
            if state.request_receive is receive:
                state.request_receive = None

