from __future__ import annotations

from dataclasses import dataclass

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_quic_varint
from tigrcorn_protocols.http3.codec import (
    FRAME_CANCEL_PUSH, FRAME_DATA, FRAME_GOAWAY, FRAME_HEADERS, FRAME_MAX_PUSH_ID,
    FRAME_PUSH_PROMISE, FRAME_SETTINGS, H3_EXCESSIVE_LOAD, H3_FRAME_ERROR,
    H3_FRAME_UNEXPECTED, H3_GENERAL_PROTOCOL_ERROR, H3_ID_ERROR, H3_MESSAGE_ERROR,
    H3_REQUEST_INCOMPLETE, HTTP3ConnectionError, HTTP3StreamError,
    QPACK_DECOMPRESSION_FAILED, decode_frame, encode_frame,
)
from tigrcorn_protocols.http3.qpack import (
    QpackBlocked, QpackDecoder, QpackDecompressionFailed, QpackEncoder,
    decode_field_section, encode_field_section,
)
from tigrcorn_protocols.http3.state import (
    HTTP3BlockedSection, HTTP3ConnectionState, HTTP3PushPromiseState,
    HTTP3RequestPhase_DATA, HTTP3RequestPhase_INITIAL, HTTP3RequestPhase_TRAILERS,
    HTTP3RequestState,
)
from .constants import DEFAULT_HTTP3_REQUEST_PARSE_BUFFER_LIMIT, SETTING_MAX_FIELD_SECTION_SIZE

_REQUEST_STATE_INITIAL = HTTP3RequestPhase_INITIAL
_REQUEST_STATE_DATA = HTTP3RequestPhase_DATA
_REQUEST_STATE_TRAILERS = HTTP3RequestPhase_TRAILERS


def _header_section_size(headers: list[tuple[bytes, bytes]]) -> int:
    return sum(len(name) + len(value) + 32 for name, value in headers)



def _parse_content_length(headers: list[tuple[bytes, bytes]], *, stream_id: int) -> int | None:
    values: list[bytes] = []
    for name, value in headers:
        if name.lower() != b'content-length':
            continue
        for part in value.split(b','):
            values.append(part.strip())
    if not values:
        return None
    parsed: int | None = None
    for value in values:
        if not value or not value.isdigit():
            raise HTTP3StreamError('invalid content-length header', error_code=H3_MESSAGE_ERROR, stream_id=stream_id)
        current = int(value)
        if parsed is None:
            parsed = current
            continue
        if parsed != current:
            raise HTTP3StreamError('conflicting content-length values', error_code=H3_MESSAGE_ERROR, stream_id=stream_id)
    return parsed


def _extract_status_code(headers: list[tuple[bytes, bytes]]) -> int | None:
    for name, value in headers:
        if name != b':status':
            continue
        if not value.isdigit():
            return None
        return int(value)
    return None


def _control_sender_is_client(stream_id: int) -> bool:
    return (stream_id & 0x01) == 0


