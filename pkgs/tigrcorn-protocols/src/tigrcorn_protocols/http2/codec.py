from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_u24, encode_u24, split_chunks

FRAME_DATA = 0x0
FRAME_HEADERS = 0x1
FRAME_PRIORITY = 0x2
FRAME_RST_STREAM = 0x3
FRAME_SETTINGS = 0x4
FRAME_PUSH_PROMISE = 0x5
FRAME_PING = 0x6
FRAME_GOAWAY = 0x7
FRAME_WINDOW_UPDATE = 0x8
FRAME_CONTINUATION = 0x9

H2_NO_ERROR = 0x0
H2_PROTOCOL_ERROR = 0x1
H2_INTERNAL_ERROR = 0x2
H2_FLOW_CONTROL_ERROR = 0x3
H2_SETTINGS_TIMEOUT = 0x4
H2_STREAM_CLOSED = 0x5
H2_FRAME_SIZE_ERROR = 0x6
H2_REFUSED_STREAM = 0x7
H2_CANCEL = 0x8
H2_COMPRESSION_ERROR = 0x9
H2_CONNECT_ERROR = 0xA
H2_ENHANCE_YOUR_CALM = 0xB
H2_INADEQUATE_SECURITY = 0xC
H2_HTTP_1_1_REQUIRED = 0xD

FLAG_ACK = 0x1
FLAG_END_STREAM = 0x1
FLAG_END_HEADERS = 0x4
FLAG_PADDED = 0x8
FLAG_PRIORITY = 0x20

SETTING_HEADER_TABLE_SIZE = 0x1
SETTING_ENABLE_PUSH = 0x2
SETTING_MAX_CONCURRENT_STREAMS = 0x3
SETTING_INITIAL_WINDOW_SIZE = 0x4
SETTING_MAX_FRAME_SIZE = 0x5
SETTING_MAX_HEADER_LIST_SIZE = 0x6
SETTING_ENABLE_CONNECT_PROTOCOL = 0x8

DEFAULT_SETTINGS = {
    SETTING_HEADER_TABLE_SIZE: 4096,
    SETTING_ENABLE_PUSH: 0,
    SETTING_MAX_CONCURRENT_STREAMS: 128,
    SETTING_INITIAL_WINDOW_SIZE: 65535,
    SETTING_MAX_FRAME_SIZE: 16384,
    SETTING_MAX_HEADER_LIST_SIZE: 65536,
    SETTING_ENABLE_CONNECT_PROTOCOL: 1,
}


@dataclass(slots=True)
class HTTP2Frame:
    frame_type: int
    flags: int
    stream_id: int
    payload: bytes = b""

    @property
    def length(self) -> int:
        return len(self.payload)


class FrameBuffer:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> None:
        self._buffer.extend(data)

    def pop_all(self) -> list[HTTP2Frame]:
        frames: list[HTTP2Frame] = []
        while len(self._buffer) >= 9:
            length = decode_u24(self._buffer[:3])
            total = 9 + length
            if len(self._buffer) < total:
                break
            frame_type = self._buffer[3]
            flags = self._buffer[4]
            stream_id = int.from_bytes(self._buffer[5:9], "big") & 0x7FFFFFFF
            payload = bytes(self._buffer[9:total])
            del self._buffer[:total]
            frames.append(HTTP2Frame(frame_type=frame_type, flags=flags, stream_id=stream_id, payload=payload))
        return frames


