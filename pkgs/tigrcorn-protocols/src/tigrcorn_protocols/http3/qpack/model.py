from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tigrcorn_core.errors import ProtocolError
from .static_table import _STATIC_TABLE


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


