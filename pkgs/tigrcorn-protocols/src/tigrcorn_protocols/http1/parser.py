from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from tigrcorn_core.errors import ProtocolError, UnsupportedFeature
from tigrcorn_protocols.http1.keepalive import expect_continue, keep_alive_for_request
from tigrcorn_core.types import StreamReaderLike
from tigrcorn_core.utils.headers import get_headers, header_contains_token


RequestTargetForm = Literal['origin', 'absolute', 'authority', 'asterisk']


_TCHAR = frozenset(b"!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")


def _is_token(value: bytes) -> bool:
    return bool(value) and all(byte in _TCHAR for byte in value)


def _validate_header_name(name: bytes) -> None:
    if not _is_token(name):
        raise ProtocolError('invalid header field name')


def _validate_header_value(value: bytes) -> None:
    for byte in value:
        if byte in {0x00, 0x0A, 0x0D} or (byte < 0x20 and byte != 0x09):
            raise ProtocolError('invalid header field value')


@dataclass(slots=True)
class ParsedRequest:
    method: str
    target: str
    path: str
    raw_path: bytes
    query_string: bytes
    http_version: str
    headers: list[tuple[bytes, bytes]]
    body: bytes
    keep_alive: bool
    expect_continue: bool
    websocket_upgrade: bool


@dataclass(slots=True)
class ParsedRequestHead:
    method: str
    target: str
    path: str
    raw_path: bytes
    query_string: bytes
    http_version: str
    headers: list[tuple[bytes, bytes]]
    keep_alive: bool
    expect_continue: bool
    websocket_upgrade: bool
    body_kind: Literal['none', 'content-length', 'chunked']
    content_length: int | None
    target_form: RequestTargetForm


async def _read_line(reader: StreamReaderLike) -> bytes:
    try:
        return await reader.readuntil(b"\r\n")
    except asyncio.IncompleteReadError as exc:
        raise ProtocolError('unexpected EOF while reading HTTP/1.1 body') from exc


async def _readexactly(reader: StreamReaderLike, amount: int) -> bytes:
    try:
        return await reader.readexactly(amount)
    except asyncio.IncompleteReadError as exc:
        raise ProtocolError('unexpected EOF while reading HTTP/1.1 body') from exc


async def _read_request_head_until_terminator(
    reader: StreamReaderLike,
    *,
    limit: int,
    buffer_size: int,
) -> bytes:
    limited_readuntil = getattr(reader, 'readuntil_limited', None)
    if callable(limited_readuntil):
        try:
            return await limited_readuntil(b"\r\n\r\n", limit=limit, read_chunk_size=buffer_size)
        except TypeError:
            return await limited_readuntil(b"\r\n\r\n", limit=limit)
    head = await reader.readuntil(b"\r\n\r\n")
    if len(head) > limit:
        raise asyncio.LimitOverrunError('request head exceeds configured HTTP/1.1 request-head limit', consumed=len(head))
    return head


async def _consume_chunked_trailers(reader: StreamReaderLike) -> None:
    while True:
        trailer = await _read_line(reader)
        if trailer == b"\r\n":
            return
        if trailer[:1] in {b' ', b'\t'}:
            raise ProtocolError('obsolete line folding is not supported')
        if b':' not in trailer[:-2]:
            raise ProtocolError('malformed chunk trailer line')
        name, value = trailer[:-2].split(b':', 1)
        _validate_header_name(name.strip().lower())
        _validate_header_value(value.strip())


async def _read_chunked_body(reader: StreamReaderLike, *, max_body_size: int) -> bytes:
    parts: list[bytes] = []
    total = 0
    while True:
        line = await _read_line(reader)
        size_token = line[:-2].split(b';', 1)[0].strip()
        try:
            size = int(size_token, 16)
        except ValueError as exc:
            raise ProtocolError('invalid chunk size') from exc
        if size < 0:
            raise ProtocolError('invalid chunk size')
        if size == 0:
            await _consume_chunked_trailers(reader)
            return b''.join(parts)
        chunk = await _readexactly(reader, size)
        terminator = await _readexactly(reader, 2)
        if terminator != b"\r\n":
            raise ProtocolError('invalid chunk terminator')
        total += size
        if total > max_body_size:
            raise ProtocolError('request body exceeds configured max_body_size')
        parts.append(chunk)



