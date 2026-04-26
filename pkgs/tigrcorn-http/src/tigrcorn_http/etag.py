from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityTag:
    value: str
    weak: bool = False

    def to_bytes(self) -> bytes:
        return format_etag(self.value, weak=self.weak)


@dataclass(frozen=True, slots=True)
class EntityTagList:
    any_value: bool
    items: tuple[EntityTag, ...] = ()


def _normalize_opaque_tag(value: bytes | str) -> str:
    if isinstance(value, bytes):
        text = value.decode('latin1')
    else:
        text = value
    return text.replace('\\', '\\\\').replace('"', '\\"')


def format_etag(value: bytes | str, *, weak: bool = False) -> bytes:
    opaque = _normalize_opaque_tag(value).encode('latin1')
    prefix = b'W/' if weak else b''
    return prefix + b'"' + opaque + b'"'


def generate_entity_tag(payload: bytes, *, weak: bool = False) -> bytes:
    digest = hashlib.blake2s(payload, digest_size=16).hexdigest()
    return format_etag(digest, weak=weak)


def parse_entity_tag(raw: bytes | str | None) -> EntityTag | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        data = raw.encode('latin1')
    else:
        data = bytes(raw)
    data = data.strip()
    weak = False
    if data.startswith((b'W/"', b'w/"')):
        weak = True
        data = data[2:]
    if len(data) < 2 or data[:1] != b'"' or data[-1:] != b'"':
        return None
    opaque = data[1:-1].decode('latin1', 'strict')
    return EntityTag(opaque, weak=weak)


def parse_entity_tag_list(raw: bytes | str | None) -> EntityTagList | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        data = raw.encode('latin1')
    else:
        data = bytes(raw)
    data = data.strip()
    if not data:
        return EntityTagList(any_value=False, items=())
    if data == b'*':
        return EntityTagList(any_value=True, items=())

    items: list[EntityTag] = []
    token = bytearray()
    in_quotes = False
    escape = False
    for byte in data:
        if in_quotes:
            token.append(byte)
            if escape:
                escape = False
                continue
            if byte == 0x5C:  # backslash
                escape = True
            elif byte == 0x22:  # quote
                in_quotes = False
            continue
        if byte == 0x22:
            token.append(byte)
            in_quotes = True
            continue
        if byte == 0x2C:  # comma
            item = parse_entity_tag(bytes(token).strip())
            if item is None:
                return None
            items.append(item)
            token.clear()
            continue
        token.append(byte)
    if in_quotes:
        return None
    final = bytes(token).strip()
    if final:
        item = parse_entity_tag(final)
        if item is None:
            return None
        items.append(item)
    return EntityTagList(any_value=False, items=tuple(items))


def strong_compare(left: EntityTag | None, right: EntityTag | None) -> bool:
    if left is None or right is None:
        return False
    if left.weak or right.weak:
        return False
    return left.value == right.value


def weak_compare(left: EntityTag | None, right: EntityTag | None) -> bool:
    if left is None or right is None:
        return False
    return left.value == right.value


__all__ = [
    'EntityTag',
    'EntityTagList',
    'format_etag',
    'generate_entity_tag',
    'parse_entity_tag',
    'parse_entity_tag_list',
    'strong_compare',
    'weak_compare',
]
