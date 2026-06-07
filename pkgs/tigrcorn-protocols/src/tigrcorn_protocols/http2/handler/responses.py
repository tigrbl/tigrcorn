from __future__ import annotations

from .imports import *


class HTTP2ResponsesMixin:
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
        if method_text not in {"GET", "HEAD"}:
            raise ProtocolError("HTTP/2 server push requires a safe cacheable method")
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

