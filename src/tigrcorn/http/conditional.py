from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from tigrcorn.http.etag import EntityTag, EntityTagList, parse_entity_tag, parse_entity_tag_list, strong_compare, weak_compare
from tigrcorn.utils.headers import get_header


HeaderList = list[tuple[bytes, bytes]]
_PRECONDITION_FAILED_BODY = b'precondition failed'


@dataclass(frozen=True, slots=True)
class ConditionalEvaluation:
    status: int
    headers: HeaderList
    body: bytes
    not_modified: bool = False
    precondition_failed: bool = False


def parse_http_date(value: bytes | str | None) -> datetime | None:
    if value is None:
        return None
    try:
        dt = parsedate_to_datetime(value.decode('latin1') if isinstance(value, bytes) else value)
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(microsecond=0)


def _current_validators(headers: HeaderList) -> tuple[EntityTag | None, bytes | None, datetime | None, bytes | None]:
    etag_raw = get_header(headers, b'etag')
    last_modified_raw = get_header(headers, b'last-modified')
    return parse_entity_tag(etag_raw), etag_raw, parse_http_date(last_modified_raw), last_modified_raw


def _build_precondition_failed_headers(current_etag_raw: bytes | None, last_modified_raw: bytes | None) -> HeaderList:
    headers: HeaderList = [(b'content-type', b'text/plain; charset=utf-8')]
    if current_etag_raw is not None:
        headers.append((b'etag', current_etag_raw))
    if last_modified_raw is not None:
        headers.append((b'last-modified', last_modified_raw))
    return headers


def _matches_if_match(condition: EntityTagList | None, current: EntityTag | None) -> bool:
    if condition is None:
        return True
    if condition.any_value:
        return current is not None
    return any(strong_compare(candidate, current) for candidate in condition.items)


def _matches_if_none_match(condition: EntityTagList | None, current: EntityTag | None) -> bool:
    if condition is None:
        return False
    if condition.any_value:
        return current is not None
    return any(weak_compare(candidate, current) for candidate in condition.items)


def apply_conditional_request(
    *,
    method: str,
    request_headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    response_headers: HeaderList,
    body: bytes,
    status: int,
) -> ConditionalEvaluation:
    method_upper = method.upper()
    headers = [(bytes(name).lower(), bytes(value)) for name, value in response_headers]
    current_etag, current_etag_raw, last_modified, last_modified_raw = _current_validators(headers)

    if_match_raw = get_header(request_headers, b'if-match')
    if if_match_raw is not None:
        condition = parse_entity_tag_list(if_match_raw)
        if condition is not None and not _matches_if_match(condition, current_etag):
            return ConditionalEvaluation(
                status=412,
                headers=_build_precondition_failed_headers(current_etag_raw, last_modified_raw),
                body=_PRECONDITION_FAILED_BODY,
                precondition_failed=True,
            )

    if_unmodified_since_raw = get_header(request_headers, b'if-unmodified-since')
    if if_unmodified_since_raw is not None and last_modified is not None:
        date_value = parse_http_date(if_unmodified_since_raw)
        if date_value is not None and last_modified > date_value:
            return ConditionalEvaluation(
                status=412,
                headers=_build_precondition_failed_headers(current_etag_raw, last_modified_raw),
                body=_PRECONDITION_FAILED_BODY,
                precondition_failed=True,
            )

    if_none_match_raw = get_header(request_headers, b'if-none-match')
    if if_none_match_raw is not None:
        condition = parse_entity_tag_list(if_none_match_raw)
        if condition is not None and _matches_if_none_match(condition, current_etag):
            if method_upper in {'GET', 'HEAD'}:
                return ConditionalEvaluation(status=304, headers=headers, body=b'', not_modified=True)
            return ConditionalEvaluation(
                status=412,
                headers=_build_precondition_failed_headers(current_etag_raw, last_modified_raw),
                body=_PRECONDITION_FAILED_BODY,
                precondition_failed=True,
            )

    if if_none_match_raw is None and method_upper in {'GET', 'HEAD'} and last_modified is not None:
        if_modified_since_raw = get_header(request_headers, b'if-modified-since')
        if if_modified_since_raw is not None:
            date_value = parse_http_date(if_modified_since_raw)
            if date_value is not None and last_modified <= date_value:
                return ConditionalEvaluation(status=304, headers=headers, body=b'', not_modified=True)

    return ConditionalEvaluation(status=status, headers=headers, body=body)


__all__ = ['ConditionalEvaluation', 'apply_conditional_request', 'parse_http_date']
