from __future__ import annotations

from dataclasses import dataclass, field

from tigrcorn_core.errors import ProtocolError
from tigrcorn_protocols.http3.codec import (
    FRAME_CANCEL_PUSH,
    FRAME_DATA,
    FRAME_GOAWAY,
    FRAME_HEADERS,
    FRAME_MAX_PUSH_ID,
    FRAME_PUSH_PROMISE,
    FRAME_SETTINGS,
    H3_CLOSED_CRITICAL_STREAM,
    H3_FRAME_ERROR,
    H3_FRAME_UNEXPECTED,
    H3_GENERAL_PROTOCOL_ERROR,
    H3_ID_ERROR,
    H3_MESSAGE_ERROR,
    H3_MISSING_SETTINGS,
    H3_REQUEST_INCOMPLETE,
    H3_REQUEST_REJECTED,
    H3_SETTINGS_ERROR,
    H3_STREAM_CREATION_ERROR,
    HTTP3ConnectionError,
    HTTP3StreamError,
    QPACK_DECODER_STREAM_ERROR,
    QPACK_DECOMPRESSION_FAILED,
    QPACK_ENCODER_STREAM_ERROR,
    STREAM_TYPE_CONTROL,
    decode_frame,
    decode_settings,
    decode_single_varint,
    encode_frame,
    encode_settings,
)
from tigrcorn_protocols.http3.qpack import (
    QpackBlocked,
    QpackDecoder,
    QpackDecoderStreamError,
    QpackDecompressionFailed,
    QpackEncoder,
    QpackEncoderStreamError,
    decode_field_section,
    encode_field_section,
)
from tigrcorn_protocols.http3.state import (
    HTTP3BlockedSection,
    HTTP3ConnectionState,
    HTTP3PushPromiseState,
    HTTP3RequestPhase_DATA,
    HTTP3RequestPhase_INITIAL,
    HTTP3RequestPhase_TRAILERS,
    HTTP3RequestState,
    HTTP3UniStreamState,
)
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint

HTTP3_STREAM_PRESSURE_CERTIFICATION_SCOPES: tuple[str, ...] = ('stream-level-backpressure', 'connection-level-backpressure', 'goaway-pressure')


def supported_http3_stream_pressure_certification_scopes() -> tuple[str, ...]:
    return HTTP3_STREAM_PRESSURE_CERTIFICATION_SCOPES

STREAM_TYPE_PUSH = 0x01
STREAM_TYPE_QPACK_ENCODER = 0x02
STREAM_TYPE_QPACK_DECODER = 0x03
SETTING_QPACK_MAX_TABLE_CAPACITY = 0x01
SETTING_MAX_FIELD_SECTION_SIZE = 0x06
SETTING_QPACK_BLOCKED_STREAMS = 0x07
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
        if fin:
            self.state.ended = True
        self._process_parse_buffer()
        self.retry_blocked()
        self._finalize_complete_message()
        return self.state


