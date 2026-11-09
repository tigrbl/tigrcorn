from __future__ import annotations

from .imports import *


class HTTP2HeadersMixin:
    def _validate_new_remote_stream(self, stream_id: int) -> None:
        if stream_id % 2 == 0:
            raise ProtocolError("client-initiated HTTP/2 streams must use odd stream ids")
        if stream_id <= self.state.highest_remote_stream_id:
            raise ProtocolError("HTTP/2 stream ids must increase")
        if self.state.peer_goaway_received or self.state.local_goaway_sent:
            raise ProtocolError("HTTP/2 new stream received after GOAWAY")
        if self.streams.active_remote_stream_count() >= self.state.max_concurrent_streams:
            raise ProtocolError("HTTP/2 maximum concurrent streams exceeded")
        self.state.highest_remote_stream_id = stream_id
        self.state.last_stream_id = max(self.state.last_stream_id, stream_id)


    def _append_header_fragment(self, state: H2StreamState, fragment: bytes) -> None:
        next_size = state.header_block_bytes + len(fragment)
        if next_size > self.config.http.http2_max_headers_size:
            raise ProtocolError("request head exceeds configured http2_max_headers_size")
        state.header_block_bytes = next_size
        state.header_fragments.append(fragment)


    def _validate_header_list_size(self, headers: list[tuple[bytes, bytes]]) -> None:
        size = sum(len(name) + len(value) + 32 for name, value in headers)
        if size > self.state.max_header_list_size:
            raise ProtocolError("HTTP/2 header list exceeds configured maximum")


    def _validate_trailer_headers(self, headers: list[tuple[bytes, bytes]]) -> None:
        for name, value in headers:
            if any(65 <= byte <= 90 for byte in name):
                raise ProtocolError("uppercase header field name forbidden in HTTP/2")
            self._validate_field_value(value)
            if name.startswith(b":"):
                raise ProtocolError("trailer pseudo-header forbidden in HTTP/2")
            if name in {b"connection", b"upgrade", b"proxy-connection", b"transfer-encoding"}:
                raise ProtocolError("connection-specific header forbidden in HTTP/2")
            if name == b"te" and value.lower() != b"trailers":
                raise ProtocolError("invalid TE header for HTTP/2")


    def _validate_field_value(self, value: bytes) -> None:
        if any(byte in {0x00, 0x0A, 0x0D} for byte in value):
            raise ProtocolError("invalid HTTP/2 header field value")
        if value[:1] in {b" ", b"\t"} or value[-1:] in {b" ", b"\t"}:
            raise ProtocolError("invalid HTTP/2 header field value")


    def _parse_content_length(self, headers: list[tuple[bytes, bytes]]) -> int | None:
        values: list[bytes] = []
        for name, value in headers:
            if name.lower() != b"content-length":
                continue
            for part in value.split(b","):
                parsed = part.strip()
                if not parsed:
                    raise ProtocolError("invalid content-length header")
                values.append(parsed)
        if not values:
            return None
        parsed_value: int | None = None
        for value in values:
            if not value.isdigit():
                raise ProtocolError("invalid content-length header")
            current = int(value)
            if parsed_value is None:
                parsed_value = current
                continue
            if parsed_value != current:
                raise ProtocolError("conflicting content-length values")
        return parsed_value


    async def _handle_headers(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0:
            raise ProtocolError("HEADERS must use a stream id")
        if self._continuation_stream_id not in (None, frame.stream_id):
            raise ProtocolError("unexpected HEADERS while CONTINUATION is pending")
        state = self.streams.find(frame.stream_id)
        is_new_stream = state is None
        if is_new_stream:
            if self.streams.is_closed(frame.stream_id):
                raise ProtocolError("HEADERS on closed HTTP/2 stream")
            self._validate_new_remote_stream(frame.stream_id)
            state = self.streams.activate_remote(
                frame.stream_id,
                send_window=self.state.initial_window_size,
                receive_window=self.state.local_initial_window_size,
            )
            state.current_header_block_is_trailers = False
            state.open_remote(end_stream=bool(frame.flags & FLAG_END_STREAM))
        else:
            if state.closed:
                raise ProtocolError("HEADERS on closed HTTP/2 stream")
            if not state.headers_complete:
                raise ProtocolError("duplicate HTTP/2 initial HEADERS block")
            if state.awaiting_continuation:
                raise ProtocolError("unexpected HEADERS while CONTINUATION is pending")
            if state.lifecycle not in {H2StreamLifecycle.OPEN, H2StreamLifecycle.HALF_CLOSED_LOCAL}:
                raise ProtocolError("HEADERS not permitted in current HTTP/2 stream state")
            if state.end_stream_received or state.trailers_complete:
                raise ProtocolError("trailing HEADERS not permitted after end of stream")
            if not (frame.flags & FLAG_END_STREAM):
                raise ProtocolError("trailing HTTP/2 HEADERS must carry END_STREAM")
            state.current_header_block_is_trailers = True
            state.receive_end_stream()
        self._append_header_fragment(state, headers_payload_fragment(frame.payload, frame.flags))
        state.awaiting_continuation = not bool(frame.flags & FLAG_END_HEADERS)
        if state.awaiting_continuation:
            self._continuation_stream_id = frame.stream_id
            return
        self._continuation_stream_id = None
        self._finish_headers(state)
        await self._maybe_dispatch(frame.stream_id)


    async def _handle_continuation(self, frame: HTTP2Frame) -> None:
        if frame.stream_id == 0:
            raise ProtocolError("CONTINUATION must use a stream id")
        if self._continuation_stream_id != frame.stream_id:
            raise ProtocolError("unexpected CONTINUATION stream")
        state = self.streams.find(frame.stream_id)
        if state is None:
            raise ProtocolError("CONTINUATION for unknown stream")
        self._append_header_fragment(state, frame.payload)
        state.awaiting_continuation = not bool(frame.flags & FLAG_END_HEADERS)
        if state.awaiting_continuation:
            return
        self._continuation_stream_id = None
        self._finish_headers(state)
        await self._maybe_dispatch(frame.stream_id)


    def _finish_headers(self, state: H2StreamState) -> None:
        block = b"".join(state.header_fragments)
        headers = self.hpack_decoder.decode_header_block(block)
        self._validate_header_list_size(headers)
        if state.current_header_block_is_trailers:
            self._validate_trailer_headers(headers)
            state.trailers = headers
            state.trailers_complete = True
        else:
            state.headers = headers
            state.headers_complete = True
            state.expected_content_length = self._parse_content_length(headers)
        state.header_fragments.clear()
        state.header_block_bytes = 0
        state.awaiting_continuation = False
        state.current_header_block_is_trailers = False


    def _pseudo_headers(self, headers: list[tuple[bytes, bytes]]) -> dict[bytes, bytes]:
        return {k: v for k, v in headers if k.startswith(b":")}


    def _extended_connect_protocol(self, headers: list[tuple[bytes, bytes]]) -> bytes | None:
        pseudo = self._pseudo_headers(headers)
        if pseudo.get(b":method") != b"CONNECT":
            return None
        return pseudo.get(b":protocol")


    def _is_extended_connect_websocket(self, headers: list[tuple[bytes, bytes]]) -> bool:
        return self._extended_connect_protocol(headers) == b"websocket"


    def _is_generic_connect_tunnel(self, headers: list[tuple[bytes, bytes]]) -> bool:
        pseudo = self._pseudo_headers(headers)
        return pseudo.get(b":method") == b"CONNECT" and self._extended_connect_protocol(headers) is None

    def _validate_request_headers(self, headers: list[tuple[bytes, bytes]]) -> None:
        pseudo_seen: set[bytes] = set()
        regular_seen = False
        allowed_pseudo = {b":method", b":scheme", b":authority", b":path", b":protocol"}
        host_values: list[bytes] = []
        for name, value in headers:
            if any(65 <= byte <= 90 for byte in name):
                raise ProtocolError("uppercase header field name forbidden in HTTP/2")
            self._validate_field_value(value)
            if name.startswith(b":"):
                if regular_seen:
                    raise ProtocolError("pseudo-header after regular header")
                if name not in allowed_pseudo:
                    raise ProtocolError("invalid request pseudo-header")
                if name in pseudo_seen:
                    raise ProtocolError("duplicate pseudo-header")
                pseudo_seen.add(name)
            else:
                regular_seen = True
                if name in {b"connection", b"upgrade", b"proxy-connection", b"transfer-encoding"}:
                    raise ProtocolError("connection-specific header forbidden in HTTP/2")
                if name == b"te" and value.lower() != b"trailers":
                    raise ProtocolError("invalid TE header for HTTP/2")
                if name == b"host":
                    host_values.append(value)
        if b":method" not in pseudo_seen:
            raise ProtocolError("missing :method pseudo-header")
        pseudo_headers = {name: value for name, value in headers if name.startswith(b":")}
        method = pseudo_headers.get(b":method", b"GET")
        protocol = pseudo_headers.get(b":protocol")
        authority = pseudo_headers.get(b":authority")
        if authority is not None and b"@" in authority:
            raise ProtocolError("userinfo is forbidden in :authority")
        if host_values:
            normalized_hosts = {value.lower() for value in host_values}
            if len(normalized_hosts) != 1:
                raise ProtocolError("conflicting host header values")
            if authority is not None and next(iter(normalized_hosts)) != authority.lower():
                raise ProtocolError("host header must match :authority")
        if protocol is not None:
            if method != b"CONNECT":
                raise ProtocolError("extended CONNECT requires CONNECT method")
            if self.state.local_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL, 0) != 1:
                raise ProtocolError("extended CONNECT not enabled")
            if b":scheme" not in pseudo_seen or b":path" not in pseudo_seen or b":authority" not in pseudo_seen:
                raise ProtocolError("extended CONNECT missing required pseudo-headers")
            return
        if method == b"CONNECT":
            if b":authority" not in pseudo_seen:
                raise ProtocolError("CONNECT missing :authority pseudo-header")
            if b":scheme" in pseudo_seen or b":path" in pseudo_seen:
                raise ProtocolError("CONNECT must not include :scheme or :path pseudo-headers")
            return
        if b":scheme" not in pseudo_seen or b":path" not in pseudo_seen:
            raise ProtocolError("missing required request pseudo-header")


    def _build_request(self, state: H2StreamState) -> ParsedRequest:
        self._validate_request_headers(state.headers)
        pseudo = {k: v for k, v in state.headers if k.startswith(b":")}
        headers = [(k, v) for k, v in state.headers if not k.startswith(b":")]
        method = pseudo.get(b":method", b"GET").decode("ascii", "strict")
        if state.expected_content_length is not None:
            observed = len(state.body)
            if observed > state.expected_content_length:
                raise ProtocolError("request body exceeds content-length")
            if state.end_stream_received and observed != state.expected_content_length:
                raise ProtocolError("request body does not match content-length")
        if method.upper() == "CONNECT" and pseudo.get(b":protocol") != b"websocket":
            target = pseudo.get(b":authority", b"").decode("ascii", "strict")
            path = target
            raw_path = target.encode("ascii", "strict")
            query_string = b""
        else:
            target_bytes = pseudo.get(b":path", b"")
            if not target_bytes:
                raise ProtocolError("empty :path pseudo-header")
            target = target_bytes.decode("ascii", "strict")
            split = urlsplit(target)
            if not split.path:
                raise ProtocolError("malformed request target")
            path = split.path
            raw_path = path.encode("utf-8")
            query_string = split.query.encode("ascii")
        return ParsedRequest(
            method=method,
            target=target,
            path=path,
            raw_path=raw_path,
            query_string=query_string,
            http_version="2",
            headers=headers,
            body=state.body,
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=False,
        )