@dataclass(slots=True)
class HTTP3RequestStream:
    state: HTTP3RequestState
    qpack_encoder: QpackEncoder | None = None
    qpack_decoder: QpackDecoder | None = None
    connection_state: HTTP3ConnectionState | None = None
    role: str | None = None
    parse_buffer_limit: int = DEFAULT_HTTP3_REQUEST_PARSE_BUFFER_LIMIT

    def encode_request(self, headers: list[tuple[bytes, bytes]], body: bytes = b'') -> bytes:
        raw = bytearray()
        if self.qpack_encoder is not None:
            header_block = self.qpack_encoder.encode_field_section(headers, stream_id=self.state.stream_id)
        else:
            header_block = encode_field_section(headers)
        raw.extend(encode_frame(FRAME_HEADERS, header_block))
        if body:
            raw.extend(encode_frame(FRAME_DATA, body))
        return bytes(raw)

    def _max_field_section_size(self) -> int | None:
        if self.connection_state is None:
            return None
        limit = self.connection_state.local_settings.get(SETTING_MAX_FIELD_SECTION_SIZE)
        if limit is None or limit <= 0:
            return None
        return limit

    def _decode_field_section_payload(self, payload: bytes) -> list[tuple[bytes, bytes]]:
        if self.qpack_decoder is None:
            return decode_field_section(payload)
        try:
            field_section = self.qpack_decoder.decode_field_section(payload, stream_id=self.state.stream_id)
        except QpackBlocked as exc:
            raise exc
        except QpackDecompressionFailed as exc:
            raise HTTP3ConnectionError('invalid HTTP/3 field section', error_code=QPACK_DECOMPRESSION_FAILED) from exc
        except ProtocolError as exc:
            raise HTTP3ConnectionError('invalid HTTP/3 field section', error_code=QPACK_DECOMPRESSION_FAILED) from exc
        return field_section.headers

    def _queue_blocked_section(self, *, kind: str, payload: bytes, push_id: int | None = None) -> None:
        self.state.blocked_header_sections.append(HTTP3BlockedSection(kind=kind, payload=payload, push_id=push_id))

    def _enforce_parse_buffer_limit(self) -> None:
        if self.parse_buffer_limit <= 0:
            return
        observed = len(self.state.parse_buffer)
        if observed <= self.parse_buffer_limit:
            return
        self.abandon()
        raise HTTP3StreamError(
            'HTTP/3 request stream parse buffer limit exceeded',
            error_code=H3_EXCESSIVE_LOAD,
            stream_id=self.state.stream_id,
        )

    def _enforce_field_section_size(self, headers: list[tuple[bytes, bytes]]) -> None:
        limit = self._max_field_section_size()
        if limit is None:
            return
        if _header_section_size(headers) > limit:
            raise HTTP3StreamError(
                'HTTP/3 field section exceeds advertised size',
                error_code=H3_MESSAGE_ERROR,
                stream_id=self.state.stream_id,
            )

    def _apply_initial_headers(self, headers: list[tuple[bytes, bytes]]) -> None:
        self._enforce_field_section_size(headers)
        status_code = _extract_status_code(headers)
        if self.role == 'client' and status_code is not None and 100 <= status_code < 200:
            self.state.informational_headers.append(list(headers))
            return
        self.state.headers.extend(headers)
        self.state.received_initial_headers = True
        self.state.phase = _REQUEST_STATE_DATA
        content_length = _parse_content_length(headers, stream_id=self.state.stream_id)
        if content_length is not None:
            self.state.expected_content_length = content_length
            if self.state.received_content_length > content_length:
                raise HTTP3StreamError(
                    'request body exceeds content-length',
                    error_code=H3_MESSAGE_ERROR,
                    stream_id=self.state.stream_id,
                )

    def _apply_trailers(self, headers: list[tuple[bytes, bytes]]) -> None:
        self._enforce_field_section_size(headers)
        for name, _value in headers:
            if name.startswith(b':'):
                raise HTTP3StreamError(
                    'pseudo-header field in trailer section',
                    error_code=H3_MESSAGE_ERROR,
                    stream_id=self.state.stream_id,
                )
        self.state.trailers.extend(headers)
        self.state.received_trailers = True
        self.state.phase = _REQUEST_STATE_TRAILERS

    def _store_push_promise(self, push_id: int, headers: list[tuple[bytes, bytes]]) -> None:
        connection_state = self.connection_state
        if connection_state is None:
            connection_state = HTTP3ConnectionState()
            self.connection_state = connection_state
        max_push_id = connection_state.local_max_push_id
        if max_push_id is None or push_id > max_push_id:
            raise HTTP3ConnectionError('PUSH_PROMISE exceeds advertised MAX_PUSH_ID', error_code=H3_ID_ERROR)
        existing = connection_state.promised_pushes.get(push_id)
        if existing is not None:
            if existing.headers != headers:
                raise HTTP3ConnectionError(
                    'inconsistent duplicate PUSH_PROMISE field section',
                    error_code=H3_GENERAL_PROTOCOL_ERROR,
                )
            existing.request_stream_ids.add(self.state.stream_id)
            self.state.push_promises[push_id] = existing
            return
        promise = HTTP3PushPromiseState(push_id=push_id, headers=list(headers), request_stream_ids={self.state.stream_id})
        connection_state.promised_pushes[push_id] = promise
        self.state.push_promises[push_id] = promise

    def _apply_blocked_section(self, section: HTTP3BlockedSection) -> None:
        try:
            headers = self._decode_field_section_payload(section.payload)
        except QpackBlocked:
            raise
        if section.kind == 'initial':
            self._apply_initial_headers(headers)
            return
        if section.kind == 'trailers':
            self._apply_trailers(headers)
            return
        if section.kind == 'push':
            assert section.push_id is not None
            self._store_push_promise(section.push_id, headers)
            return
        raise HTTP3ConnectionError('unknown blocked header section kind', error_code=H3_GENERAL_PROTOCOL_ERROR)

    def _decode_or_block(self, *, kind: str, payload: bytes, push_id: int | None = None) -> bool:
        try:
            headers = self._decode_field_section_payload(payload)
        except QpackBlocked:
            self._queue_blocked_section(kind=kind, payload=payload, push_id=push_id)
            return True
        if kind == 'initial':
            self._apply_initial_headers(headers)
            return False
        if kind == 'trailers':
            self._apply_trailers(headers)
            return False
        if kind == 'push':
            assert push_id is not None
            self._store_push_promise(push_id, headers)
            return False
        raise HTTP3ConnectionError('unknown header section kind', error_code=H3_GENERAL_PROTOCOL_ERROR)

    def _handle_headers_frame(self, payload: bytes) -> bool:
        if self.state.phase == _REQUEST_STATE_INITIAL:
            return self._decode_or_block(kind='initial', payload=payload)
        if self.state.phase == _REQUEST_STATE_DATA:
            return self._decode_or_block(kind='trailers', payload=payload)
        raise HTTP3ConnectionError('HEADERS after trailer section', error_code=H3_FRAME_UNEXPECTED)

    def _handle_data_frame(self, payload: bytes) -> bool:
        if self.state.phase == _REQUEST_STATE_INITIAL:
            raise HTTP3ConnectionError('DATA frame before initial HEADERS', error_code=H3_FRAME_UNEXPECTED)
        if self.state.phase == _REQUEST_STATE_TRAILERS:
            raise HTTP3ConnectionError('DATA frame after trailing HEADERS', error_code=H3_FRAME_UNEXPECTED)
        self.state.body_parts.append(payload)
        self.state.received_content_length += len(payload)
        expected = self.state.expected_content_length
        if expected is not None and self.state.received_content_length > expected:
            raise HTTP3StreamError(
                'request body exceeds content-length',
                error_code=H3_MESSAGE_ERROR,
                stream_id=self.state.stream_id,
            )
        return False

    def _handle_push_promise_frame(self, payload: bytes) -> bool:
        if self.role == 'server':
            raise HTTP3ConnectionError('server received PUSH_PROMISE on request stream', error_code=H3_FRAME_UNEXPECTED)
        try:
            push_id, offset = decode_quic_varint(payload, 0)
        except ProtocolError as exc:
            raise HTTP3ConnectionError('malformed PUSH_PROMISE frame payload', error_code=H3_FRAME_ERROR) from exc
        field_section = payload[offset:]
        return self._decode_or_block(kind='push', payload=field_section, push_id=push_id)

    def _handle_frame(self, frame_type: int, payload: bytes) -> bool:
        if frame_type == FRAME_HEADERS:
            return self._handle_headers_frame(payload)
        if frame_type == FRAME_DATA:
            return self._handle_data_frame(payload)
        if frame_type == FRAME_PUSH_PROMISE:
            return self._handle_push_promise_frame(payload)
        if frame_type in {FRAME_CANCEL_PUSH, FRAME_SETTINGS, FRAME_GOAWAY, FRAME_MAX_PUSH_ID}:
            raise HTTP3ConnectionError('frame not permitted on request stream', error_code=H3_FRAME_UNEXPECTED)
        return False

    def _process_parse_buffer(self) -> None:
        self._enforce_parse_buffer_limit()
        offset = 0
        data = bytes(self.state.parse_buffer)
        while offset < len(data):
            try:
                frame, next_offset = decode_frame(data, offset)
            except ProtocolError:
                break
            offset = next_offset
            blocked = self._handle_frame(frame.frame_type, frame.payload)
            if blocked:
                break
        remaining = data[offset:]
        self.state.parse_buffer.clear()
        self.state.parse_buffer.extend(remaining)
        self._enforce_parse_buffer_limit()

    def _finalize_complete_message(self) -> None:
        if not self.state.ended:
            return
        if self.state.blocked_header_sections:
            return
        if self.state.parse_buffer:
            raise HTTP3StreamError(
                'request stream ended with incomplete frame',
                error_code=H3_REQUEST_INCOMPLETE,
                stream_id=self.state.stream_id,
            )
        if not self.state.received_initial_headers:
            raise HTTP3StreamError(
                'request stream ended before initial HEADERS',
                error_code=H3_REQUEST_INCOMPLETE,
                stream_id=self.state.stream_id,
            )
        expected = self.state.expected_content_length
        if expected is not None and self.state.received_content_length != expected:
            raise HTTP3StreamError(
                'content-length does not match DATA frame lengths',
                error_code=H3_MESSAGE_ERROR,
                stream_id=self.state.stream_id,
            )

    def retry_blocked(self) -> bool:
        if self.qpack_decoder is None or not self.state.blocked_header_sections:
            self._finalize_complete_message()
            return False
        progressed = False
        remaining: list[HTTP3BlockedSection] = []
        for section in self.state.blocked_header_sections:
            try:
                self._apply_blocked_section(section)
            except QpackBlocked:
                remaining.append(section)
                continue
            progressed = True
        self.state.blocked_header_sections = remaining
        if progressed and not self.state.blocked_header_sections and self.state.parse_buffer:
            self._process_parse_buffer()
        self._finalize_complete_message()
        return progressed

    def abandon(self) -> None:
        if self.state.abandoned:
            return
        self.state.abandoned = True
        if self.qpack_decoder is not None and self.state.blocked_header_sections:
            self.qpack_decoder.cancel_stream(self.state.stream_id)
        self.state.blocked_header_sections.clear()
        self.state.parse_buffer.clear()

    def receive(self, payload: bytes, *, fin: bool = False) -> HTTP3RequestState:
        if self.state.abandoned:
            return self.state
        self.state.parse_buffer.extend(payload)
        self._enforce_parse_buffer_limit()
        if fin:
            self.state.ended = True
        self._process_parse_buffer()
        self.retry_blocked()
        self._finalize_complete_message()
        return self.state

