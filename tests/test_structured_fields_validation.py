from __future__ import annotations

import pytest

from tigrcorn.http.structured_fields import (
    Item,
    StructuredFieldError,
    Token,
    parse_dictionary,
    parse_item,
    serialize_dictionary,
    serialize_item,
)


@pytest.mark.parametrize(
    ('wire_value', 'message_fragment'),
    [
        ('"bad\\q"', 'invalid escape'),
        ('"bad\n"', 'invalid character'),
    ],
)
def test_parse_item_rejects_malformed_strings(wire_value: str, message_fragment: str) -> None:
    with pytest.raises(StructuredFieldError, match=message_fragment):
        parse_item(wire_value)


def test_parse_item_accepts_escaped_quote_and_backslash() -> None:
    parsed = parse_item(r'"a\"b\\c"')

    assert parsed.value == 'a"b\\c'
    assert serialize_item(parsed) == r'"a\"b\\c"'


def test_parse_dictionary_rejects_uppercase_keys() -> None:
    with pytest.raises(StructuredFieldError, match='invalid structured key'):
        parse_dictionary('fooBar=1')


def test_parse_item_accepts_tokens_with_colon_and_slash() -> None:
    parsed = parse_item('Digest:sha-256/example')

    assert parsed.value == Token('Digest:sha-256/example')
    assert serialize_item(parsed) == 'Digest:sha-256/example'


@pytest.mark.parametrize(
    'value',
    [
        {'fooBar': Item(1)},
        {'foo': Item('m\u00fc')},
        {'foo': Item(Token('b\u00e9po'))},
    ],
)
def test_serialize_dictionary_rejects_invalid_keys_and_item_values(value: dict[str, Item]) -> None:
    with pytest.raises(StructuredFieldError):
        serialize_dictionary(value)
