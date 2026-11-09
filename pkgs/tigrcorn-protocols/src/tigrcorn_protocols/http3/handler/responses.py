from __future__ import annotations

from .imports import *

class HTTP3ResponsesMixin:
    def _build_http3_response_datagrams_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
        *,
        end_stream: bool,
    ) -> list[bytes]:
        response_headers = apply_response_header_policy(
            strip_connection_specific_headers(headers),
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
            alt_svc_values=configured_alt_svc_values(self.config, request_http_version='3'),
        )
        header_block = session.h3.encode_headers(
            stream_id,
            [(b':status', str(status).encode('ascii')), *response_headers],
        )
        payload = bytearray(encode_frame(FRAME_HEADERS, header_block))
        if body:
            payload.extend(encode_frame(FRAME_DATA, body))
        return [*self._flush_qpack_streams(session), *session.quic.send_stream_data_packets(stream_id, bytes(payload), fin=end_stream)]

    async def _send_http3_streamed_response_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body_segments: list,
        trailers: list[tuple[bytes, bytes]],
        informational: list[tuple[int, list[tuple[bytes, bytes]]]],
        endpoint: UDPEndpoint,
    ) -> None:
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        for interim_status, interim_headers in informational:
            interim_header_block = session.h3.encode_headers(
                stream_id,
                [(b':status', str(interim_status).encode('ascii')), *sanitize_early_hints_headers(interim_headers)],
            )
            outbound = [*self._flush_qpack_streams(session), *session.quic.send_stream_data_packets(stream_id, encode_frame(FRAME_HEADERS, interim_header_block), fin=False)]
            self._queue_session_outbound_locked(session, outbound, endpoint)
        has_body = response_body_segments_have_bytes(body_segments)
        response_headers = apply_response_header_policy(
            strip_connection_specific_headers(headers),
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
            alt_svc_values=configured_alt_svc_values(self.config, request_http_version='3'),
        )
        header_block = session.h3.encode_headers(stream_id, [(b':status', str(status).encode('ascii')), *response_headers])
        outbound = [*self._flush_qpack_streams(session), *session.quic.send_stream_data_packets(stream_id, encode_frame(FRAME_HEADERS, header_block), fin=(not has_body and not trailers))]
        self._queue_session_outbound_locked(session, outbound, endpoint)
        if not has_body and not trailers:
            return
        if has_body:
            chunk_size = max(1024, int(self.listener.max_datagram_size) - 256)
            async for chunk in iter_response_body_segments(body_segments, chunk_size=chunk_size):
                outbound = self._build_http3_data_datagrams_locked(session, stream_id, chunk, end_stream=False)
                self._queue_session_outbound_locked(session, outbound, endpoint)
        if trailers:
            trailer_block = session.h3.encode_headers(stream_id, list(trailers))
            outbound = [*self._flush_qpack_streams(session), *session.quic.send_stream_data_packets(stream_id, encode_frame(FRAME_HEADERS, trailer_block), fin=True)]
        else:
            outbound = self._build_http3_data_datagrams_locked(session, stream_id, b'', end_stream=True)
        self._queue_session_outbound_locked(session, outbound, endpoint)

    def _build_http3_data_datagrams_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        data: bytes,
        *,
        end_stream: bool,
    ) -> list[bytes]:
        payload = encode_frame(FRAME_DATA, data) if data else b''
        return [*self._flush_qpack_streams(session), *session.quic.send_stream_data_packets(stream_id, payload, fin=end_stream)]