def _parse_request_target(method: str, target: str) -> tuple[str, bytes, bytes, RequestTargetForm]:
    method_upper = method.upper()
    if target == '*':
        if method_upper != 'OPTIONS':
            raise ProtocolError('asterisk-form request-target is only valid for OPTIONS')
        return '*', b'*', b'', 'asterisk'

    if method_upper == 'CONNECT':
        if '://' in target or '/' in target or '?' in target or '#' in target or not target:
            raise ProtocolError('invalid authority-form request-target')
        return target, target.encode('ascii'), b'', 'authority'

    if target.startswith('http://') or target.startswith('https://'):
        split = urlsplit(target)
        if not split.scheme or not split.netloc:
            raise ProtocolError('invalid absolute-form request-target')
        path = split.path or '/'
        return path, path.encode('utf-8'), split.query.encode('ascii'), 'absolute'

    if not target.startswith('/'):
        raise ProtocolError('invalid origin-form request-target')
    split = urlsplit(target)
    path = split.path or '/'
    return path, path.encode('utf-8'), split.query.encode('ascii'), 'origin'



def _parse_transfer_encoding(headers: list[tuple[bytes, bytes]]) -> Literal['none', 'chunked']:
    codings: list[bytes] = []
    for key, value in headers:
        if key != b'transfer-encoding':
            continue
        for part in value.split(b','):
            token = part.strip().lower()
            if token:
                codings.append(token)
    if not codings:
        return 'none'
    if codings.count(b'chunked') > 1:
        raise ProtocolError('chunked transfer-encoding must not be repeated')
    if b'chunked' in codings and codings[-1] != b'chunked':
        raise ProtocolError('chunked transfer-encoding must be final')
    unsupported = [coding for coding in codings if coding not in {b'chunked', b'identity'}]
    if unsupported:
        raise UnsupportedFeature('unsupported transfer-encoding')
    if codings and codings[-1] == b'chunked' and any(coding not in {b'chunked', b'identity'} for coding in codings[:-1]):
        raise UnsupportedFeature('unsupported transfer-encoding')
    if any(coding != b'identity' for coding in codings[:-1]):
        raise UnsupportedFeature('unsupported transfer-encoding')
    return 'chunked' if codings[-1] == b'chunked' else 'none'



