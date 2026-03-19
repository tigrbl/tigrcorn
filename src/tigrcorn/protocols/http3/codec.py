from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from tigrcorn.errors import ProtocolError
from tigrcorn.utils.bytes import decode_quic_varint, encode_quic_varint

FRAME_DATA = 0x0
FRAME_HEADERS = 0x1
FRAME_CANCEL_PUSH = 0x3
FRAME_SETTINGS = 0x4
FRAME_PUSH_PROMISE = 0x5
FRAME_GOAWAY = 0x7
FRAME_MAX_PUSH_ID = 0xD
STREAM_TYPE_CONTROL = 0x00
SETTING_ENABLE_CONNECT_PROTOCOL = 0x08

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


def is_reserved_setting(identifier: int) -> bool:
    return identifier in HTTP3_RESERVED_SETTINGS



def is_reserved_frame_type(frame_type: int) -> bool:
    return frame_type in HTTP3_RESERVED_FRAME_TYPES



def is_grease_identifier(identifier: int) -> bool:
    return identifier >= 0x21 and (identifier - 0x21) % 0x1F == 0


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
