from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint

FRAME_DATA = 0x0
FRAME_HEADERS = 0x1
FRAME_CANCEL_PUSH = 0x3
FRAME_SETTINGS = 0x4
FRAME_PUSH_PROMISE = 0x5
FRAME_GOAWAY = 0x7
FRAME_MAX_PUSH_ID = 0xD
FRAME_PRIORITY_UPDATE = 0xF0700
STREAM_TYPE_CONTROL = 0x00
STREAM_TYPE_PUSH = 0x01
STREAM_TYPE_QPACK_ENCODER = 0x02
STREAM_TYPE_QPACK_DECODER = 0x03
SETTING_QPACK_MAX_TABLE_CAPACITY = 0x01
SETTING_MAX_FIELD_SECTION_SIZE = 0x06
SETTING_QPACK_BLOCKED_STREAMS = 0x07
SETTING_ENABLE_CONNECT_PROTOCOL = 0x08
SETTING_H3_DATAGRAM = 0x33
SETTING_ENABLE_WEBTRANSPORT = 0x2B603742
SETTING_WT_MAX_SESSIONS = 0x14E9CD29

H3_DATAGRAM_ERROR = 0x33
H3_NO_ERROR = 0x0100
H3_GENERAL_PROTOCOL_ERROR = 0x0101
H3_INTERNAL_ERROR = 0x0102
H3_STREAM_CREATION_ERROR = 0x0103
H3_CLOSED_CRITICAL_STREAM = 0x0104
H3_FRAME_UNEXPECTED = 0x0105
H3_FRAME_ERROR = 0x0106
H3_EXCESSIVE_LOAD = 0x0107
H3_ID_ERROR = 0x0108
H3_SETTINGS_ERROR = 0x0109
H3_MISSING_SETTINGS = 0x010A
H3_REQUEST_REJECTED = 0x010B
H3_REQUEST_CANCELLED = 0x010C
H3_REQUEST_INCOMPLETE = 0x010D
H3_MESSAGE_ERROR = 0x010E
H3_CONNECT_ERROR = 0x010F
H3_VERSION_FALLBACK = 0x0110
QPACK_DECOMPRESSION_FAILED = 0x0200
QPACK_ENCODER_STREAM_ERROR = 0x0201
QPACK_DECODER_STREAM_ERROR = 0x0202

HTTP3_RESERVED_SETTINGS = frozenset({0x00, 0x02, 0x03, 0x04, 0x05})
HTTP3_RESERVED_FRAME_TYPES = frozenset({0x02, 0x06, 0x08, 0x09})

HTTP3_IANA_FRAME_TYPES = {
    "DATA": FRAME_DATA,
    "HEADERS": FRAME_HEADERS,
    "CANCEL_PUSH": FRAME_CANCEL_PUSH,
    "SETTINGS": FRAME_SETTINGS,
    "PUSH_PROMISE": FRAME_PUSH_PROMISE,
    "GOAWAY": FRAME_GOAWAY,
    "MAX_PUSH_ID": FRAME_MAX_PUSH_ID,
    "PRIORITY_UPDATE": FRAME_PRIORITY_UPDATE,
}

HTTP3_IANA_SETTINGS = {
    "SETTINGS_QPACK_MAX_TABLE_CAPACITY": SETTING_QPACK_MAX_TABLE_CAPACITY,
    "SETTINGS_MAX_FIELD_SECTION_SIZE": SETTING_MAX_FIELD_SECTION_SIZE,
    "SETTINGS_QPACK_BLOCKED_STREAMS": SETTING_QPACK_BLOCKED_STREAMS,
    "SETTINGS_ENABLE_CONNECT_PROTOCOL": SETTING_ENABLE_CONNECT_PROTOCOL,
    "SETTINGS_H3_DATAGRAM": SETTING_H3_DATAGRAM,
    "SETTINGS_WT_MAX_SESSIONS": SETTING_WT_MAX_SESSIONS,
}

HTTP3_IANA_ERROR_CODES = {
    "H3_DATAGRAM_ERROR": H3_DATAGRAM_ERROR,
    "H3_NO_ERROR": H3_NO_ERROR,
    "H3_GENERAL_PROTOCOL_ERROR": H3_GENERAL_PROTOCOL_ERROR,
    "H3_INTERNAL_ERROR": H3_INTERNAL_ERROR,
    "H3_STREAM_CREATION_ERROR": H3_STREAM_CREATION_ERROR,
    "H3_CLOSED_CRITICAL_STREAM": H3_CLOSED_CRITICAL_STREAM,
    "H3_FRAME_UNEXPECTED": H3_FRAME_UNEXPECTED,
    "H3_FRAME_ERROR": H3_FRAME_ERROR,
    "H3_EXCESSIVE_LOAD": H3_EXCESSIVE_LOAD,
    "H3_ID_ERROR": H3_ID_ERROR,
    "H3_SETTINGS_ERROR": H3_SETTINGS_ERROR,
    "H3_MISSING_SETTINGS": H3_MISSING_SETTINGS,
    "H3_REQUEST_REJECTED": H3_REQUEST_REJECTED,
    "H3_REQUEST_CANCELLED": H3_REQUEST_CANCELLED,
    "H3_REQUEST_INCOMPLETE": H3_REQUEST_INCOMPLETE,
    "H3_MESSAGE_ERROR": H3_MESSAGE_ERROR,
    "H3_CONNECT_ERROR": H3_CONNECT_ERROR,
    "H3_VERSION_FALLBACK": H3_VERSION_FALLBACK,
    "QPACK_DECOMPRESSION_FAILED": QPACK_DECOMPRESSION_FAILED,
    "QPACK_ENCODER_STREAM_ERROR": QPACK_ENCODER_STREAM_ERROR,
    "QPACK_DECODER_STREAM_ERROR": QPACK_DECODER_STREAM_ERROR,
}