def _parse_request_head_bytes(head: bytes) -> ParsedRequestHead | None:
    if not head:
        return None
    lines = head.split(b"\r\n")
    if not lines or not lines[0]:
        return None

    request_line = lines[0]
    parts = request_line.split(b' ', 2)
    if len(parts) != 3:
        raise ProtocolError('invalid HTTP request line')

    method_b, target_b, version_b = parts
    if not version_b.startswith(b'HTTP/'):
        raise ProtocolError('invalid HTTP version token')

    if not _is_token(method_b):
        raise ProtocolError('invalid HTTP method token')

    try:
        method = method_b.decode('ascii', 'strict')
        target = target_b.decode('ascii', 'strict')
        http_version = version_b.removeprefix(b'HTTP/').decode('ascii', 'strict')
    except UnicodeDecodeError as exc:
        raise ProtocolError('request line is not valid ASCII') from exc

    if http_version not in {'1.0', '1.1'}:
        raise ProtocolError('unsupported HTTP version')

    path, raw_path, query_string, target_form = _parse_request_target(method, target)

    headers: list[tuple[bytes, bytes]] = []
    content_length: int | None = None
    host_values: list[bytes] = []
    for raw_line in lines[1:]:
        if raw_line == b'':
            continue
        if raw_line[:1] in {b' ', b'\t'}:
            raise ProtocolError('obsolete line folding is not supported')
        try:
            key, value = raw_line.split(b':', 1)
        except ValueError as exc:
            raise ProtocolError('malformed header line') from exc
        key = key.strip().lower()
        value = value.strip()
        _validate_header_name(key)
        _validate_header_value(value)
        headers.append((key, value))
        if key == b'content-length':
            try:
                new_len = int(value.decode('ascii'))
            except ValueError as exc:
                raise ProtocolError('invalid Content-Length header') from exc
            if new_len < 0:
                raise ProtocolError('invalid Content-Length header')
            if content_length is None:
                content_length = new_len
            elif content_length != new_len:
                raise ProtocolError('conflicting Content-Length headers')
        elif key == b'host':
            host_values.append(value)

    if http_version == '1.1':
        if len(host_values) != 1 or not host_values[0]:
            raise ProtocolError('HTTP/1.1 requests must include exactly one Host header')

    transfer_encoding = _parse_transfer_encoding(headers)
    if transfer_encoding == 'chunked' and content_length is not None:
        raise ProtocolError('request cannot specify both Content-Length and chunked transfer-encoding')

    body_kind: Literal['none', 'content-length', 'chunked']
    if transfer_encoding == 'chunked':
        body_kind = 'chunked'
    elif content_length:
        body_kind = 'content-length'
    else:
        body_kind = 'none'

    return ParsedRequestHead(
        method=method,
        target=target,
        path=path,
        raw_path=raw_path,
        query_string=query_string,
        http_version=http_version,
        headers=headers,
        keep_alive=keep_alive_for_request(http_version, headers),
        expect_continue=expect_continue(headers) and body_kind != 'none',
        websocket_upgrade=(
            method.upper() == 'GET'
            and header_contains_token(headers, b'connection', b'upgrade')
            and header_contains_token(headers, b'upgrade', b'websocket')
        ),
        body_kind=body_kind,
        content_length=content_length,
        target_form=target_form,
    )


async def read_http11_request_head(
    reader: StreamReaderLike,
    *,
    max_body_size: int = 16 * 1024 * 1024,
    max_header_size: int = 64 * 1024,
    max_incomplete_event_size: int | None = None,
    buffer_size: int = 64 * 1024,
) -> ParsedRequestHead | None:
    request_head_limit = max_header_size if max_incomplete_event_size is None else min(max_header_size, max_incomplete_event_size)
    try:
        head = await _read_request_head_until_terminator(
            reader,
            limit=request_head_limit,
            buffer_size=buffer_size,
        )
    except asyncio.IncompleteReadError as exc:
        if exc.partial == b'':
            return None
        raise ProtocolError('unexpected EOF while reading request head') from exc
    except asyncio.LimitOverrunError as exc:
        raise ProtocolError('request head exceeds configured HTTP/1.1 request-head limit') from exc

    if not head:
        return None
    if len(head) > request_head_limit:
        raise ProtocolError('request head exceeds configured HTTP/1.1 request-head limit')
    if len(head) > max_header_size:
        raise ProtocolError('request head exceeds configured max_header_size')

    parsed = _parse_request_head_bytes(head)
    if parsed is None:
        return None
    if parsed.content_length is not None and parsed.content_length > max_body_size:
        raise ProtocolError('request body exceeds configured max_body_size')
    return parsed


