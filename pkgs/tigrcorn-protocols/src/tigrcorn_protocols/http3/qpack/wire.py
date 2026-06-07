from __future__ import annotations

from tigrcorn_core.errors import ProtocolError
from tigrcorn_protocols._compression import (
    decode_prefixed_integer,
    decode_prefixed_string,
    encode_prefixed_integer,
    encode_prefixed_string,
)

# Wire helpers

def encode_qpack_integer(value: int, prefix_bits: int, prefix_mask: int = 0) -> bytes:
    return encode_prefixed_integer(value, prefix_bits, prefix_mask)


def decode_qpack_integer(data: bytes, offset: int, prefix_bits: int) -> tuple[int, int]:
    return decode_prefixed_integer(data, offset, prefix_bits)


def encode_qpack_string(data: bytes, prefix_bits: int = 8, prefix_mask: int = 0, *, huffman: bool = True) -> bytes:
    return encode_prefixed_string(data, prefix_bits, prefix_mask, huffman=huffman)


def decode_qpack_string(data: bytes, offset: int, prefix_bits: int = 8) -> tuple[bytes, int]:
    return decode_prefixed_string(data, offset, prefix_bits)


# Encoder stream instructions.
def encode_set_dynamic_table_capacity(capacity: int) -> bytes:
    return encode_qpack_integer(capacity, 5, 0x20)


def encode_insert_with_name_reference(name_index: int, value: bytes, *, static: bool, huffman: bool = True) -> bytes:
    return encode_qpack_integer(name_index, 6, 0xC0 if static else 0x80) + encode_qpack_string(
        value, 8, 0x00, huffman=huffman
    )


def encode_insert_with_literal_name(name: bytes, value: bytes, *, huffman: bool = True) -> bytes:
    return encode_qpack_string(name, 6, 0x40, huffman=huffman) + encode_qpack_string(value, 8, 0x00, huffman=huffman)


def encode_duplicate(relative_index: int) -> bytes:
    return encode_qpack_integer(relative_index, 5, 0x00)


# Decoder stream instructions.
def encode_section_ack(stream_id: int) -> bytes:
    return encode_qpack_integer(stream_id, 7, 0x80)


def encode_stream_cancellation(stream_id: int) -> bytes:
    return encode_qpack_integer(stream_id, 6, 0x40)


def encode_insert_count_increment(increment: int) -> bytes:
    if increment <= 0:
        raise ProtocolError('QPACK insert count increment must be positive')
    return encode_qpack_integer(increment, 6, 0x00)
