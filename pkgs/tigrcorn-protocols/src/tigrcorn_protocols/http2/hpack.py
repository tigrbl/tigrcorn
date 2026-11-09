from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from tigrcorn_core.errors import ProtocolError
from tigrcorn_protocols._compression import (
    decode_prefixed_integer,
    decode_prefixed_string,
    encode_prefixed_integer,
    encode_prefixed_string,
)

_STATIC_TABLE: list[tuple[bytes, bytes]] = [
    (b":authority", b""),
    (b":method", b"GET"),
    (b":method", b"POST"),
    (b":path", b"/"),
    (b":path", b"/index.html"),
    (b":scheme", b"http"),
    (b":scheme", b"https"),
    (b":status", b"200"),
    (b":status", b"204"),
    (b":status", b"206"),
    (b":status", b"304"),
    (b":status", b"400"),
    (b":status", b"404"),
    (b":status", b"500"),
    (b"accept-charset", b""),
    (b"accept-encoding", b"gzip, deflate"),
    (b"accept-language", b""),
    (b"accept-ranges", b""),
    (b"accept", b""),
    (b"access-control-allow-origin", b""),
    (b"age", b""),
    (b"allow", b""),
    (b"authorization", b""),
    (b"cache-control", b""),
    (b"content-disposition", b""),
    (b"content-encoding", b""),
    (b"content-language", b""),
    (b"content-length", b""),
    (b"content-location", b""),
    (b"content-range", b""),
    (b"content-type", b""),
    (b"cookie", b""),
    (b"date", b""),
    (b"etag", b""),
    (b"expect", b""),
    (b"expires", b""),
    (b"from", b""),
    (b"host", b""),
    (b"if-match", b""),
    (b"if-modified-since", b""),
    (b"if-none-match", b""),
    (b"if-range", b""),
    (b"if-unmodified-since", b""),
    (b"last-modified", b""),
    (b"link", b""),
    (b"location", b""),
    (b"max-forwards", b""),
    (b"proxy-authenticate", b""),
    (b"proxy-authorization", b""),
    (b"range", b""),
    (b"referer", b""),
    (b"refresh", b""),
    (b"retry-after", b""),
    (b"server", b""),
    (b"set-cookie", b""),
    (b"strict-transport-security", b""),
    (b"transfer-encoding", b""),
    (b"user-agent", b""),
    (b"vary", b""),
    (b"via", b""),
    (b"www-authenticate", b""),
]

STATIC_TABLE: list[tuple[bytes, bytes] | None] = [None, *_STATIC_TABLE]
STATIC_TABLE_LENGTH = len(STATIC_TABLE) - 1
STATIC_INDEX = {entry: idx for idx, entry in enumerate(STATIC_TABLE) if idx and entry is not None}
STATIC_NAME_INDEX: dict[bytes, int] = {}
for idx, entry in enumerate(STATIC_TABLE):
    if not idx or entry is None:
        continue
    name, _value = entry
    if name not in STATIC_NAME_INDEX:
        STATIC_NAME_INDEX[name] = idx

SENSITIVE_HEADERS = {
    b"authorization",
    b"cookie",
    b"proxy-authorization",
    b"set-cookie",
}


# Public helpers retained for existing callers.
def encode_integer(value: int, prefix_bits: int, prefix_mask: int = 0) -> bytes:
    return encode_prefixed_integer(value, prefix_bits, prefix_mask)



def decode_integer(
    data: bytes,
    offset: int,
    prefix_bits: int,
    *,
    max_octets: int | None = None,
    max_value: int | None = None,
) -> tuple[int, int]:
    return decode_prefixed_integer(data, offset, prefix_bits, max_octets=max_octets, max_value=max_value)



def encode_string(data: bytes, *, huffman: bool = True) -> bytes:
    return encode_prefixed_string(data, 8, 0x00, huffman=huffman)



def decode_string(
    data: bytes,
    offset: int,
    *,
    max_length: int | None = None,
    max_decoded_length: int | None = None,
    max_integer_octets: int | None = None,
) -> tuple[bytes, int]:
    return decode_prefixed_string(
        data,
        offset,
        8,
        max_length=max_length,
        max_decoded_length=max_decoded_length,
        max_integer_octets=max_integer_octets,
    )


@dataclass(slots=True)
class DynamicTableEntry:
    name: bytes
    value: bytes

    @property
    def size(self) -> int:
        return len(self.name) + len(self.value) + 32


