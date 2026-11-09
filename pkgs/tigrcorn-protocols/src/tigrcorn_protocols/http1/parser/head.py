from __future__ import annotations

import asyncio
from typing import Literal

from tigrcorn_core.errors import ProtocolError, UnsupportedFeature
from tigrcorn_core.types import StreamReaderLike
from tigrcorn_core.utils.headers import header_contains_token
from tigrcorn_protocols.http1.keepalive import expect_continue, keep_alive_for_request

from .body import _read_request_head_until_terminator
from .models import ParsedRequestHead
from .target import _parse_request_target
from .validation import _is_token, _validate_header_name, _validate_header_value


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

    if http_version == '1.1' and (len(host_values) != 1 or not host_values[0]):
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
        head = await _read_request_head_until_terminator(reader, limit=request_head_limit, buffer_size=buffer_size)
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
    {'case': 'request_line_shape', 'rfc': 'RFC 9112 request line', 'trigger': 'request line must contain exactly method, target, and version tokens', 'expected_exception': 'ProtocolError', 'message_fragment': 'invalid HTTP request line'},
    {'case': 'http_version_token', 'rfc': 'RFC 9112 version token', 'trigger': 'version token must begin with HTTP/ and resolve to 1.0 or 1.1', 'expected_exception': 'ProtocolError', 'message_fragment': 'invalid HTTP version token'},
    {'case': 'unsupported_http_version', 'rfc': 'RFC 9112 version negotiation', 'trigger': 'request line advertises an unsupported HTTP version', 'expected_exception': 'ProtocolError', 'message_fragment': 'unsupported HTTP version'},
    {'case': 'method_token', 'rfc': 'RFC 9110 method token syntax', 'trigger': 'method token contains invalid bytes', 'expected_exception': 'ProtocolError', 'message_fragment': 'invalid HTTP method token'},
    {'case': 'target_form_authority', 'rfc': 'RFC 9112 CONNECT authority-form', 'trigger': 'CONNECT target is not valid authority-form', 'expected_exception': 'ProtocolError', 'message_fragment': 'invalid authority-form request-target'},
    {'case': 'target_form_absolute', 'rfc': 'RFC 9112 absolute-form', 'trigger': 'absolute-form target is syntactically malformed', 'expected_exception': 'ProtocolError', 'message_fragment': 'invalid absolute-form request-target'},
    {'case': 'target_form_origin', 'rfc': 'RFC 9112 origin-form', 'trigger': 'origin-form target does not start with /', 'expected_exception': 'ProtocolError', 'message_fragment': 'invalid origin-form request-target'},
    {'case': 'target_form_asterisk', 'rfc': 'RFC 9112 asterisk-form', 'trigger': 'asterisk-form is used with a method other than OPTIONS', 'expected_exception': 'ProtocolError', 'message_fragment': 'asterisk-form request-target is only valid for OPTIONS'},
    {'case': 'header_line_folding', 'rfc': 'RFC 9110 field line syntax', 'trigger': 'obs-fold / line folding appears in field section', 'expected_exception': 'ProtocolError', 'message_fragment': 'obsolete line folding is not supported'},
    {'case': 'header_name_and_value', 'rfc': 'RFC 9110 field syntax', 'trigger': 'header field name or value contains forbidden octets', 'expected_exception': 'ProtocolError', 'message_fragment': 'invalid header field'},
    {'case': 'content_length_conflict', 'rfc': 'RFC 9112 message body length', 'trigger': 'multiple Content-Length values disagree or are negative', 'expected_exception': 'ProtocolError', 'message_fragment': 'Content-Length'},
    {'case': 'host_header_requirements', 'rfc': 'RFC 9112 Host requirements', 'trigger': 'HTTP/1.1 request does not include exactly one non-empty Host header', 'expected_exception': 'ProtocolError', 'message_fragment': 'must include exactly one Host header'},
    {'case': 'transfer_encoding_chain', 'rfc': 'RFC 9112 transfer-coding', 'trigger': 'chunked is repeated, not final, or appears with an unsupported chain', 'expected_exception': 'ProtocolError|UnsupportedFeature', 'message_fragment': 'transfer-encoding'},
    {'case': 'content_length_and_chunked_conflict', 'rfc': 'RFC 9112 message body length', 'trigger': 'Content-Length appears with chunked transfer-encoding', 'expected_exception': 'ProtocolError', 'message_fragment': 'both Content-Length and chunked transfer-encoding'},
    {'case': 'chunked_body_syntax', 'rfc': 'RFC 9112 chunked coding', 'trigger': 'chunk size, terminator, or trailers are malformed', 'expected_exception': 'ProtocolError', 'message_fragment': 'chunk'},
    {'case': 'size_limits', 'rfc': 'RFC 9112 implementation limits', 'trigger': 'request head or body exceeds configured limits', 'expected_exception': 'ProtocolError', 'message_fragment': 'configured max_'},
)


def http11_request_head_error_matrix() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in HTTP11_REQUEST_HEAD_ERROR_MATRIX)
