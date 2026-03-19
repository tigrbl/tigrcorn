from __future__ import annotations

import struct
from dataclasses import dataclass

from tigrcorn.errors import ProtocolError
from tigrcorn.types import StreamReaderLike

OP_CONT = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA
_CONTROL_OPCODES = {OP_CLOSE, OP_PING, OP_PONG}
_DATA_OPCODES = {OP_CONT, OP_TEXT, OP_BINARY}
_VALID_OPCODES = _CONTROL_OPCODES | _DATA_OPCODES
_FORBIDDEN_CLOSE_CODES = {1004, 1005, 1006, 1015}


@dataclass(slots=True)
class Frame:
    fin: bool
    opcode: int
    payload: bytes
    rsv1: bool = False


def _mask_payload(mask_key: bytes, payload: bytes) -> bytes:
    return bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))


def validate_close_code(code: int) -> None:
    if code < 1000 or code >= 5000:
        raise ProtocolError('invalid close code')
    if code in _FORBIDDEN_CLOSE_CODES:
        raise ProtocolError('invalid close code')
    if 1016 <= code <= 2999:
        raise ProtocolError('invalid close code')


def _validate_frame_semantics(fin: bool, opcode: int, payload_length: int) -> None:
    if opcode not in _VALID_OPCODES:
        raise ProtocolError('unsupported websocket opcode')
    if opcode in _CONTROL_OPCODES:
        if not fin:
            raise ProtocolError('control frames must not be fragmented')
        if payload_length > 125:
            raise ProtocolError('control frame payload too large')


def parse_frame_bytes(data: bytes, *, expect_masked: bool = False, max_payload_size: int | None = None, allow_rsv1: bool = False) -> Frame:
    if len(data) < 2:
        raise ProtocolError('incomplete websocket frame')
    pos = 0
    b1, b2 = data[pos], data[pos + 1]
    pos += 2
    fin = bool(b1 & 0x80)
    rsv1 = bool(b1 & 0x40)
    rsv = b1 & 0x70
    opcode = b1 & 0x0F
    masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    if rsv & 0x30:
        raise ProtocolError('RSV2/RSV3 bits are not supported')
    if rsv1 and not allow_rsv1:
        raise ProtocolError('RSV1 is not negotiated')
    if expect_masked and not masked:
        raise ProtocolError('client websocket frames must be masked')
    if length == 126:
        if len(data) < pos + 2:
            raise ProtocolError('incomplete websocket frame')
        length = struct.unpack('!H', data[pos : pos + 2])[0]
        pos += 2
    elif length == 127:
        if len(data) < pos + 8:
            raise ProtocolError('incomplete websocket frame')
        length = struct.unpack('!Q', data[pos : pos + 8])[0]
        pos += 8
    _validate_frame_semantics(fin, opcode, length)
    if max_payload_size is not None and length > max_payload_size:
        raise ProtocolError('websocket frame exceeds configured max payload size')
    mask_key = b''
    if masked:
        if len(data) < pos + 4:
            raise ProtocolError('incomplete websocket frame')
        mask_key = data[pos : pos + 4]
        pos += 4
    if len(data) < pos + length:
        raise ProtocolError('incomplete websocket frame')
    payload = data[pos : pos + length]
    if masked:
        payload = _mask_payload(mask_key, payload)
    return Frame(fin=fin, opcode=opcode, payload=payload, rsv1=rsv1)


async def read_frame(reader: StreamReaderLike, *, max_payload_size: int, expect_masked: bool = True, allow_rsv1: bool = False) -> Frame:
    header = await reader.readexactly(2)
    b1, b2 = header[0], header[1]
    fin = bool(b1 & 0x80)
    rsv1 = bool(b1 & 0x40)
    rsv = b1 & 0x70
    opcode = b1 & 0x0F
    masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    if rsv & 0x30:
        raise ProtocolError('RSV2/RSV3 bits are not supported')
    if rsv1 and not allow_rsv1:
        raise ProtocolError('RSV1 is not negotiated')
    if expect_masked and not masked:
        raise ProtocolError('client websocket frames must be masked')
    if length == 126:
        length = struct.unpack('!H', await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack('!Q', await reader.readexactly(8))[0]
    _validate_frame_semantics(fin, opcode, length)
    if length > max_payload_size:
        raise ProtocolError('websocket frame exceeds configured max payload size')
    if masked:
        mask_key = await reader.readexactly(4)
        payload = await reader.readexactly(length)
        payload = _mask_payload(mask_key, payload)
    else:
        payload = await reader.readexactly(length)
    return Frame(fin=fin, opcode=opcode, payload=payload, rsv1=rsv1)


def serialize_frame(opcode: int, payload: bytes = b'', *, fin: bool = True, mask: bool = False, mask_key: bytes = b'\x00\x00\x00\x00', rsv1: bool = False) -> bytes:
    _validate_frame_semantics(fin, opcode, len(payload))
    first = opcode | (0x80 if fin else 0) | (0x40 if rsv1 else 0)
    length = len(payload)
    mask_bit = 0x80 if mask else 0
    if length < 126:
        head = bytes([first, mask_bit | length])
    elif length <= 0xFFFF:
        head = bytes([first, mask_bit | 126]) + struct.pack('!H', length)
    else:
        head = bytes([first, mask_bit | 127]) + struct.pack('!Q', length)
    if not mask:
        return head + payload
    masked = _mask_payload(mask_key, payload)
    return head + mask_key + masked


def encode_frame(opcode: int, payload: bytes = b'', *, fin: bool = True, masked: bool = False, mask_key: bytes = b'\x00\x00\x00\x00', rsv1: bool = False) -> bytes:
    return serialize_frame(opcode, payload, fin=fin, mask=masked, mask_key=mask_key, rsv1=rsv1)


def decode_frame(data: bytes, *, expect_masked: bool = False, allow_rsv1: bool = False) -> Frame:
    return parse_frame_bytes(data, expect_masked=expect_masked, allow_rsv1=allow_rsv1)


def encode_close_payload(code: int, reason: str = '') -> bytes:
    validate_close_code(code)
    encoded = reason.encode('utf-8')
    if len(encoded) > 123:
        raise ProtocolError('close reason too long')
    return struct.pack('!H', code) + encoded if encoded or code != 1005 else b''


def decode_close_payload(payload: bytes) -> tuple[int, str]:
    if not payload:
        return 1005, ''
    if len(payload) == 1:
        raise ProtocolError('invalid close payload')
    if len(payload) > 125:
        raise ProtocolError('control frame payload too large')
    code = struct.unpack('!H', payload[:2])[0]
    validate_close_code(code)
    try:
        reason = payload[2:].decode('utf-8', 'strict')
    except UnicodeDecodeError as exc:
        raise ProtocolError('invalid close reason utf-8') from exc
    return code, reason