@dataclass(slots=True)
class HPACKDynamicTable:
    max_size: int = 4096
    entries: list[DynamicTableEntry] = field(default_factory=list)
    size: int = 0

    def update_max_size(self, max_size: int) -> None:
        if max_size < 0:
            raise ProtocolError("HPACK dynamic table size must be non-negative")
        self.max_size = max_size
        self._evict_to_limit(0)

    def _evict_to_limit(self, incoming_size: int) -> None:
        while self.size + incoming_size > self.max_size and self.entries:
            evicted = self.entries.pop()
            self.size -= evicted.size

    def insert(self, name: bytes, value: bytes) -> None:
        entry = DynamicTableEntry(name=name, value=value)
        if entry.size > self.max_size:
            self.entries.clear()
            self.size = 0
            return
        self._evict_to_limit(entry.size)
        self.entries.insert(0, entry)
        self.size += entry.size

    def lookup(self, index: int) -> tuple[bytes, bytes]:
        if index <= 0:
            raise ProtocolError(f"invalid HPACK index: {index}")
        if index <= STATIC_TABLE_LENGTH:
            entry = STATIC_TABLE[index]
            if entry is None:
                raise ProtocolError(f"unknown HPACK static index: {index}")
            return entry
        dynamic_index = index - STATIC_TABLE_LENGTH - 1
        if dynamic_index < 0 or dynamic_index >= len(self.entries):
            raise ProtocolError(f"unknown HPACK dynamic index: {index}")
        entry = self.entries[dynamic_index]
        return entry.name, entry.value

    def lookup_exact(self, name: bytes, value: bytes) -> int | None:
        exact_static = STATIC_INDEX.get((name, value))
        if exact_static is not None:
            return exact_static
        for offset, entry in enumerate(self.entries, start=STATIC_TABLE_LENGTH + 1):
            if entry.name == name and entry.value == value:
                return offset
        return None

    def lookup_name(self, name: bytes) -> int:
        for offset, entry in enumerate(self.entries, start=STATIC_TABLE_LENGTH + 1):
            if entry.name == name:
                return offset
        return STATIC_NAME_INDEX.get(name, 0)


class HPACKEncoder:
    def __init__(
        self,
        *,
        max_table_size: int = 4096,
        use_huffman: bool = True,
        sensitive_headers: set[bytes] | None = None,
    ) -> None:
        self.dynamic_table = HPACKDynamicTable(max_size=max_table_size)
        self.use_huffman = use_huffman
        self.sensitive_headers = set(SENSITIVE_HEADERS if sensitive_headers is None else sensitive_headers)
        self._pending_table_size_updates: list[int] = []

    def set_max_table_size(self, value: int) -> None:
        self.dynamic_table.update_max_size(value)
        self._pending_table_size_updates.append(value)

    def _encode_indexed(self, index: int) -> bytes:
        return encode_integer(index, 7, 0x80)

    def _encode_literal(self, name: bytes, value: bytes, *, prefix_mask: int, prefix_bits: int, index: bool) -> bytes:
        name_index = self.dynamic_table.lookup_name(name)
        raw = bytearray(encode_integer(name_index, prefix_bits, prefix_mask))
        if name_index == 0:
            raw.extend(encode_string(name, huffman=self.use_huffman))
        raw.extend(encode_string(value, huffman=self.use_huffman))
        if index:
            self.dynamic_table.insert(name, value)
        return bytes(raw)

    def _should_index(self, name: bytes, value: bytes) -> bool:
        if name in self.sensitive_headers:
            return False
        return self.dynamic_table.max_size > 0 and len(name) + len(value) + 32 <= self.dynamic_table.max_size

    def encode_header(self, name: bytes, value: bytes) -> bytes:
        exact = self.dynamic_table.lookup_exact(name, value)
        if exact is not None:
            return self._encode_indexed(exact)
        if self._should_index(name, value):
            return self._encode_literal(name, value, prefix_mask=0x40, prefix_bits=6, index=True)
        prefix_mask = 0x10 if name in self.sensitive_headers else 0x00
        return self._encode_literal(name, value, prefix_mask=prefix_mask, prefix_bits=4, index=False)

    def encode_header_block(self, headers: Iterable[tuple[bytes, bytes]]) -> bytes:
        raw = bytearray()
        for value in self._pending_table_size_updates:
            raw.extend(encode_integer(value, 5, 0x20))
        self._pending_table_size_updates.clear()
        for name, value in headers:
            raw.extend(self.encode_header(name, value))
        return bytes(raw)


