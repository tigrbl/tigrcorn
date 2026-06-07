from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tigrcorn_core.errors import ProtocolError
from .model import QpackDecoderStreamError, QpackDynamicEntry, QpackDynamicTable, _OutstandingSection
from .static_table import SENSITIVE_HEADERS, STATIC_INDEX, STATIC_NAME_INDEX
from .wire import (
    decode_qpack_integer,
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

