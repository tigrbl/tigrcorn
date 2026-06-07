from __future__ import annotations

from tigrcorn_core.errors import ProtocolError
from .model import (
    QpackBlocked,
    QpackDecoderStreamError,
    QpackDecompressionFailed,
    QpackDynamicTable,
    QpackEncoderStreamError,
    QpackFieldSection,
)
from .wire import (
    decode_qpack_integer,
    decode_qpack_string,
    encode_insert_count_increment,
    encode_section_ack,
    encode_stream_cancellation,
)


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