HTTP11_REQUEST_HEAD_ERROR_MATRIX: tuple[dict[str, object], ...] = (
    {
        'case': 'request_line_shape',
        'rfc': 'RFC 9112 request line',
        'trigger': 'request line must contain exactly method, target, and version tokens',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'invalid HTTP request line',
    },
    {
        'case': 'http_version_token',
        'rfc': 'RFC 9112 version token',
        'trigger': 'version token must begin with HTTP/ and resolve to 1.0 or 1.1',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'invalid HTTP version token',
    },
    {
        'case': 'unsupported_http_version',
        'rfc': 'RFC 9112 version negotiation',
        'trigger': 'request line advertises an unsupported HTTP version',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'unsupported HTTP version',
    },
    {
        'case': 'method_token',
        'rfc': 'RFC 9110 method token syntax',
        'trigger': 'method token contains invalid bytes',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'invalid HTTP method token',
    },
    {
        'case': 'target_form_authority',
        'rfc': 'RFC 9112 CONNECT authority-form',
        'trigger': 'CONNECT target is not valid authority-form',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'invalid authority-form request-target',
    },
    {
        'case': 'target_form_absolute',
        'rfc': 'RFC 9112 absolute-form',
        'trigger': 'absolute-form target is syntactically malformed',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'invalid absolute-form request-target',
    },
    {
        'case': 'target_form_origin',
        'rfc': 'RFC 9112 origin-form',
        'trigger': 'origin-form target does not start with /',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'invalid origin-form request-target',
    },
    {
        'case': 'target_form_asterisk',
        'rfc': 'RFC 9112 asterisk-form',
        'trigger': 'asterisk-form is used with a method other than OPTIONS',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'asterisk-form request-target is only valid for OPTIONS',
    },
    {
        'case': 'header_line_folding',
        'rfc': 'RFC 9110 field line syntax',
        'trigger': 'obs-fold / line folding appears in field section',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'obsolete line folding is not supported',
    },
    {
        'case': 'header_name_and_value',
        'rfc': 'RFC 9110 field syntax',
        'trigger': 'header field name or value contains forbidden octets',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'invalid header field',
    },
    {
        'case': 'content_length_conflict',
        'rfc': 'RFC 9112 message body length',
        'trigger': 'multiple Content-Length values disagree or are negative',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'Content-Length',
    },
    {
        'case': 'host_header_requirements',
        'rfc': 'RFC 9112 Host requirements',
        'trigger': 'HTTP/1.1 request does not include exactly one non-empty Host header',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'must include exactly one Host header',
    },
    {
        'case': 'transfer_encoding_chain',
        'rfc': 'RFC 9112 transfer-coding',
        'trigger': 'chunked is repeated, not final, or appears with an unsupported chain',
        'expected_exception': 'ProtocolError|UnsupportedFeature',
        'message_fragment': 'transfer-encoding',
    },
    {
        'case': 'content_length_and_chunked_conflict',
        'rfc': 'RFC 9112 message body length',
        'trigger': 'Content-Length appears with chunked transfer-encoding',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'both Content-Length and chunked transfer-encoding',
    },
    {
        'case': 'chunked_body_syntax',
        'rfc': 'RFC 9112 chunked coding',
        'trigger': 'chunk size, terminator, or trailers are malformed',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'chunk',
    },
    {
        'case': 'size_limits',
        'rfc': 'RFC 9112 implementation limits',
        'trigger': 'request head or body exceeds configured limits',
        'expected_exception': 'ProtocolError',
        'message_fragment': 'configured max_',
    },
)


def http11_request_head_error_matrix() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in HTTP11_REQUEST_HEAD_ERROR_MATRIX)


async def read_http11_request(
    reader: StreamReaderLike,
    *,
    max_body_size: int = 16 * 1024 * 1024,
    max_header_size: int = 64 * 1024,
) -> ParsedRequest | None:
    parsed = await read_http11_request_head(
        reader,
        max_body_size=max_body_size,
        max_header_size=max_header_size,
    )
    if parsed is None:
        return None

    body = b''
    if parsed.body_kind == 'chunked':
        body = await _read_chunked_body(reader, max_body_size=max_body_size)
    elif parsed.body_kind == 'content-length':
        assert parsed.content_length is not None
        body = await _readexactly(reader, parsed.content_length)

    return ParsedRequest(
        method=parsed.method,
        target=parsed.target,
        path=parsed.path,
        raw_path=parsed.raw_path,
        query_string=parsed.query_string,
        http_version=parsed.http_version,
        headers=parsed.headers,
        body=body,
        keep_alive=parsed.keep_alive,
        expect_continue=parsed.expect_continue,
        websocket_upgrade=parsed.websocket_upgrade,
    )