@dataclass(slots=True)
class HTTP3ConnectionCore:
    state: HTTP3ConnectionState = field(default_factory=HTTP3ConnectionState)
    role: str | None = None
    requests: dict[int, HTTP3RequestStream] = field(default_factory=dict)
    qpack_encoder: QpackEncoder = field(default_factory=QpackEncoder)
    qpack_decoder: QpackDecoder = field(default_factory=QpackDecoder)

    def _update_request_codecs(self) -> None:
        for request in self.requests.values():
            request.qpack_encoder = self.qpack_encoder
            request.qpack_decoder = self.qpack_decoder
            request.connection_state = self.state
            request.role = self.role

    def _configure_local_decoder(self) -> None:
        capacity = self.state.local_settings.get(SETTING_QPACK_MAX_TABLE_CAPACITY, 0)
        blocked = self.state.local_settings.get(SETTING_QPACK_BLOCKED_STREAMS, 0)
        self.qpack_decoder = QpackDecoder(max_table_capacity=capacity, blocked_streams=blocked)
        self._update_request_codecs()

    def _configure_remote_encoder(self) -> None:
        capacity = self.state.remote_settings.get(SETTING_QPACK_MAX_TABLE_CAPACITY, 0)
        blocked = self.state.remote_settings.get(SETTING_QPACK_BLOCKED_STREAMS, 0)
        self.qpack_encoder = QpackEncoder(max_table_capacity=capacity, blocked_streams=blocked)
        self._update_request_codecs()

    def encode_control_stream(self, settings: dict[int, int]) -> bytes:
        if self.state.control_stream_opened:
            raise ProtocolError('HTTP/3 endpoints must not open multiple local control streams')
        self.state.local_settings.update(settings)
        self.state.control_stream_opened = True
        self._configure_local_decoder()
        return encode_quic_varint(STREAM_TYPE_CONTROL) + encode_frame(FRAME_SETTINGS, encode_settings(settings))

    def encode_goaway(self, identifier: int) -> bytes:
        if self.state.local_goaway_id is not None and identifier > self.state.local_goaway_id:
            raise ProtocolError('HTTP/3 GOAWAY identifier must not increase')
        self.state.local_goaway_id = identifier
        self.state.goaway_stream_id = identifier
        return encode_frame(FRAME_GOAWAY, encode_quic_varint(identifier))

    def encode_cancel_push(self, push_id: int) -> bytes:
        return encode_frame(FRAME_CANCEL_PUSH, encode_quic_varint(push_id))

    def encode_max_push_id(self, push_id: int) -> bytes:
        if self.state.local_max_push_id is not None and push_id < self.state.local_max_push_id:
            raise ProtocolError('HTTP/3 MAX_PUSH_ID must not decrease')
        self.state.local_max_push_id = push_id
        return encode_frame(FRAME_MAX_PUSH_ID, encode_quic_varint(push_id))

    def encode_push_promise(self, stream_id: int, push_id: int, headers: list[tuple[bytes, bytes]]) -> bytes:
        if self.qpack_encoder is not None:
            header_block = self.qpack_encoder.encode_field_section(headers, stream_id=stream_id)
        else:
            header_block = encode_field_section(headers)
        payload = encode_quic_varint(push_id) + header_block
        return encode_frame(FRAME_PUSH_PROMISE, payload)

    def get_request(self, stream_id: int) -> HTTP3RequestStream:
        return self.requests.setdefault(
            stream_id,
            HTTP3RequestStream(
                state=HTTP3RequestState(stream_id=stream_id),
                qpack_encoder=self.qpack_encoder,
                qpack_decoder=self.qpack_decoder,
                connection_state=self.state,
                role=self.role,
            ),
        )

    def abandon_stream(self, stream_id: int) -> None:
        request = self.requests.get(stream_id)
        if request is None:
            return
        request.abandon()

    def encode_headers(self, stream_id: int, headers: list[tuple[bytes, bytes]]) -> bytes:
        return self.qpack_encoder.encode_field_section(headers, stream_id=stream_id)

    def take_encoder_stream_data(self) -> bytes:
        return self.qpack_encoder.take_encoder_stream_data()

    def take_decoder_stream_data(self) -> bytes:
        return self.qpack_decoder.take_decoder_stream_data()

    def ready_request_states(self) -> list[HTTP3RequestState]:
        return [request.state for request in self.requests.values() if request.state.ready]

    def _retry_blocked_requests(self) -> None:
        for request in self.requests.values():
            request.retry_blocked()

    def _process_goaway(self, identifier: int, *, sender_is_client: bool) -> None:
        direction = 'client' if sender_is_client else 'server'
        previous = self.state.peer_goaway_id
        if previous is not None and identifier > previous:
            raise HTTP3ConnectionError('GOAWAY identifier increased', error_code=H3_ID_ERROR)
        if not sender_is_client and (identifier & 0x03) != 0:
            raise HTTP3ConnectionError('server GOAWAY identifier must be a client-initiated bidirectional stream ID', error_code=H3_ID_ERROR)
        self.state.peer_goaway_direction = direction
        self.state.peer_goaway_id = identifier
        self.state.goaway_stream_id = identifier

    def _process_cancel_push(self, push_id: int, *, sender_is_client: bool) -> None:
        if sender_is_client:
            max_push_id = self.state.peer_max_push_id
            if max_push_id is not None and push_id > max_push_id:
                raise HTTP3ConnectionError('CANCEL_PUSH exceeds peer MAX_PUSH_ID', error_code=H3_ID_ERROR)
            if push_id not in self.state.promised_pushes:
                raise HTTP3ConnectionError('CANCEL_PUSH references unknown promised push', error_code=H3_ID_ERROR)
        else:
            local_max_push_id = self.state.local_max_push_id
            if local_max_push_id is not None and push_id > local_max_push_id:
                raise HTTP3ConnectionError('CANCEL_PUSH exceeds advertised MAX_PUSH_ID', error_code=H3_ID_ERROR)
        self.state.cancelled_push_ids.add(push_id)

    def _process_max_push_id(self, push_id: int, *, sender_is_client: bool) -> None:
        if not sender_is_client:
            raise HTTP3ConnectionError('server sent MAX_PUSH_ID', error_code=H3_FRAME_UNEXPECTED)
        if self.state.peer_max_push_id is not None and push_id < self.state.peer_max_push_id:
            raise HTTP3ConnectionError('MAX_PUSH_ID must not decrease', error_code=H3_ID_ERROR)
        self.state.peer_max_push_id = push_id

    def _receive_control_frame(self, frame_type: int, payload: bytes, *, stream_id: int) -> None:
        sender_is_client = _control_sender_is_client(stream_id)
        if frame_type == FRAME_SETTINGS:
            raise HTTP3ConnectionError('duplicate HTTP/3 SETTINGS frame', error_code=H3_FRAME_UNEXPECTED)
        if frame_type == FRAME_GOAWAY:
            identifier = decode_single_varint(payload, context='GOAWAY')
            self._process_goaway(identifier, sender_is_client=sender_is_client)
            return
        if frame_type == FRAME_CANCEL_PUSH:
            push_id = decode_single_varint(payload, context='CANCEL_PUSH')
            self._process_cancel_push(push_id, sender_is_client=sender_is_client)
            return
        if frame_type == FRAME_MAX_PUSH_ID:
            push_id = decode_single_varint(payload, context='MAX_PUSH_ID')
            self._process_max_push_id(push_id, sender_is_client=sender_is_client)
            return
        if frame_type in {FRAME_PUSH_PROMISE, FRAME_HEADERS, FRAME_DATA}:
            raise HTTP3ConnectionError('frame not permitted on control stream', error_code=H3_FRAME_UNEXPECTED)
        # Unknown or reserved frame types are ignored after SETTINGS.

    def _receive_uni_stream(self, stream_id: int, payload: bytes, *, fin: bool = False) -> None:
        state = self.state.uni_streams.setdefault(stream_id, HTTP3UniStreamState(stream_id=stream_id))
        state.parse_buffer.extend(payload)
        offset = 0
        data = bytes(state.parse_buffer)
        if state.stream_type is None:
            try:
                state.stream_type, offset = decode_quic_varint(data, offset)
            except ProtocolError:
                if fin:
                    state.parse_buffer.clear()
                return
            if state.stream_type == STREAM_TYPE_CONTROL:
                if self.state.remote_control_stream_id is None:
                    self.state.remote_control_stream_id = stream_id
                elif self.state.remote_control_stream_id != stream_id:
                    raise HTTP3ConnectionError('peer opened more than one control stream', error_code=H3_STREAM_CREATION_ERROR)
            elif state.stream_type == STREAM_TYPE_QPACK_ENCODER:
                if self.state.remote_qpack_encoder_stream_id is None:
                    self.state.remote_qpack_encoder_stream_id = stream_id
                elif self.state.remote_qpack_encoder_stream_id != stream_id:
                    raise HTTP3ConnectionError('peer opened more than one QPACK encoder stream', error_code=H3_STREAM_CREATION_ERROR)
            elif state.stream_type == STREAM_TYPE_QPACK_DECODER:
                if self.state.remote_qpack_decoder_stream_id is None:
                    self.state.remote_qpack_decoder_stream_id = stream_id
                elif self.state.remote_qpack_decoder_stream_id != stream_id:
                    raise HTTP3ConnectionError('peer opened more than one QPACK decoder stream', error_code=H3_STREAM_CREATION_ERROR)
            elif state.stream_type == STREAM_TYPE_PUSH:
                if _control_sender_is_client(stream_id):
                    raise HTTP3ConnectionError('client-initiated push stream is forbidden', error_code=H3_STREAM_CREATION_ERROR)
                self.state.remote_push_stream_ids.add(stream_id)
            else:
                state.discard_stream = True
        if state.stream_type == STREAM_TYPE_CONTROL:
            if fin:
                raise HTTP3ConnectionError('HTTP/3 control stream closed', error_code=H3_CLOSED_CRITICAL_STREAM)
            while offset < len(data):
                try:
                    frame, next_offset = decode_frame(data, offset)
                except ProtocolError:
                    break
                offset = next_offset
                if not state.settings_received:
                    if frame.frame_type != FRAME_SETTINGS:
                        raise HTTP3ConnectionError('control stream must begin with SETTINGS', error_code=H3_MISSING_SETTINGS)
                    state.settings_received = True
                    try:
                        self.state.remote_settings.update(decode_settings(frame.payload))
                    except HTTP3ConnectionError:
                        raise
                    except ProtocolError as exc:
                        raise HTTP3ConnectionError('invalid HTTP/3 SETTINGS payload', error_code=H3_SETTINGS_ERROR) from exc
                    self._configure_remote_encoder()
                    continue
                self._receive_control_frame(frame.frame_type, frame.payload, stream_id=stream_id)
            remaining = data[offset:]
            state.parse_buffer.clear()
            state.parse_buffer.extend(remaining)
            return
        if state.stream_type == STREAM_TYPE_QPACK_ENCODER:
            if fin:
                raise HTTP3ConnectionError('HTTP/3 QPACK encoder stream closed', error_code=H3_CLOSED_CRITICAL_STREAM)
            try:
                self.qpack_decoder.receive_encoder_stream(data[offset:])
            except QpackEncoderStreamError as exc:
                raise HTTP3ConnectionError('invalid QPACK encoder stream data', error_code=QPACK_ENCODER_STREAM_ERROR) from exc
            except ProtocolError as exc:
                raise HTTP3ConnectionError('invalid QPACK encoder stream data', error_code=QPACK_ENCODER_STREAM_ERROR) from exc
            finally:
                state.parse_buffer.clear()
            self._retry_blocked_requests()
            return
        if state.stream_type == STREAM_TYPE_QPACK_DECODER:
            if fin:
                raise HTTP3ConnectionError('HTTP/3 QPACK decoder stream closed', error_code=H3_CLOSED_CRITICAL_STREAM)
            try:
                self.qpack_encoder.receive_decoder_stream(data[offset:])
            except QpackDecoderStreamError as exc:
                raise HTTP3ConnectionError('invalid QPACK decoder stream data', error_code=QPACK_DECODER_STREAM_ERROR) from exc
            except ProtocolError as exc:
                raise HTTP3ConnectionError('invalid QPACK decoder stream data', error_code=QPACK_DECODER_STREAM_ERROR) from exc
            finally:
                state.parse_buffer.clear()
            return
        if state.stream_type == STREAM_TYPE_PUSH:
            if state.push_id is None:
                try:
                    state.push_id, offset = decode_quic_varint(data, offset)
                except ProtocolError:
                    if fin:
                        state.parse_buffer.clear()
                    return
                for other in self.state.uni_streams.values():
                    if other is state or other.stream_type != STREAM_TYPE_PUSH or other.push_id is None:
                        continue
                    if other.push_id == state.push_id:
                        raise HTTP3ConnectionError('push stream reused push ID', error_code=H3_ID_ERROR)
            state.parse_buffer.clear()
            return
        state.parse_buffer.clear()

    def receive_stream_data(self, stream_id: int, payload: bytes, *, fin: bool = False) -> HTTP3RequestState | None:
        if stream_id & 0x02:
            self._receive_uni_stream(stream_id, payload, fin=fin)
            return None
        if self.role == 'server' and self.state.local_goaway_id is not None and stream_id >= self.state.local_goaway_id and stream_id not in self.requests:
            raise HTTP3StreamError('request rejected after GOAWAY', error_code=H3_REQUEST_REJECTED, stream_id=stream_id)
        return self.get_request(stream_id).receive(payload, fin=fin)
