from __future__ import annotations

from collections.abc import Iterable

from .decoder import QpackDecoder
from .encoder import QpackEncoder
from .model import (
    FieldLine,
    QpackBlocked,
    QpackDecoderStreamError,
    QpackDecompressionFailed,
    QpackDynamicEntry,
    QpackDynamicTable,
    QpackEncoderStreamError,
    QpackError,
    QpackFieldSection,
)
from .wire import (
    decode_qpack_integer,
    decode_qpack_string,
    encode_duplicate,
    encode_insert_count_increment,
    encode_insert_with_literal_name,
    encode_insert_with_name_reference,
    encode_qpack_integer,
    encode_qpack_string,
    encode_section_ack,
    encode_set_dynamic_table_capacity,
    encode_stream_cancellation,
)


def encode_field_line(name: bytes, value: bytes) -> bytes:
    return QpackEncoder(max_table_capacity=0).encode_field_section([(name, value)])


def encode_field_section(headers: Iterable[tuple[bytes, bytes]]) -> bytes:
    return QpackEncoder(max_table_capacity=0).encode_field_section(headers)


def decode_field_section(data: bytes) -> list[tuple[bytes, bytes]]:
    return QpackDecoder(max_table_capacity=0).decode_field_section(data, stream_id=None).headers


__all__ = [
    "FieldLine",
    "QpackBlocked",
    "QpackDecoder",
    "QpackDecoderStreamError",
    "QpackDecompressionFailed",
    "QpackDynamicEntry",
    "QpackDynamicTable",
    "QpackEncoder",
    "QpackEncoderStreamError",
    "QpackError",
    "QpackFieldSection",
    "decode_field_section",
    "decode_qpack_integer",
    "decode_qpack_string",
    "encode_duplicate",
    "encode_field_line",
    "encode_field_section",
    "encode_insert_count_increment",
    "encode_insert_with_literal_name",
    "encode_insert_with_name_reference",
    "encode_qpack_integer",
    "encode_qpack_string",
    "encode_section_ack",
    "encode_set_dynamic_table_capacity",
    "encode_stream_cancellation",
]
