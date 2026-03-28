from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from tigrcorn.asgi.send import FileBodySegment, MemoryBodySegment
from tigrcorn.http.conditional import parse_http_date
from tigrcorn.http.etag import parse_entity_tag, strong_compare
from tigrcorn.protocols.http1.serializer import response_allows_body
from tigrcorn.utils.headers import append_if_missing, get_header, replace_header


HeaderList = list[tuple[bytes, bytes]]


@dataclass(frozen=True, slots=True)
class ByteRange:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class RangeEvaluation:
    status: int
    headers: HeaderList
    body: bytes
    applied: bool = False
    unsatisfied: bool = False


@dataclass(frozen=True, slots=True)
class FileRangePlan:
    status: int
    headers: HeaderList
    body_length: int
    parts: tuple[ByteRange, ...] = ()
    boundary: bytes | None = None
    applied: bool = False
    unsatisfied: bool = False


def parse_range_header(value: bytes | str | None, *, resource_length: int) -> list[ByteRange] | None:
    if value is None:
        return None
    raw = value.decode('latin1') if isinstance(value, bytes) else value
    unit, sep, spec = raw.partition('=')
    if sep != '=' or unit.strip().lower() != 'bytes':
        return None
    ranges: list[ByteRange] = []
    for part in spec.split(','):
        token = part.strip()
        if not token or '-' not in token:
            return None
        start_raw, end_raw = token.split('-', 1)
        if not start_raw:
            try:
                suffix_length = int(end_raw)
            except ValueError:
                return None
            if suffix_length <= 0:
                return None
            if resource_length <= 0:
                continue
            start = max(resource_length - suffix_length, 0)
            end = resource_length - 1
        else:
            try:
                start = int(start_raw)
            except ValueError:
                return None
            if start < 0:
                return None
            if not end_raw:
                if start >= resource_length:
                    continue
                end = resource_length - 1
            else:
                try:
                    end = int(end_raw)
                except ValueError:
                    return None
                if end < 0 or start > end:
                    return None
                if start >= resource_length:
                    continue
                end = min(end, resource_length - 1)
        if start > end:
            continue
        ranges.append(ByteRange(start, end))
    if not ranges:
        return []
    return ranges


def _if_range_allows_range(request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...], response_headers: HeaderList) -> bool:
    if_range_raw = get_header(request_headers, b'if-range')
    if if_range_raw is None:
        return True
    if b'"' in if_range_raw:
        current = parse_entity_tag(get_header(response_headers, b'etag'))
        provided = parse_entity_tag(if_range_raw)
        return strong_compare(current, provided)
    current_last_modified = parse_http_date(get_header(response_headers, b'last-modified'))
    provided_date = parse_http_date(if_range_raw)
    if current_last_modified is None or provided_date is None:
        return False
    return current_last_modified <= provided_date


def _multipart_boundary_for_ranges(*, total_length: int, response_headers: HeaderList) -> bytes:
    seed = (get_header(response_headers, b'etag') or b'') + b':' + str(total_length).encode('ascii')
    return f'tigrcorn-{hashlib.blake2s(seed, digest_size=8).hexdigest()}'.encode('ascii')


def _multipart_body(ranges: list[ByteRange], body: bytes, *, content_type: bytes | None) -> tuple[bytes, bytes]:
    boundary = _multipart_boundary_for_ranges(total_length=len(body), response_headers=[(b'etag', hashlib.blake2s(body, digest_size=8).hexdigest().encode('ascii'))])
    parts: list[bytes] = []
    total_length = len(body)
    for item in ranges:
        part_headers = [b'--' + boundary]
        if content_type is not None:
            part_headers.append(b'Content-Type: ' + content_type)
        part_headers.append(b'Content-Range: bytes ' + f'{item.start}-{item.end}/{total_length}'.encode('ascii'))
        parts.append(b'\r\n'.join(part_headers) + b'\r\n\r\n' + body[item.start : item.end + 1] + b'\r\n')
    parts.append(b'--' + boundary + b'--\r\n')
    return boundary, b''.join(parts)


def _multipart_part_prefix(item: ByteRange, *, total_length: int, boundary: bytes, content_type: bytes | None) -> bytes:
    lines = [b'--' + boundary]
    if content_type is not None:
        lines.append(b'Content-Type: ' + content_type)
    lines.append(b'Content-Range: bytes ' + f'{item.start}-{item.end}/{total_length}'.encode('ascii'))
    return b'\r\n'.join(lines) + b'\r\n\r\n'


def _multipart_total_length(
    ranges: tuple[ByteRange, ...],
    *,
    total_length: int,
    boundary: bytes,
    content_type: bytes | None,
) -> int:
    size = 0
    for item in ranges:
        size += len(_multipart_part_prefix(item, total_length=total_length, boundary=boundary, content_type=content_type))
        size += (item.end - item.start + 1)
        size += 2  # trailing CRLF
    size += len(b'--' + boundary + b'--\r\n')
    return size