class FrameWriter:
    def __init__(self, max_frame_size: int = 16384) -> None:
        self.max_frame_size = max_frame_size

    def headers(self, stream_id: int, block: bytes, *, end_stream: bool = False) -> bytes:
        pieces = list(split_chunks(block, self.max_frame_size)) or [b""]
        raw = bytearray()
        for idx, piece in enumerate(pieces):
            flags = 0
            if idx == len(pieces) - 1:
                flags |= FLAG_END_HEADERS
                if end_stream:
                    flags |= FLAG_END_STREAM
            raw.extend(serialize_frame(FRAME_HEADERS if idx == 0 else FRAME_CONTINUATION, flags, stream_id, piece))
        return bytes(raw)

    def push_promise(self, stream_id: int, promised_stream_id: int, block: bytes) -> bytes:
        first_capacity = max(self.max_frame_size - 4, 0)
        first_piece = block[:first_capacity]
        remainder = block[first_capacity:]
        payload = (promised_stream_id & 0x7FFFFFFF).to_bytes(4, "big") + first_piece
        if not remainder:
            return serialize_frame(FRAME_PUSH_PROMISE, FLAG_END_HEADERS, stream_id, payload)
        raw = bytearray()
        raw.extend(serialize_frame(FRAME_PUSH_PROMISE, 0, stream_id, payload))
        pieces = list(split_chunks(remainder, self.max_frame_size))
        for idx, piece in enumerate(pieces):
            flags = FLAG_END_HEADERS if idx == len(pieces) - 1 else 0
            raw.extend(serialize_frame(FRAME_CONTINUATION, flags, stream_id, piece))
        return bytes(raw)

    def data(self, stream_id: int, payload: bytes, *, end_stream: bool = False) -> bytes:
        pieces = list(split_chunks(payload, self.max_frame_size)) or [b""]
        raw = bytearray()
        for idx, piece in enumerate(pieces):
            flags = FLAG_END_STREAM if idx == len(pieces) - 1 and end_stream else 0
            raw.extend(serialize_frame(FRAME_DATA, flags, stream_id, piece))
        return bytes(raw)


def serialize_frame(frame_type: int, flags: int, stream_id: int, payload: bytes = b"") -> bytes:
    if stream_id < 0 or stream_id > 0x7FFFFFFF:
        raise ValueError("stream_id out of range")
    header = bytearray()
    header.extend(encode_u24(len(payload)))
    header.append(frame_type & 0xFF)
    header.append(flags & 0xFF)
    header.extend((stream_id & 0x7FFFFFFF).to_bytes(4, "big"))
    return bytes(header) + payload


def encode_settings(settings: Mapping[int, int]) -> bytes:
    payload = bytearray()
    for setting_id, value in settings.items():
        payload.extend(int(setting_id).to_bytes(2, "big"))
        payload.extend(int(value).to_bytes(4, "big"))
    return bytes(payload)


def decode_settings(payload: bytes) -> dict[int, int]:
    if len(payload) % 6 != 0:
        raise ProtocolError("invalid SETTINGS payload length")
    settings: dict[int, int] = {}
    for offset in range(0, len(payload), 6):
        key = int.from_bytes(payload[offset : offset + 2], "big")
        value = int.from_bytes(payload[offset + 2 : offset + 6], "big")
        if key in settings:
            raise ProtocolError("duplicate SETTINGS parameter")
        if key == SETTING_ENABLE_PUSH and value not in {0, 1}:
            raise ProtocolError("ENABLE_PUSH must be 0 or 1")
        if key == SETTING_INITIAL_WINDOW_SIZE and value > 0x7FFFFFFF:
            raise ProtocolError("INITIAL_WINDOW_SIZE too large")
        if key == SETTING_MAX_FRAME_SIZE and not 16_384 <= value <= 16_777_215:
            raise ProtocolError("MAX_FRAME_SIZE out of range")
        if key == SETTING_ENABLE_CONNECT_PROTOCOL and value not in {0, 1}:
            raise ProtocolError("ENABLE_CONNECT_PROTOCOL must be 0 or 1")
        settings[key] = value
    return settings


def serialize_settings(settings: Mapping[int, int]) -> bytes:
    return serialize_frame(FRAME_SETTINGS, 0, 0, encode_settings(settings))


def serialize_settings_ack() -> bytes:
    return serialize_frame(FRAME_SETTINGS, FLAG_ACK, 0, b"")


