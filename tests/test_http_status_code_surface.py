from __future__ import annotations

import pytest

from tigrcorn.http.entity import finalize_response_content_length
from tigrcorn.http.range import apply_byte_ranges
from tigrcorn.protocols.http1.serializer import (
    response_allows_body,
    serialize_http11_response_whole,
)


FIRST_CLASS_STATUS_PHRASES = {
    100: b"Continue",
    101: b"Switching Protocols",
    103: b"Early Hints",
    200: b"OK",
    201: b"Created",
    202: b"Accepted",
    204: b"No Content",
    206: b"Partial Content",
    301: b"Moved Permanently",
    302: b"Found",
    304: b"Not Modified",
    307: b"Temporary Redirect",
    308: b"Permanent Redirect",
    400: b"Bad Request",
    401: b"Unauthorized",
    402: b"Payment Required",
    403: b"Forbidden",
    404: b"Not Found",
    405: b"Method Not Allowed",
    406: b"Not Acceptable",
    408: b"Request Timeout",
    413: b"Content Too Large",
    416: b"Range Not Satisfiable",
    421: b"Misdirected Request",
    426: b"Upgrade Required",
    431: b"Request Header Fields Too Large",
    500: b"Internal Server Error",
    502: b"Bad Gateway",
    503: b"Service Unavailable",
    504: b"Gateway Timeout",
}


@pytest.mark.parametrize(("status", "phrase"), sorted(FIRST_CLASS_STATUS_PHRASES.items()))
def test_first_class_http_status_codes_have_wire_reason_phrases(status: int, phrase: bytes) -> None:
    response = serialize_http11_response_whole(
        status=status,
        headers=[],
        body=b"payload",
        keep_alive=False,
        include_date_header=False,
    )

    assert response.startswith(b"HTTP/1.1 " + str(status).encode("ascii") + b" " + phrase + b"\r\n")
    if response_allows_body(status):
        assert response.endswith(b"\r\n\r\npayload")
    else:
        assert response.endswith(b"\r\n\r\n")
        assert not response.endswith(b"\r\n\r\npayload")


@pytest.mark.parametrize("status", [307, 308, 402, 408, 431, 502, 504])
def test_first_class_final_statuses_receive_content_length(status: int) -> None:
    headers = finalize_response_content_length(
        method="GET",
        status=status,
        headers=[],
        body_length=7,
    )

    assert (b"content-length", b"7") in headers


def test_partial_content_and_unsatisfied_range_statuses_are_runtime_reachable() -> None:
    partial = apply_byte_ranges(
        method="GET",
        request_headers=[(b"range", b"bytes=1-3")],
        response_headers=[],
        body=b"abcdef",
        status=200,
    )
    unsatisfied = apply_byte_ranges(
        method="GET",
        request_headers=[(b"range", b"bytes=99-100")],
        response_headers=[],
        body=b"abcdef",
        status=200,
    )

    assert partial.status == 206
    assert partial.body == b"bcd"
    assert (b"content-range", b"bytes 1-3/6") in partial.headers
    assert unsatisfied.status == 416
    assert (b"content-range", b"bytes */6") in unsatisfied.headers