def plan_file_byte_ranges(
    *,
    method: str,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: HeaderList,
    resource_length: int,
    status: int,
) -> FileRangePlan:
    headers = [(bytes(name).lower(), bytes(value)) for name, value in response_headers]
    if method.upper() not in {'GET', 'HEAD'}:
        return FileRangePlan(status=status, headers=headers, body_length=resource_length)
    if status != 200 or not response_allows_body(status):
        return FileRangePlan(status=status, headers=headers, body_length=resource_length)
    if get_header(headers, b'content-encoding') is not None:
        return FileRangePlan(status=status, headers=headers, body_length=resource_length)
    append_if_missing(headers, b'accept-ranges', b'bytes')
    range_header = get_header(request_headers, b'range')
    if range_header is None:
        return FileRangePlan(status=status, headers=headers, body_length=resource_length)
    if not _if_range_allows_range(request_headers, headers):
        return FileRangePlan(status=status, headers=headers, body_length=resource_length)

    resolved = parse_range_header(range_header, resource_length=resource_length)
    if resolved is None:
        return FileRangePlan(status=status, headers=headers, body_length=resource_length)
    if resolved == []:
        headers = replace_header(headers, b'content-range', f'bytes */{resource_length}'.encode('ascii'))
        headers = replace_header(headers, b'content-length', b'0')
        return FileRangePlan(status=416, headers=headers, body_length=0, unsatisfied=True)

    headers = [(name, value) for name, value in headers if name not in {b'content-range', b'content-length'}]
    parts = tuple(resolved)
    if len(parts) == 1:
        item = parts[0]
        part_length = item.end - item.start + 1
        headers.append((b'content-range', f'bytes {item.start}-{item.end}/{resource_length}'.encode('ascii')))
        headers.append((b'content-length', str(part_length).encode('ascii')))
        return FileRangePlan(status=206, headers=headers, body_length=part_length, parts=parts, applied=True)

    boundary = _multipart_boundary_for_ranges(total_length=resource_length, response_headers=headers)
    original_content_type = get_header(headers, b'content-type')
    headers = replace_header(headers, b'content-type', b'multipart/byteranges; boundary=' + boundary)
    multipart_length = _multipart_total_length(parts, total_length=resource_length, boundary=boundary, content_type=original_content_type)
    headers.append((b'content-length', str(multipart_length).encode('ascii')))
    return FileRangePlan(status=206, headers=headers, body_length=multipart_length, parts=parts, boundary=boundary, applied=True)


def build_file_range_segments(
    *,
    path: str | Path,
    plan: FileRangePlan,
    total_length: int,
    source_content_type: bytes | None = None,
) -> tuple[MemoryBodySegment | FileBodySegment, ...]:
    source_path = str(path)
    if not plan.applied or not plan.parts:
        return (FileBodySegment(source_path, 0, total_length),)
    if len(plan.parts) == 1:
        item = plan.parts[0]
        return (FileBodySegment(source_path, item.start, item.end - item.start + 1),)
    assert plan.boundary is not None
    segments: list[MemoryBodySegment | FileBodySegment] = []
    for item in plan.parts:
        segments.append(
            MemoryBodySegment(
                _multipart_part_prefix(
                    item,
                    total_length=total_length,
                    boundary=plan.boundary,
                    content_type=source_content_type,
                )
            )
        )
        segments.append(FileBodySegment(source_path, item.start, item.end - item.start + 1))
        segments.append(MemoryBodySegment(b'\r\n'))
    segments.append(MemoryBodySegment(b'--' + plan.boundary + b'--\r\n'))
    return tuple(segments)


def apply_byte_ranges(
    *,
    method: str,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: HeaderList,
    body: bytes,
    status: int,
) -> RangeEvaluation:
    headers = [(bytes(name).lower(), bytes(value)) for name, value in response_headers]
    if method.upper() not in {'GET', 'HEAD'}:
        return RangeEvaluation(status=status, headers=headers, body=body)
    if status != 200 or not response_allows_body(status):
        return RangeEvaluation(status=status, headers=headers, body=body)
    if get_header(headers, b'content-encoding') is not None:
        return RangeEvaluation(status=status, headers=headers, body=body)
    append_if_missing(headers, b'accept-ranges', b'bytes')
    range_header = get_header(request_headers, b'range')
    if range_header is None:
        return RangeEvaluation(status=status, headers=headers, body=body)
    if not _if_range_allows_range(request_headers, headers):
        return RangeEvaluation(status=status, headers=headers, body=body)

    resolved = parse_range_header(range_header, resource_length=len(body))
    if resolved is None:
        return RangeEvaluation(status=status, headers=headers, body=body)
    if resolved == []:
        headers = replace_header(headers, b'content-range', f'bytes */{len(body)}'.encode('ascii'))
        headers = replace_header(headers, b'content-length', b'0')
        return RangeEvaluation(status=416, headers=headers, body=b'', unsatisfied=True)

    headers = [(name, value) for name, value in headers if name not in {b'content-range', b'content-length'}]
    if len(resolved) == 1:
        item = resolved[0]
        partial = body[item.start : item.end + 1]
        headers.append((b'content-range', f'bytes {item.start}-{item.end}/{len(body)}'.encode('ascii')))
        headers.append((b'content-length', str(len(partial)).encode('ascii')))
        return RangeEvaluation(status=206, headers=headers, body=partial, applied=True)

    boundary = _multipart_boundary_for_ranges(total_length=len(body), response_headers=headers)
    parts: list[bytes] = []
    content_type = get_header(headers, b'content-type')
    for item in resolved:
        parts.append(_multipart_part_prefix(item, total_length=len(body), boundary=boundary, content_type=content_type))
        parts.append(body[item.start : item.end + 1])
        parts.append(b'\r\n')
    parts.append(b'--' + boundary + b'--\r\n')
    multipart = b''.join(parts)
    headers = replace_header(headers, b'content-type', b'multipart/byteranges; boundary=' + boundary)
    headers.append((b'content-length', str(len(multipart)).encode('ascii')))
    return RangeEvaluation(status=206, headers=headers, body=multipart, applied=True)


__all__ = [
    'ByteRange',
    'FileRangePlan',
    'build_file_range_segments',
    'RangeEvaluation',
    'apply_byte_ranges',
    'parse_range_header',
    'plan_file_byte_ranges',
]