def serialize_window_update(stream_id: int, increment: int) -> bytes:
    if not 1 <= increment <= 0x7FFFFFFF:
        raise ValueError("WINDOW_UPDATE increment out of range")
    return serialize_frame(FRAME_WINDOW_UPDATE, 0, stream_id, increment.to_bytes(4, "big"))


def parse_window_update(payload: bytes) -> int:
    if len(payload) != 4:
        raise ProtocolError("WINDOW_UPDATE payload must be 4 bytes")
    increment = int.from_bytes(payload, "big") & 0x7FFFFFFF
    if increment <= 0:
        raise ProtocolError("WINDOW_UPDATE increment must be positive")
    return increment


def serialize_ping(data: bytes, *, ack: bool = False) -> bytes:
    if len(data) != 8:
        raise ValueError("PING payload must be 8 bytes")
    return serialize_frame(FRAME_PING, FLAG_ACK if ack else 0, 0, data)


def serialize_goaway(last_stream_id: int, error_code: int = 0, debug_data: bytes = b"") -> bytes:
    payload = bytearray()
    payload.extend((last_stream_id & 0x7FFFFFFF).to_bytes(4, "big"))
    payload.extend(int(error_code).to_bytes(4, "big"))
    payload.extend(debug_data)
    return serialize_frame(FRAME_GOAWAY, 0, 0, bytes(payload))


def parse_goaway(payload: bytes) -> tuple[int, int, bytes]:
    if len(payload) < 8:
        raise ProtocolError("GOAWAY payload too short")
    last_stream_id = int.from_bytes(payload[:4], "big") & 0x7FFFFFFF
    error_code = int.from_bytes(payload[4:8], "big")
    return last_stream_id, error_code, payload[8:]


def parse_priority(payload: bytes) -> tuple[bool, int, int]:
    if len(payload) != 5:
        raise ProtocolError("PRIORITY payload must be 5 bytes")
    dependency_raw = int.from_bytes(payload[:4], "big")
    exclusive = bool(dependency_raw & 0x80000000)
    dependency = dependency_raw & 0x7FFFFFFF
    weight = payload[4]
    return exclusive, dependency, weight


def parse_push_promise(payload: bytes, flags: int) -> tuple[int, bytes]:
    payload = strip_padding(payload, flags)
    if len(payload) < 4:
        raise ProtocolError("PUSH_PROMISE payload too short")
    promised_stream_id = int.from_bytes(payload[:4], "big") & 0x7FFFFFFF
    return promised_stream_id, payload[4:]


def serialize_push_promise(stream_id: int, promised_stream_id: int, header_block_fragment: bytes, *, end_headers: bool = True) -> bytes:
    flags = FLAG_END_HEADERS if end_headers else 0
    payload = (promised_stream_id & 0x7FFFFFFF).to_bytes(4, "big") + header_block_fragment
    return serialize_frame(FRAME_PUSH_PROMISE, flags, stream_id, payload)


def serialize_rst_stream(stream_id: int, error_code: int = 0) -> bytes:
    return serialize_frame(FRAME_RST_STREAM, 0, stream_id, int(error_code).to_bytes(4, "big"))


def strip_padding(payload: bytes, flags: int) -> bytes:
    if not (flags & FLAG_PADDED):
        return payload
    if not payload:
        raise ProtocolError("PADDED frame missing pad length")
    pad_length = payload[0]
    body = payload[1:]
    if pad_length > len(body):
        raise ProtocolError("invalid padding")
    return body[:-pad_length] if pad_length else body


def headers_payload_fragment(payload: bytes, flags: int) -> bytes:
    payload = strip_padding(payload, flags)
    if flags & FLAG_PRIORITY:
        if len(payload) < 5:
            raise ProtocolError("HEADERS priority payload too short")
        payload = payload[5:]
    return payload
