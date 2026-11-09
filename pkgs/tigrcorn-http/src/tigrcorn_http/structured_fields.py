from __future__ import annotations

import base64
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from tigrcorn_config.governance_surface import STRUCTURED_FIELD_REGISTRY


@dataclass(frozen=True, slots=True)
class Token:
    value: str


@dataclass(frozen=True, slots=True)
class ByteSequence:
    value: bytes


@dataclass(frozen=True, slots=True)
class Date:
    value: int


BareItem = bool | int | Decimal | str | Token | ByteSequence | Date


@dataclass(frozen=True, slots=True)
class Item:
    value: BareItem
    params: dict[str, BareItem] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InnerList:
    items: list[Item]
    params: dict[str, BareItem] = field(default_factory=dict)


ListMember = Item | InnerList
StructuredValue = Item | list[ListMember] | dict[str, ListMember]


class StructuredFieldError(ValueError):
    pass


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.length = len(text)
        self.index = 0

    def parse_dictionary(self) -> dict[str, ListMember]:
        result: dict[str, ListMember] = {}
        while True:
            self._skip_ows()
            if self.index >= self.length:
                return result
            key = self._parse_key()
            self._skip_ows()
            if self._peek('='):
                self.index += 1
                member = self.parse_list_member()
            else:
                params = self._parse_parameters()
                member = Item(True, params)
            result[key] = member
            self._skip_ows()
            if self.index >= self.length:
                return result
            self._expect(',')

    def parse_list(self) -> list[ListMember]:
        result: list[ListMember] = []
        while True:
            self._skip_ows()
            if self.index >= self.length:
                return result
            result.append(self.parse_list_member())
            self._skip_ows()
            if self.index >= self.length:
                return result
            self._expect(',')

    def parse_item_only(self) -> Item:
        item = self._parse_item()
        self._skip_ows()
        if self.index != self.length:
            raise StructuredFieldError('unexpected trailing data in structured item')
        return item

    def parse_list_member(self) -> ListMember:
        self._skip_ows()
        if self._peek('('):
            self.index += 1
            items: list[Item] = []
            while True:
                self._skip_sp()
                if self._peek(')'):
                    self.index += 1
                    break
                items.append(self._parse_item())
                self._skip_sp()
                if self._peek(')'):
                    self.index += 1
                    break
            return InnerList(items, self._parse_parameters())
        return self._parse_item()

    def _parse_item(self) -> Item:
        bare = self._parse_bare_item()
        return Item(bare, self._parse_parameters())

    def _parse_parameters(self) -> dict[str, BareItem]:
        params: dict[str, BareItem] = {}
        while self._peek(';'):
            self.index += 1
            key = self._parse_key()
            value: BareItem = True
            if self._peek('='):
                self.index += 1
                value = self._parse_bare_item()
            params[key] = value
        return params

    def _parse_bare_item(self) -> BareItem:
        if self.index >= self.length:
            raise StructuredFieldError('unexpected end of structured field')
        char = self.text[self.index]
        if char == '"':
            return self._parse_string()
        if char == '?':
            return self._parse_boolean()
        if char == ':':
            return self._parse_bytes()
        if char == '@':
            return self._parse_date()
        if char == '-' or char.isdigit():
            return self._parse_number()
        return Token(self._parse_token())

    def _parse_string(self) -> str:
        self._expect('"')
        chunks: list[str] = []
        while self.index < self.length:
            char = self.text[self.index]
            self.index += 1
            if char == '"':
                return ''.join(chunks)
            if char == '\\':
                if self.index >= self.length:
                    raise StructuredFieldError('unterminated escape in structured string')
                chunks.append(self.text[self.index])
                self.index += 1
                continue
            chunks.append(char)
        raise StructuredFieldError('unterminated structured string')

    def _parse_boolean(self) -> bool:
        self._expect('?')
        if self.index >= self.length or self.text[self.index] not in '01':
            raise StructuredFieldError('invalid structured boolean')
        value = self.text[self.index] == '1'
        self.index += 1
        return value

    def _parse_bytes(self) -> ByteSequence:
        self._expect(':')
        start = self.index
        while self.index < self.length and self.text[self.index] != ':':
            self.index += 1
        if self.index >= self.length:
            raise StructuredFieldError('unterminated byte sequence')
        encoded = self.text[start:self.index]
        self.index += 1
        try:
            decoded = base64.b64decode(encoded.encode('ascii'), validate=True)
        except Exception as exc:
            raise StructuredFieldError('invalid byte sequence') from exc
        return ByteSequence(decoded)

    def _parse_date(self) -> Date:
        self._expect('@')
        digits = self._parse_digits(allow_sign=True)
        return Date(int(digits))

    def _parse_number(self) -> int | Decimal:
        number = self._parse_digits(allow_sign=True)
        if self._peek('.'):
            self.index += 1
            fraction = self._parse_digits(allow_sign=False)
            return Decimal(f'{number}.{fraction}')
        return int(number)

    def _parse_token(self) -> str:
        start = self.index
        while self.index < self.length and self.text[self.index] not in '()<>@,;:\\"/[]?={} \t':
            self.index += 1
        token = self.text[start:self.index]
        if not token:
            raise StructuredFieldError('expected token')
        return token

    def _parse_key(self) -> str:
        key = self._parse_token()
        if not key[0].islower() and key[0] != '*':
            raise StructuredFieldError(f'invalid structured key {key!r}')
        return key

    def _parse_digits(self, *, allow_sign: bool) -> str:
        start = self.index
        if allow_sign and self._peek('-'):
            self.index += 1
        while self.index < self.length and self.text[self.index].isdigit():
            self.index += 1
        digits = self.text[start:self.index]
        if digits in {'', '-'}:
            raise StructuredFieldError('expected digits')
        return digits

    def _skip_ows(self) -> None:
        while self.index < self.length and self.text[self.index] in ' \t':
            self.index += 1

    def _skip_sp(self) -> None:
        while self.index < self.length and self.text[self.index] == ' ':
            self.index += 1

    def _expect(self, char: str) -> None:
        if not self._peek(char):
            raise StructuredFieldError(f'expected {char!r}')
        self.index += 1

    def _peek(self, char: str) -> bool:
        return self.index < self.length and self.text[self.index] == char


