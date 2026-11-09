from __future__ import annotations

from tigrcorn_protocols.websocket.frames import (
    OP_BINARY,
    OP_CLOSE,
    OP_PING,
    OP_PONG,
    OP_TEXT,
    encode_close_payload,
    serialize_frame,
)


def text_frame(text: str, *, rsv1: bool = False) -> bytes:
    return serialize_frame(OP_TEXT, text.encode('utf-8'), rsv1=rsv1)


def binary_frame(data: bytes, *, rsv1: bool = False) -> bytes:
    return serialize_frame(OP_BINARY, data, rsv1=rsv1)


def ping_frame(data: bytes = b'') -> bytes:
    return serialize_frame(OP_PING, data)


def pong_frame(data: bytes = b'') -> bytes:
    return serialize_frame(OP_PONG, data)


def close_frame(code: int = 1000, reason: str = '') -> bytes:
    return serialize_frame(OP_CLOSE, encode_close_payload(code, reason))
