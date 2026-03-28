from __future__ import annotations

from dataclasses import dataclass

from tigrcorn.asgi.send import BodySegment
from tigrcorn.http.conditional import apply_conditional_request
from tigrcorn.http.etag import generate_entity_tag
from tigrcorn.http.range import apply_byte_ranges, build_file_range_segments, plan_file_byte_ranges
from tigrcorn.protocols.content_coding import ContentCodingSelection, apply_http_content_coding
from tigrcorn.protocols.http1.serializer import response_allows_body
from tigrcorn.utils.headers import append_if_missing, get_header, replace_header


HeaderList = list[tuple[bytes, bytes]]


@dataclass(frozen=True, slots=True)
class EntitySemanticsResult:
    status: int
    headers: HeaderList
    body: bytes
    content_coding: ContentCodingSelection
    range_applied: bool = False
    not_modified: bool = False
    precondition_failed: bool = False
    head_response: bool = False


@dataclass(frozen=True, slots=True)
class FileBackedEntitySemanticsResult:
    status: int
    headers: HeaderList
    body: bytes
    body_segments: tuple[BodySegment, ...] = ()
    use_body_segments: bool = False
    range_applied: bool = False
    not_modified: bool = False
    precondition_failed: bool = False
    head_response: bool = False
    requires_materialization: bool = False


def _normalize_headers(headers: list[tuple[bytes, bytes]]) -> HeaderList:
    return [(bytes(name).lower(), bytes(value)) for name, value in headers]


def finalize_response_content_length(*, method: str, status: int, headers: HeaderList, body_length: int, trailers_present: bool = False) -> HeaderList:
    normalized = [(name.lower(), value) for name, value in headers if name.lower() != b'content-length']
    method_upper = method.upper()
    if status in {204} or 100 <= status < 200:
        return normalized
    if trailers_present:
        return normalized
    if status == 304:
        return normalized
    if not response_allows_body(status):
        return normalized
    normalized.append((b'content-length', str(max(int(body_length), 0)).encode('ascii')))
    if method_upper == 'HEAD':
        return normalized
    return normalized


def _maybe_generate_etag(headers: HeaderList, body: bytes, *, enabled: bool) -> HeaderList:
    if not enabled:
        return headers
    if get_header(headers, b'etag') is not None:
        return headers
    headers = list(headers)
    headers.append((b'etag', generate_entity_tag(body)))
    return headers


def _default_selection() -> ContentCodingSelection:
    return ContentCodingSelection(coding=None, identity_acceptable=True)


def should_materialize_response_body(
    *,
    method: str,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: list[tuple[bytes, bytes]],
    status: int,
    apply_content_coding: bool = True,
) -> bool:
    method_upper = method.upper()
    if method_upper == 'HEAD' or not response_allows_body(status) or status in {304} or 100 <= status < 200:
        return False
    if not apply_content_coding:
        return False
    if get_header(response_headers, b'content-encoding') is not None:
        return False
    return get_header(request_headers, b'accept-encoding') is not None


def apply_header_only_response_semantics(
    *,
    method: str,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: list[tuple[bytes, bytes]],
    status: int,
    body_length: int,
    generated_etag: bytes | None = None,
    trailers_present: bool = False,
    advertise_accept_ranges: bool = False,
) -> EntitySemanticsResult:
    method_upper = method.upper()
    headers = _normalize_headers(response_headers)
    if generated_etag is not None and get_header(headers, b'etag') is None and status not in {412, 416} and not (100 <= status < 200):
        headers = list(headers)
        headers.append((b'etag', generated_etag))

    conditional = apply_conditional_request(
        method=method_upper,
        request_headers=request_headers,
        response_headers=headers,
        body=b'',
        status=status,
    )
    status = conditional.status
    headers = conditional.headers
    body = conditional.body

    if advertise_accept_ranges and get_header(headers, b'accept-ranges') is None and status in {200, 206} and get_header(headers, b'content-encoding') is None:
        append_if_missing(headers, b'accept-ranges', b'bytes')

    content_length = len(body) if conditional.precondition_failed else int(body_length)
    headers = finalize_response_content_length(
        method=method_upper,
        status=status,
        headers=headers,
        body_length=content_length,
        trailers_present=trailers_present,
    )

    if method_upper == 'HEAD':
        return EntitySemanticsResult(
            status=status,
            headers=headers,
            body=b'',
            content_coding=_default_selection(),
            not_modified=conditional.not_modified,
            precondition_failed=conditional.precondition_failed,
            head_response=True,
        )

    return EntitySemanticsResult(
        status=status,
        headers=headers,
        body=body,
        content_coding=_default_selection(),
        not_modified=conditional.not_modified,
        precondition_failed=conditional.precondition_failed,
    )