class HPACKDecoder:
    def __init__(
        self,
        *,
        max_table_size: int = 4096,
        max_header_list_size: int | None = 65536,
        max_header_block_size: int = 65536,
        max_header_count: int = 256,
        max_string_length: int = 65536,
        max_integer_octets: int = 8,
    ) -> None:
        self.dynamic_table = HPACKDynamicTable(max_size=max_table_size)
        self.max_allowed_table_size = max_table_size
        self.max_header_list_size = max_header_list_size
        self.max_header_block_size = max_header_block_size
        self.max_header_count = max_header_count
        self.max_string_length = max_string_length
        self.max_integer_octets = max_integer_octets

    def set_max_allowed_table_size(self, value: int) -> None:
        if value < 0:
            raise ProtocolError("HPACK table size limit must be non-negative")
        self.max_allowed_table_size = value
        if self.dynamic_table.max_size > value:
            self.dynamic_table.update_max_size(value)

    def set_max_header_list_size(self, value: int | None) -> None:
        if value is not None and value < 0:
            raise ProtocolError("HPACK header list size limit must be non-negative")
        self.max_header_list_size = value

    def _resolve_name(self, name_index: int, data: bytes, offset: int) -> tuple[bytes, int]:
        if name_index == 0:
            return decode_string(
                data,
                offset,
                max_length=self.max_string_length,
                max_decoded_length=self.max_string_length,
                max_integer_octets=self.max_integer_octets,
            )
        name, _value = self.dynamic_table.lookup(name_index)
        return name, offset

    def _append_header(
        self,
        headers: list[tuple[bytes, bytes]],
        header: tuple[bytes, bytes],
        running_size: int,
    ) -> int:
        if len(headers) >= self.max_header_count:
            raise ProtocolError("HPACK header count exceeds configured maximum")
        new_size = running_size + len(header[0]) + len(header[1]) + 32
        if self.max_header_list_size is not None and new_size > self.max_header_list_size:
            raise ProtocolError("HPACK header list exceeds configured maximum")
        headers.append(header)
        return new_size

    def decode_header_block(self, block: bytes) -> list[tuple[bytes, bytes]]:
        if len(block) > self.max_header_block_size:
            raise ProtocolError("HPACK header block exceeds configured maximum")
        headers: list[tuple[bytes, bytes]] = []
        offset = 0
        header_size = 0
        saw_header_representation = False
        while offset < len(block):
            first = block[offset]
            if first & 0x80:
                saw_header_representation = True
                index, offset = decode_integer(block, offset, 7, max_octets=self.max_integer_octets)
                header = self.dynamic_table.lookup(index)
                header_size = self._append_header(headers, header, header_size)
                continue
            if first & 0x40:
                saw_header_representation = True
                name_index, offset = decode_integer(block, offset, 6, max_octets=self.max_integer_octets)
                name, offset = self._resolve_name(name_index, block, offset)
                value, offset = decode_string(
                    block,
                    offset,
                    max_length=self.max_string_length,
                    max_decoded_length=self.max_string_length,
                    max_integer_octets=self.max_integer_octets,
                )
                header_size = self._append_header(headers, (name, value), header_size)
                self.dynamic_table.insert(name, value)
                continue
            if first & 0x20:
                if saw_header_representation:
                    raise ProtocolError("HPACK dynamic table size update must appear at the start of a header block")
                size, offset = decode_integer(
                    block,
                    offset,
                    5,
                    max_octets=self.max_integer_octets,
                    max_value=self.max_allowed_table_size,
                )
                if size > self.max_allowed_table_size:
                    raise ProtocolError("HPACK dynamic table size update exceeds allowed maximum")
                self.dynamic_table.update_max_size(size)
                continue
            saw_header_representation = True
            name_index, offset = decode_integer(block, offset, 4, max_octets=self.max_integer_octets)
            name, offset = self._resolve_name(name_index, block, offset)
            value, offset = decode_string(
                block,
                offset,
                max_length=self.max_string_length,
                max_decoded_length=self.max_string_length,
                max_integer_octets=self.max_integer_octets,
            )
            header_size = self._append_header(headers, (name, value), header_size)
        return headers


# Stateless wrappers used by standalone tests and utilities.
def encode_header(name: bytes, value: bytes) -> bytes:
    return HPACKEncoder(max_table_size=0).encode_header(name, value)



def encode_header_block(headers: Iterable[tuple[bytes, bytes]]) -> bytes:
    return HPACKEncoder().encode_header_block(headers)



def decode_header_block(
    block: bytes,
    *,
    max_header_list_size: int | None = 65536,
    max_header_block_size: int = 65536,
) -> list[tuple[bytes, bytes]]:
    return HPACKDecoder(
        max_header_list_size=max_header_list_size,
        max_header_block_size=max_header_block_size,
    ).decode_header_block(block)