HTTP3_IANA_STREAM_TYPES = {
    "CONTROL": STREAM_TYPE_CONTROL,
    "PUSH": STREAM_TYPE_PUSH,
    "QPACK_ENCODER": STREAM_TYPE_QPACK_ENCODER,
    "QPACK_DECODER": STREAM_TYPE_QPACK_DECODER,
}


def is_reserved_setting(identifier: int) -> bool:
    return identifier in HTTP3_RESERVED_SETTINGS



def is_reserved_frame_type(frame_type: int) -> bool:
    return frame_type in HTTP3_RESERVED_FRAME_TYPES



def is_grease_identifier(identifier: int) -> bool:
    return identifier >= 0x21 and (identifier - 0x21) % 0x1F == 0


def http3_iana_registry_snapshot() -> dict[str, dict[str, int]]:
    return {
        "frame_types": dict(HTTP3_IANA_FRAME_TYPES),
        "settings": dict(HTTP3_IANA_SETTINGS),
        "error_codes": dict(HTTP3_IANA_ERROR_CODES),
        "stream_types": dict(HTTP3_IANA_STREAM_TYPES),
    }


class HTTP3Error(ProtocolError):
    def __init__(self, message: str, *, error_code: int, stream_id: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.stream_id = stream_id


class HTTP3ConnectionError(HTTP3Error):
    pass


class HTTP3StreamError(HTTP3Error):
    pass


@dataclass(slots=True)
class HTTP3Frame:
    frame_type: int
    payload: bytes



def encode_frame(frame_type: int, payload: bytes = b'') -> bytes:
    return encode_quic_varint(frame_type) + encode_quic_varint(len(payload)) + payload



def decode_frame(data: bytes, offset: int = 0) -> tuple[HTTP3Frame, int]:
    frame_type, offset = decode_quic_varint(data, offset)
    length, offset = decode_quic_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise ProtocolError('truncated HTTP/3 frame payload')
    return HTTP3Frame(frame_type=frame_type, payload=data[offset:end]), end



def parse_frames(data: bytes) -> list[HTTP3Frame]:
    frames: list[HTTP3Frame] = []
    offset = 0
    while offset < len(data):
        frame, offset = decode_frame(data, offset)
        frames.append(frame)
    return frames



def encode_settings(settings: Mapping[int, int]) -> bytes:
    payload = bytearray()
    seen: set[int] = set()
    for key, value in settings.items():
        key_int = int(key)
        if key_int in seen:
            raise ProtocolError('duplicate HTTP/3 setting identifier')
        if is_reserved_setting(key_int):
            raise ProtocolError(f'reserved HTTP/3 setting identifier: {key_int:#x}')
        seen.add(key_int)
        payload.extend(encode_quic_varint(key_int))
        payload.extend(encode_quic_varint(int(value)))
    return bytes(payload)



def decode_settings(payload: bytes) -> dict[int, int]:
    settings: dict[int, int] = {}
    offset = 0
    while offset < len(payload):
        try:
            key, offset = decode_quic_varint(payload, offset)
            value, offset = decode_quic_varint(payload, offset)
        except ProtocolError as exc:
            raise HTTP3ConnectionError('malformed HTTP/3 SETTINGS payload', error_code=H3_SETTINGS_ERROR) from exc
        if key in settings:
            raise HTTP3ConnectionError('duplicate HTTP/3 setting', error_code=H3_SETTINGS_ERROR)
        if is_reserved_setting(key):
            raise HTTP3ConnectionError(f'reserved HTTP/3 setting received: {key:#x}', error_code=H3_SETTINGS_ERROR)
        settings[key] = value
    return settings



def decode_single_varint(payload: bytes, *, context: str) -> int:
    try:
        value, offset = decode_quic_varint(payload, 0)
    except ProtocolError as exc:
        raise HTTP3ConnectionError(f'malformed {context} frame payload', error_code=H3_FRAME_ERROR) from exc
    if offset != len(payload):
        raise HTTP3ConnectionError(f'invalid {context} frame size', error_code=H3_FRAME_ERROR)
    return value