def parse_item(value: str) -> Item:
    return _Parser(value).parse_item_only()


def parse_list(value: str) -> list[ListMember]:
    return _Parser(value).parse_list()


def parse_dictionary(value: str) -> dict[str, ListMember]:
    return _Parser(value).parse_dictionary()


def parse_structured_field(field_name: str, value: str) -> StructuredValue:
    field_type = STRUCTURED_FIELD_REGISTRY.get(field_name.lower())
    if field_type == 'dictionary':
        return parse_dictionary(value)
    if field_type == 'list':
        return parse_list(value)
    if field_type == 'item':
        return parse_item(value)
    raise StructuredFieldError(f'unknown structured field registry type for {field_name!r}')


def serialize_bare_item(value: BareItem) -> str:
    if isinstance(value, bool):
        return '?1' if value else '?0'
    if isinstance(value, Token):
        return value.value
    if isinstance(value, ByteSequence):
        return ':' + base64.b64encode(value.value).decode('ascii') + ':'
    if isinstance(value, Date):
        return '@' + str(value.value)
    if isinstance(value, Decimal):
        text = format(value, 'f')
        text = text.rstrip('0').rstrip('.') if '.' in text else text
        return text
    if isinstance(value, int):
        return str(value)
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def serialize_item(item: Item) -> str:
    return serialize_bare_item(item.value) + _serialize_params(item.params)


def serialize_list_member(member: ListMember) -> str:
    if isinstance(member, InnerList):
        inner = ' '.join(serialize_item(item) for item in member.items)
        return f'({inner})' + _serialize_params(member.params)
    return serialize_item(member)


def serialize_dictionary(value: dict[str, ListMember]) -> str:
    parts: list[str] = []
    for key, member in value.items():
        if isinstance(member, Item) and member.value is True:
            parts.append(key + _serialize_params(member.params))
        else:
            parts.append(f'{key}={serialize_list_member(member)}')
    return ', '.join(parts)


def serialize_list(value: list[ListMember]) -> str:
    return ', '.join(serialize_list_member(member) for member in value)


def serialize_structured_value(value: StructuredValue) -> str:
    if isinstance(value, dict):
        return serialize_dictionary(value)
    if isinstance(value, list):
        return serialize_list(value)
    return serialize_item(value)


def _serialize_params(params: dict[str, BareItem]) -> str:
    return ''.join(
        f';{key}' if raw is True else f';{key}={serialize_bare_item(raw)}'
        for key, raw in params.items()
    )


def normalize_for_json(value: Any) -> Any:
    if isinstance(value, Token):
        return {'type': 'token', 'value': value.value}
    if isinstance(value, ByteSequence):
        return {'type': 'bytes', 'value': base64.b64encode(value.value).decode('ascii')}
    if isinstance(value, Date):
        return {'type': 'date', 'value': value.value}
    if isinstance(value, Decimal):
        return {'type': 'decimal', 'value': str(value)}
    if isinstance(value, Item):
        return {'type': 'item', 'value': normalize_for_json(value.value), 'params': {k: normalize_for_json(v) for k, v in value.params.items()}}
    if isinstance(value, InnerList):
        return {'type': 'inner_list', 'items': [normalize_for_json(item) for item in value.items], 'params': {k: normalize_for_json(v) for k, v in value.params.items()}}
    if isinstance(value, dict):
        return {key: normalize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_for_json(item) for item in value]
    return value


__all__ = [
    'ByteSequence',
    'Date',
    'InnerList',
    'Item',
    'StructuredFieldError',
    'Token',
    'normalize_for_json',
    'parse_dictionary',
    'parse_item',
    'parse_list',
    'parse_structured_field',
    'serialize_dictionary',
    'serialize_item',
    'serialize_list',
    'serialize_structured_value',
]
