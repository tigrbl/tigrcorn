from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable, Iterable

from tigrcorn.errors import ProtocolError
from tigrcorn.protocols._compression import (
    decode_prefixed_integer,
    decode_prefixed_string,
    encode_prefixed_integer,
    encode_prefixed_string,
)

# RFC 9204 Appendix A static table (0-indexed).
_STATIC_TABLE: list[tuple[bytes, bytes]] = [
    (b":authority", b""),
    (b":path", b"/"),
    (b"age", b"0"),
    (b"content-disposition", b""),
    (b"content-length", b"0"),
    (b"cookie", b""),
    (b"date", b""),
    (b"etag", b""),
    (b"if-modified-since", b""),
    (b"if-none-match", b""),
    (b"last-modified", b""),
    (b"link", b""),
    (b"location", b""),
    (b"referer", b""),
    (b"set-cookie", b""),
    (b":method", b"CONNECT"),
    (b":method", b"DELETE"),
    (b":method", b"GET"),
    (b":method", b"HEAD"),
    (b":method", b"OPTIONS"),
    (b":method", b"POST"),
    (b":method", b"PUT"),
    (b":scheme", b"http"),
    (b":scheme", b"https"),
    (b":status", b"103"),
    (b":status", b"200"),
    (b":status", b"304"),
    (b":status", b"404"),
    (b":status", b"503"),
    (b"accept", b"*/*"),
    (b"accept", b"application/dns-message"),
    (b"accept-encoding", b"gzip, deflate, br"),
    (b"accept-ranges", b"bytes"),
    (b"access-control-allow-headers", b"cache-control"),
    (b"access-control-allow-headers", b"content-type"),
    (b"access-control-allow-origin", b"*"),
    (b"cache-control", b"max-age=0"),
    (b"cache-control", b"max-age=2592000"),
    (b"cache-control", b"max-age=604800"),
    (b"cache-control", b"no-cache"),
    (b"cache-control", b"no-store"),
    (b"cache-control", b"public, max-age=31536000"),
    (b"content-encoding", b"br"),
    (b"content-encoding", b"gzip"),
    (b"content-type", b"application/dns-message"),
    (b"content-type", b"application/javascript"),
    (b"content-type", b"application/json"),
    (b"content-type", b"application/x-www-form-urlencoded"),
    (b"content-type", b"image/gif"),
    (b"content-type", b"image/jpeg"),
    (b"content-type", b"image/png"),
    (b"content-type", b"text/css"),
    (b"content-type", b"text/html; charset=utf-8"),
    (b"content-type", b"text/plain"),
    (b"content-type", b"text/plain;charset=utf-8"),
    (b"range", b"bytes=0-"),
    (b"strict-transport-security", b"max-age=31536000"),
    (b"strict-transport-security", b"max-age=31536000; includesubdomains"),
    (b"strict-transport-security", b"max-age=31536000; includesubdomains; preload"),
    (b"vary", b"accept-encoding"),
    (b"vary", b"origin"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-xss-protection", b"1; mode=block"),
    (b":status", b"100"),
    (b":status", b"204"),
    (b":status", b"206"),
    (b":status", b"302"),
    (b":status", b"400"),
    (b":status", b"403"),
    (b":status", b"421"),
    (b":status", b"425"),
    (b":status", b"500"),
    (b"accept-language", b""),
    (b"access-control-allow-credentials", b"FALSE"),
    (b"access-control-allow-credentials", b"TRUE"),
    (b"access-control-allow-headers", b"*"),
    (b"access-control-allow-methods", b"get"),
    (b"access-control-allow-methods", b"get, post, options"),
    (b"access-control-allow-methods", b"options"),
    (b"access-control-expose-headers", b"content-length"),
    (b"access-control-request-headers", b"content-type"),
    (b"access-control-request-method", b"get"),
    (b"access-control-request-method", b"post"),
    (b"alt-svc", b"clear"),
    (b"authorization", b""),
    (b"content-security-policy", b"script-src 'none'; object-src 'none'; base-uri 'none'"),
    (b"early-data", b"1"),
    (b"expect-ct", b""),
    (b"forwarded", b""),
    (b"if-range", b""),
    (b"origin", b""),
    (b"purpose", b"prefetch"),
    (b"server", b""),
    (b"timing-allow-origin", b"*"),
    (b"upgrade-insecure-requests", b"1"),
    (b"user-agent", b""),
    (b"x-forwarded-for", b""),
    (b"x-frame-options", b"deny"),
    (b"x-frame-options", b"sameorigin"),
]

STATIC_INDEX: dict[tuple[bytes, bytes], int] = {entry: idx for idx, entry in enumerate(_STATIC_TABLE)}
STATIC_NAME_INDEX: dict[bytes, int] = {}
for idx, (name, _value) in enumerate(_STATIC_TABLE):
    if name not in STATIC_NAME_INDEX:
        STATIC_NAME_INDEX[name] = idx

SENSITIVE_HEADERS = {
    b"authorization",
    b"cookie",
    b"proxy-authorization",
    b"set-cookie",
}


class QpackError(ProtocolError):
    pass


class QpackBlocked(QpackError):
    def __init__(self, required_insert_count: int) -> None:
        super().__init__(f"QPACK field section is blocked on insert count {required_insert_count}")
        self.required_insert_count = required_insert_count


class QpackDecompressionFailed(QpackError):
    pass


class QpackEncoderStreamError(QpackError):
    pass


class QpackDecoderStreamError(QpackError):
    pass


@dataclass(slots=True)
class FieldLine:
    name: bytes
    value: bytes


@dataclass(slots=True)
class QpackFieldSection:
    required_insert_count: int
    base: int
    headers: list[tuple[bytes, bytes]]
    used_dynamic: bool = False


@dataclass(slots=True)
class QpackDynamicEntry:
    absolute_index: int
    name: bytes
    value: bytes

    @property
    def size(self) -> int:
        return len(self.name) + len(self.value) + 32


@dataclass(slots=True)
class _OutstandingSection:
    required_insert_count: int
    referenced_indexes: tuple[int, ...]


@dataclass(slots=True)
class _PlannedHeaderField:
    kind: str
    name: bytes
    value: bytes
    static_index: int | None = None
    dynamic_absolute_index: int | None = None

    def referenced_indexes(self) -> set[int]:
        if self.dynamic_absolute_index is None:
            return set()
        return {self.dynamic_absolute_index}

    def render(self, *, base: int, huffman: bool) -> bytes:
        if self.kind == 'static_exact':
            assert self.static_index is not None
            return encode_qpack_integer(self.static_index, 6, 0xC0)
        if self.kind == 'dynamic_exact':
            assert self.dynamic_absolute_index is not None
            relative_index = base - self.dynamic_absolute_index - 1
            return encode_qpack_integer(relative_index, 6, 0x80)
        if self.kind == 'static_name':
            assert self.static_index is not None
            return encode_qpack_integer(self.static_index, 4, 0x50) + encode_qpack_string(
                self.value, 8, 0x00, huffman=huffman
            )
        if self.kind == 'dynamic_name':
            assert self.dynamic_absolute_index is not None
            relative_index = base - self.dynamic_absolute_index - 1
            return encode_qpack_integer(relative_index, 4, 0x40) + encode_qpack_string(
                self.value, 8, 0x00, huffman=huffman
            )
        if self.kind == 'literal':
            return encode_qpack_string(self.name, 4, 0x20, huffman=huffman) + encode_qpack_string(
                self.value, 8, 0x00, huffman=huffman
            )
        raise ProtocolError(f'unsupported QPACK header representation: {self.kind}')


@dataclass(slots=True)
class QpackDynamicTable:
    maximum_capacity: int = 0
    capacity: int = 0
    entries: list[QpackDynamicEntry] = field(default_factory=list)  # newest first
    size: int = 0
    insert_count: int = 0

    def max_entries(self) -> int:
        return self.maximum_capacity // 32 if self.maximum_capacity > 0 else 0

    def set_capacity(self, capacity: int, *, evictable: Callable[[QpackDynamicEntry], bool] | None = None) -> None:
        if capacity < 0 or capacity > self.maximum_capacity:
            raise ProtocolError('QPACK dynamic table capacity out of range')
        self.capacity = capacity
        if not self._evict_to_limit(0, evictable=evictable):
            raise ProtocolError('QPACK dynamic table capacity would evict a referenced entry')

    def _evict_to_limit(
        self,
        incoming_size: int,
        *,
        evictable: Callable[[QpackDynamicEntry], bool] | None = None,
    ) -> bool:
        while self.size + incoming_size > self.capacity:
            if not self.entries:
                return False
            evicted = self.entries[-1]
            if evictable is not None and not evictable(evicted):
                return False
            self.entries.pop()
            self.size -= evicted.size
        return True

    def can_insert(
        self,
        name: bytes,
        value: bytes,
        *,
        evictable: Callable[[QpackDynamicEntry], bool] | None = None,
    ) -> bool:
        entry_size = len(name) + len(value) + 32
        if entry_size > self.capacity:
            return False
        simulated_size = self.size
        for entry in reversed(self.entries):
            if simulated_size + entry_size <= self.capacity:
                break
            if evictable is not None and not evictable(entry):
                return False
            simulated_size -= entry.size
        return simulated_size + entry_size <= self.capacity

    def insert(
        self,
        name: bytes,
        value: bytes,
        *,
        evictable: Callable[[QpackDynamicEntry], bool] | None = None,
    ) -> QpackDynamicEntry:
        entry = QpackDynamicEntry(absolute_index=self.insert_count, name=name, value=value)
        if entry.size > self.capacity:
            raise ProtocolError('QPACK dynamic entry exceeds table capacity')
        if not self._evict_to_limit(entry.size, evictable=evictable):
            raise ProtocolError('QPACK dynamic entry would evict a referenced entry')
        self.entries.insert(0, entry)
        self.size += entry.size
        self.insert_count += 1
        return entry

    def duplicate_relative(
        self,
        relative_index: int,
        *,
        evictable: Callable[[QpackDynamicEntry], bool] | None = None,
    ) -> QpackDynamicEntry:
        entry = self.lookup_instruction_relative(relative_index)
        return self.insert(entry.name, entry.value, evictable=evictable)

    def lookup_static(self, index: int) -> tuple[bytes, bytes]:
        if index < 0 or index >= len(_STATIC_TABLE):
            raise ProtocolError(f'unsupported QPACK static index: {index}')
        return _STATIC_TABLE[index]

    def lookup_absolute_entry(self, absolute_index: int) -> QpackDynamicEntry:
        for entry in self.entries:
            if entry.absolute_index == absolute_index:
                return entry
        raise ProtocolError(f'unknown QPACK dynamic index: {absolute_index}')

    def lookup_absolute(self, absolute_index: int) -> tuple[bytes, bytes]:
        entry = self.lookup_absolute_entry(absolute_index)
        return entry.name, entry.value

    def absolute_index_from_relative(self, base: int, relative_index: int) -> int:
        absolute_index = base - relative_index - 1
        if absolute_index < 0:
            raise ProtocolError('invalid QPACK relative index')
        return absolute_index

    def absolute_index_from_post_base(self, base: int, post_base_index: int) -> int:
        absolute_index = base + post_base_index
        if absolute_index < 0:
            raise ProtocolError('invalid QPACK post-base index')
        return absolute_index

    def lookup_relative(self, base: int, relative_index: int) -> tuple[bytes, bytes]:
        return self.lookup_absolute(self.absolute_index_from_relative(base, relative_index))

    def lookup_post_base(self, base: int, post_base_index: int) -> tuple[bytes, bytes]:
        return self.lookup_absolute(self.absolute_index_from_post_base(base, post_base_index))

    def lookup_instruction_relative(self, relative_index: int) -> QpackDynamicEntry:
        absolute_index = self.insert_count - relative_index - 1
        if absolute_index < 0:
            raise ProtocolError('invalid QPACK instruction relative index')
        return self.lookup_absolute_entry(absolute_index)

    def lookup_dynamic_exact(self, name: bytes, value: bytes, *, max_absolute_index: int | None = None) -> QpackDynamicEntry | None:
        for entry in self.entries:
            if max_absolute_index is not None and entry.absolute_index >= max_absolute_index:
                continue
            if entry.name == name and entry.value == value:
                return entry
        return None

    def lookup_dynamic_name(self, name: bytes, *, max_absolute_index: int | None = None) -> QpackDynamicEntry | None:
        for entry in self.entries:
            if max_absolute_index is not None and entry.absolute_index >= max_absolute_index:
                continue
            if entry.name == name:
                return entry
        return None


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


class QpackEncoder:
    def __init__(
        self,
        *,
        max_table_capacity: int = 0,
        blocked_streams: int = 0,
        use_huffman: bool = True,
        sensitive_headers: set[bytes] | None = None,
    ) -> None:
        self.dynamic_table = QpackDynamicTable(maximum_capacity=max_table_capacity, capacity=0)
        self.blocked_streams = blocked_streams
        self.use_huffman = use_huffman
        self.sensitive_headers = set(SENSITIVE_HEADERS if sensitive_headers is None else sensitive_headers)
        self.known_received_count = 0
        self._pending_encoder_bytes = bytearray()
        self._announced_capacity = 0
        self._outstanding_sections: dict[int, list[_OutstandingSection]] = {}
        self._reference_counts: dict[int, int] = {}

    def _evictable_entry(self, entry: QpackDynamicEntry) -> bool:
        return entry.absolute_index < self.known_received_count and self._reference_counts.get(entry.absolute_index, 0) == 0

    def _ensure_capacity_announced(self) -> None:
        target = self.dynamic_table.maximum_capacity
        if target > 0 and self._announced_capacity != target:
            self.dynamic_table.set_capacity(target, evictable=self._evictable_entry)
            self._pending_encoder_bytes.extend(encode_set_dynamic_table_capacity(target))
            self._announced_capacity = target

    def _should_index(self, name: bytes, value: bytes) -> bool:
        if self.dynamic_table.maximum_capacity <= 0 or name in self.sensitive_headers:
            return False
        return self.dynamic_table.can_insert(name, value, evictable=self._evictable_entry)

    def _queue_insert(self, name: bytes, value: bytes) -> QpackDynamicEntry:
        static_name_index = STATIC_NAME_INDEX.get(name)
        dynamic_name_entry = self.dynamic_table.lookup_dynamic_name(name)
        if static_name_index is not None:
            self._pending_encoder_bytes.extend(
                encode_insert_with_name_reference(static_name_index, value, static=True, huffman=self.use_huffman)
            )
        elif dynamic_name_entry is not None:
            relative_index = self.dynamic_table.insert_count - dynamic_name_entry.absolute_index - 1
            self._pending_encoder_bytes.extend(
                encode_insert_with_name_reference(relative_index, value, static=False, huffman=self.use_huffman)
            )
        else:
            self._pending_encoder_bytes.extend(encode_insert_with_literal_name(name, value, huffman=self.use_huffman))
        return self.dynamic_table.insert(name, value, evictable=self._evictable_entry)

    def _encode_prefix(self, required_insert_count: int, base: int) -> bytes:
        max_entries = self.dynamic_table.max_entries()
        if required_insert_count == 0:
            encoded_required = 0
        else:
            if max_entries <= 0:
                raise ProtocolError('QPACK dynamic references require non-zero table capacity')
            encoded_required = (required_insert_count % (2 * max_entries)) + 1
        if base < required_insert_count:
            sign = 1
            delta = required_insert_count - base - 1
        else:
            sign = 0
            delta = base - required_insert_count
        return encode_qpack_integer(encoded_required, 8, 0x00) + encode_qpack_integer(delta, 7, 0x80 if sign else 0x00)

    def _blocked_stream_ids(self) -> set[int]:
        blocked: set[int] = set()
        for stream_id, sections in self._outstanding_sections.items():
            if any(section.required_insert_count > self.known_received_count for section in sections):
                blocked.add(stream_id)
        return blocked

    def _can_risk_blocking(self, stream_id: int) -> bool:
        if self.blocked_streams <= 0:
            return False
        blocked_stream_ids = self._blocked_stream_ids()
        return stream_id in blocked_stream_ids or len(blocked_stream_ids) < self.blocked_streams

    def _plan_header(self, name: bytes, value: bytes, *, reference_limit: int) -> _PlannedHeaderField:
        static_exact = STATIC_INDEX.get((name, value))
        if static_exact is not None:
            return _PlannedHeaderField(kind='static_exact', name=name, value=value, static_index=static_exact)
        dynamic_exact = self.dynamic_table.lookup_dynamic_exact(name, value, max_absolute_index=reference_limit)
        if dynamic_exact is not None:
            return _PlannedHeaderField(
                kind='dynamic_exact',
                name=name,
                value=value,
                dynamic_absolute_index=dynamic_exact.absolute_index,
            )
        static_name = STATIC_NAME_INDEX.get(name)
        if static_name is not None:
            return _PlannedHeaderField(kind='static_name', name=name, value=value, static_index=static_name)
        dynamic_name = self.dynamic_table.lookup_dynamic_name(name, max_absolute_index=reference_limit)
        if dynamic_name is not None:
            return _PlannedHeaderField(
                kind='dynamic_name',
                name=name,
                value=value,
                dynamic_absolute_index=dynamic_name.absolute_index,
            )
        return _PlannedHeaderField(kind='literal', name=name, value=value)

    def _track_outstanding_section(self, stream_id: int, *, required_insert_count: int, referenced_indexes: set[int]) -> None:
        if required_insert_count <= 0:
            return
        ordered_indexes = tuple(sorted(referenced_indexes))
        self._outstanding_sections.setdefault(stream_id, []).append(
            _OutstandingSection(required_insert_count=required_insert_count, referenced_indexes=ordered_indexes)
        )
        for absolute_index in ordered_indexes:
            self._reference_counts[absolute_index] = self._reference_counts.get(absolute_index, 0) + 1

    def _release_section(self, section: _OutstandingSection) -> None:
        for absolute_index in section.referenced_indexes:
            remaining = self._reference_counts.get(absolute_index, 0) - 1
            if remaining > 0:
                self._reference_counts[absolute_index] = remaining
            else:
                self._reference_counts.pop(absolute_index, None)

    def encode_field_section(self, headers: Iterable[tuple[bytes, bytes]], *, stream_id: int = 0) -> bytes:
        header_list = [(bytes(name), bytes(value)) for name, value in headers]
        allow_blocking = self._can_risk_blocking(stream_id)
        if self.dynamic_table.maximum_capacity > 0:
            self._ensure_capacity_announced()
            if allow_blocking:
                inserted: set[tuple[bytes, bytes]] = set()
                for name, value in header_list:
                    if not self._should_index(name, value):
                        continue
                    if STATIC_INDEX.get((name, value)) is not None:
                        continue
                    if self.dynamic_table.lookup_dynamic_exact(name, value) is not None:
                        continue
                    candidate = (name, value)
                    if candidate in inserted:
                        continue
                    try:
                        self._queue_insert(name, value)
                    except ProtocolError:
                        continue
                    inserted.add(candidate)
        reference_limit = self.dynamic_table.insert_count if allow_blocking else self.known_received_count
        plans = [self._plan_header(name, value, reference_limit=reference_limit) for name, value in header_list]
        referenced_indexes: set[int] = set()
        for plan in plans:
            referenced_indexes.update(plan.referenced_indexes())
        required_insert_count = max((absolute_index + 1 for absolute_index in referenced_indexes), default=0)
        base = required_insert_count
        encoded = bytearray(self._encode_prefix(required_insert_count, base))
        for plan in plans:
            encoded.extend(plan.render(base=base, huffman=self.use_huffman))
        self._track_outstanding_section(stream_id, required_insert_count=required_insert_count, referenced_indexes=referenced_indexes)
        return bytes(encoded)

    def receive_decoder_stream(self, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            first = data[offset]
            if first & 0x80:
                stream_id, offset = decode_qpack_integer(data, offset, 7)
                outstanding = self._outstanding_sections.get(stream_id)
                if not outstanding:
                    raise QpackDecoderStreamError('unexpected QPACK section acknowledgment')
                section = outstanding.pop(0)
                self._release_section(section)
                self.known_received_count = max(self.known_received_count, section.required_insert_count)
                if not outstanding:
                    self._outstanding_sections.pop(stream_id, None)
                continue
            if first & 0x40:
                stream_id, offset = decode_qpack_integer(data, offset, 6)
                cancelled = self._outstanding_sections.pop(stream_id, [])
                for section in cancelled:
                    self._release_section(section)
                continue
            increment, offset = decode_qpack_integer(data, offset, 6)
            if increment <= 0:
                raise QpackDecoderStreamError('invalid QPACK insert count increment')
            if self.known_received_count + increment > self.dynamic_table.insert_count:
                raise QpackDecoderStreamError('QPACK insert count increment exceeds sent inserts')
            self.known_received_count += increment

    def take_encoder_stream_data(self) -> bytes:
        payload = bytes(self._pending_encoder_bytes)
        self._pending_encoder_bytes.clear()
        return payload


class QpackDecoder:
    def __init__(self, *, max_table_capacity: int = 0, blocked_streams: int = 0) -> None:
        self.dynamic_table = QpackDynamicTable(maximum_capacity=max_table_capacity, capacity=0)
        self.blocked_streams = blocked_streams
        self.known_received_count = 0
        self._pending_decoder_bytes = bytearray()
        self._blocked_requirements: dict[int, list[int]] = {}

    def _decode_required_insert_count(self, encoded_required: int) -> int:
        max_entries = self.dynamic_table.max_entries()
        if encoded_required == 0:
            return 0
        if max_entries <= 0:
            raise QpackDecompressionFailed('QPACK dynamic references require non-zero table capacity')
        full_range = 2 * max_entries
        if encoded_required > full_range:
            raise QpackDecompressionFailed('invalid QPACK encoded required insert count')
        max_value = self.dynamic_table.insert_count + max_entries
        max_wrapped = (max_value // full_range) * full_range
        required = max_wrapped + encoded_required - 1
        if required > max_value:
            if required <= full_range:
                raise QpackDecompressionFailed('invalid QPACK required insert count')
            required -= full_range
        if required == 0:
            raise QpackDecompressionFailed('QPACK zero required insert count must be encoded as zero')
        return required

    def _mark_blocked(self, stream_id: int | None, required_insert_count: int) -> None:
        if stream_id is None:
            return
        blocked = self._blocked_requirements.get(stream_id)
        if blocked is None:
            if len(self._blocked_requirements) >= self.blocked_streams:
                raise QpackDecompressionFailed('QPACK blocked streams limit exceeded')
            blocked = []
            self._blocked_requirements[stream_id] = blocked
        blocked.append(required_insert_count)

    def _unmark_blocked(self, stream_id: int | None, required_insert_count: int) -> None:
        if stream_id is None:
            return
        blocked = self._blocked_requirements.get(stream_id)
        if not blocked:
            return
        try:
            blocked.remove(required_insert_count)
        except ValueError:
            return
        if not blocked:
            self._blocked_requirements.pop(stream_id, None)

    def _lookup_encoder_stream_name(self, *, static: bool, name_index: int) -> bytes:
        try:
            if static:
                name, _value = self.dynamic_table.lookup_static(name_index)
                return name
            entry = self.dynamic_table.lookup_instruction_relative(name_index)
            return entry.name
        except ProtocolError as exc:
            raise QpackEncoderStreamError('invalid QPACK encoder stream name reference') from exc

    def _require_dynamic_entry(self, absolute_index: int, *, required_insert_count: int) -> tuple[bytes, bytes]:
        if required_insert_count <= 0 or absolute_index >= required_insert_count:
            raise QpackDecompressionFailed('invalid QPACK dynamic table reference')
        try:
            return self.dynamic_table.lookup_absolute(absolute_index)
        except ProtocolError as exc:
            raise QpackDecompressionFailed('invalid QPACK dynamic table reference') from exc

    def _resolve_name(self, *, static: bool, base: int, index: int, post_base: bool = False, required_insert_count: int) -> bytes:
        if static:
            try:
                name, _value = self.dynamic_table.lookup_static(index)
            except ProtocolError as exc:
                raise QpackDecompressionFailed('invalid QPACK static table index') from exc
            return name
        try:
            absolute_index = (
                self.dynamic_table.absolute_index_from_post_base(base, index)
                if post_base
                else self.dynamic_table.absolute_index_from_relative(base, index)
            )
        except ProtocolError as exc:
            raise QpackDecompressionFailed('invalid QPACK dynamic name reference') from exc
        name, _value = self._require_dynamic_entry(absolute_index, required_insert_count=required_insert_count)
        return name

    def receive_encoder_stream(self, data: bytes) -> None:
        offset = 0
        processed_inserts = 0
        while offset < len(data):
            first = data[offset]
            if first & 0x80:
                static = bool(first & 0x40)
                name_index, offset = decode_qpack_integer(data, offset, 6)
                name = self._lookup_encoder_stream_name(static=static, name_index=name_index)
                try:
                    value, offset = decode_qpack_string(data, offset, 8)
                    self.dynamic_table.insert(name, value)
                except ProtocolError as exc:
                    raise QpackEncoderStreamError('invalid QPACK encoder stream insertion') from exc
                processed_inserts += 1
                continue
            if first & 0x40:
                try:
                    name, offset = decode_qpack_string(data, offset, 6)
                    value, offset = decode_qpack_string(data, offset, 8)
                    self.dynamic_table.insert(name, value)
                except ProtocolError as exc:
                    raise QpackEncoderStreamError('invalid QPACK encoder stream literal insertion') from exc
                processed_inserts += 1
                continue
            if first & 0x20:
                try:
                    capacity, offset = decode_qpack_integer(data, offset, 5)
                    self.dynamic_table.set_capacity(capacity)
                except ProtocolError as exc:
                    raise QpackEncoderStreamError('invalid QPACK encoder stream capacity update') from exc
                continue
            try:
                relative_index, offset = decode_qpack_integer(data, offset, 5)
                self.dynamic_table.duplicate_relative(relative_index)
            except ProtocolError as exc:
                raise QpackEncoderStreamError('invalid QPACK duplicate instruction') from exc
            processed_inserts += 1
        if processed_inserts:
            self.known_received_count += processed_inserts
            self._pending_decoder_bytes.extend(encode_insert_count_increment(processed_inserts))

    def decode_field_section(self, data: bytes, *, stream_id: int | None = 0) -> QpackFieldSection:
        offset = 0
        encoded_required, offset = decode_qpack_integer(data, offset, 8)
        required_insert_count = self._decode_required_insert_count(encoded_required)
        if required_insert_count > self.dynamic_table.insert_count:
            self._mark_blocked(stream_id, required_insert_count)
            raise QpackBlocked(required_insert_count)
        if offset >= len(data):
            raise QpackDecompressionFailed('truncated QPACK field section prefix')
        sign = bool(data[offset] & 0x80)
        delta_base, offset = decode_qpack_integer(data, offset, 7)
        if sign:
            if required_insert_count <= delta_base:
                raise QpackDecompressionFailed('invalid QPACK base')
            base = required_insert_count - delta_base - 1
        else:
            base = required_insert_count + delta_base
        headers: list[tuple[bytes, bytes]] = []
        used_dynamic = False
        while offset < len(data):
            first = data[offset]
            if first & 0x80:
                static = bool(first & 0x40)
                index, offset = decode_qpack_integer(data, offset, 6)
                if static:
                    try:
                        headers.append(self.dynamic_table.lookup_static(index))
                    except ProtocolError as exc:
                        raise QpackDecompressionFailed('invalid QPACK static table index') from exc
                else:
                    try:
                        absolute_index = self.dynamic_table.absolute_index_from_relative(base, index)
                    except ProtocolError as exc:
                        raise QpackDecompressionFailed('invalid QPACK relative reference') from exc
                    headers.append(self._require_dynamic_entry(absolute_index, required_insert_count=required_insert_count))
                    used_dynamic = True
                continue
            if first & 0x40:
                static = bool(first & 0x10)
                name_index, offset = decode_qpack_integer(data, offset, 4)
                name = self._resolve_name(
                    static=static,
                    base=base,
                    index=name_index,
                    post_base=False,
                    required_insert_count=required_insert_count,
                )
                value, offset = decode_qpack_string(data, offset, 8)
                headers.append((name, value))
                if not static:
                    used_dynamic = True
                continue
            if first & 0x20:
                name, offset = decode_qpack_string(data, offset, 4)
                value, offset = decode_qpack_string(data, offset, 8)
                headers.append((name, value))
                continue
            if first & 0x10:
                index, offset = decode_qpack_integer(data, offset, 4)
                try:
                    absolute_index = self.dynamic_table.absolute_index_from_post_base(base, index)
                except ProtocolError as exc:
                    raise QpackDecompressionFailed('invalid QPACK post-base reference') from exc
                headers.append(self._require_dynamic_entry(absolute_index, required_insert_count=required_insert_count))
                used_dynamic = True
                continue
            name_index, offset = decode_qpack_integer(data, offset, 3)
            name = self._resolve_name(
                static=False,
                base=base,
                index=name_index,
                post_base=True,
                required_insert_count=required_insert_count,
            )
            value, offset = decode_qpack_string(data, offset, 8)
            headers.append((name, value))
            used_dynamic = True
        self._unmark_blocked(stream_id, required_insert_count)
        if required_insert_count != 0 and stream_id is not None:
            self._pending_decoder_bytes.extend(encode_section_ack(stream_id))
        return QpackFieldSection(
            required_insert_count=required_insert_count,
            base=base,
            headers=headers,
            used_dynamic=used_dynamic,
        )

    def cancel_stream(self, stream_id: int) -> None:
        blocked = self._blocked_requirements.pop(stream_id, None)
        if not blocked:
            return
        if self.dynamic_table.maximum_capacity <= 0:
            return
        self._pending_decoder_bytes.extend(encode_stream_cancellation(stream_id))

    def take_decoder_stream_data(self) -> bytes:
        payload = bytes(self._pending_decoder_bytes)
        self._pending_decoder_bytes.clear()
        return payload


# Stateless helpers preserve the previous convenience API but now emit/parse the
# RFC 9204 field-section prefix as well.
def encode_field_line(name: bytes, value: bytes) -> bytes:
    return QpackEncoder(max_table_capacity=0).encode_field_section([(name, value)])


def encode_field_section(headers: Iterable[tuple[bytes, bytes]]) -> bytes:
    return QpackEncoder(max_table_capacity=0).encode_field_section(headers)


def decode_field_section(data: bytes) -> list[tuple[bytes, bytes]]:
    return QpackDecoder(max_table_capacity=0).decode_field_section(data, stream_id=None).headers