def plan_file_backed_response_entity_semantics(
    *,
    method: str,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: list[tuple[bytes, bytes]],
    status: int,
    body_path: str,
    body_length: int,
    generated_etag: bytes | None = None,
    apply_content_coding: bool = True,
    trailers_present: bool = False,
) -> FileBackedEntitySemanticsResult:
    method_upper = method.upper()
    headers = _normalize_headers(response_headers)
    if generated_etag is not None and get_header(headers, b'etag') is None and status not in {412, 416} and not (100 <= status < 200):
        headers = list(headers)
        headers.append((b'etag', generated_etag))

    if should_materialize_response_body(
        method=method_upper,
        request_headers=request_headers,
        response_headers=headers,
        status=status,
        apply_content_coding=apply_content_coding,
    ):
        return FileBackedEntitySemanticsResult(
            status=status,
            headers=headers,
            body=b'',
            requires_materialization=True,
        )

    conditional = apply_conditional_request(
        method=method_upper,
        request_headers=request_headers,
        response_headers=headers,
        body=b'',
        status=status,
    )
    if conditional.not_modified or conditional.precondition_failed:
        precondition_body = conditional.body if not (method_upper == 'HEAD') else b''
        precondition_headers = finalize_response_content_length(
            method=method_upper,
            status=conditional.status,
            headers=conditional.headers,
            body_length=len(conditional.body),
            trailers_present=False,
        )
        return FileBackedEntitySemanticsResult(
            status=conditional.status,
            headers=precondition_headers,
            body=precondition_body,
            not_modified=conditional.not_modified,
            precondition_failed=conditional.precondition_failed,
            head_response=method_upper == 'HEAD',
        )

    plan = plan_file_byte_ranges(
        method=method_upper,
        request_headers=request_headers,
        response_headers=conditional.headers,
        resource_length=body_length,
        status=conditional.status,
    )
    headers = finalize_response_content_length(
        method=method_upper,
        status=plan.status,
        headers=plan.headers,
        body_length=plan.body_length,
        trailers_present=trailers_present,
    )

    if method_upper == 'HEAD' or not response_allows_body(plan.status) or plan.unsatisfied:
        return FileBackedEntitySemanticsResult(
            status=plan.status,
            headers=headers,
            body=b'',
            range_applied=plan.applied,
            head_response=method_upper == 'HEAD',
        )

    body_segments = build_file_range_segments(
        path=body_path,
        plan=plan,
        total_length=body_length,
        source_content_type=get_header(conditional.headers, b'content-type'),
    )
    return FileBackedEntitySemanticsResult(
        status=plan.status,
        headers=headers,
        body=b'',
        body_segments=body_segments,
        use_body_segments=True,
        range_applied=plan.applied,
    )


def apply_response_entity_semantics(
    *,
    method: str,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: list[tuple[bytes, bytes]],
    body: bytes,
    status: int,
    content_coding_policy: str = 'allowlist',
    supported_codings: tuple[str, ...] = ('br', 'gzip', 'deflate'),
    apply_content_coding: bool = True,
    generate_etag: bool = True,
    trailers_present: bool = False,
) -> EntitySemanticsResult:
    method_upper = method.upper()
    headers = _normalize_headers(response_headers)
    range_present = get_header(request_headers, b'range') is not None and method_upper in {'GET', 'HEAD'}

    if apply_content_coding and not range_present:
        status, headers, body, selection = apply_http_content_coding(
            request_headers=request_headers,
            response_headers=headers,
            body=body,
            status=status,
            policy=content_coding_policy,
            supported=supported_codings,
        )
    else:
        selection = _default_selection()

    headers = _maybe_generate_etag(headers, body, enabled=generate_etag and status not in {412, 416} and not (100 <= status < 200))

    conditional = apply_conditional_request(
        method=method_upper,
        request_headers=request_headers,
        response_headers=headers,
        body=body,
        status=status,
    )
    status = conditional.status
    headers = conditional.headers
    body = conditional.body
    range_applied = False

    if not conditional.not_modified and not conditional.precondition_failed:
        range_result = apply_byte_ranges(
            method=method_upper,
            request_headers=request_headers,
            response_headers=headers,
            body=body,
            status=status,
        )
        status = range_result.status
        headers = range_result.headers
        body = range_result.body
        range_applied = range_result.applied

    if get_header(headers, b'accept-ranges') is None and status in {200, 206} and get_header(headers, b'content-encoding') is None:
        append_if_missing(headers, b'accept-ranges', b'bytes')

    headers = finalize_response_content_length(method=method_upper, status=status, headers=headers, body_length=len(body), trailers_present=trailers_present)

    if method_upper == 'HEAD':
        return EntitySemanticsResult(
            status=status,
            headers=headers,
            body=b'',
            content_coding=selection,
            range_applied=range_applied,
            not_modified=conditional.not_modified,
            precondition_failed=conditional.precondition_failed,
            head_response=True,
        )

    return EntitySemanticsResult(
        status=status,
        headers=headers,
        body=body,
        content_coding=selection,
        range_applied=range_applied,
        not_modified=conditional.not_modified,
        precondition_failed=conditional.precondition_failed,
    )


__all__ = ['EntitySemanticsResult', 'FileBackedEntitySemanticsResult', 'apply_header_only_response_semantics', 'apply_response_entity_semantics', 'finalize_response_content_length', 'plan_file_backed_response_entity_semantics', 'should_materialize_response_body']
