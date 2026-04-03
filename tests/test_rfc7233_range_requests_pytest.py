from __future__ import annotations

from email.utils import formatdate
from pathlib import Path
import tempfile

from tigrcorn.http.range import apply_byte_ranges
from tigrcorn.static import StaticFilesApp
from tigrcorn.utils.headers import get_header


def test_rfc7233_byte_range_engine_supports_single_multi_and_unsatisfied_ranges() -> None:
    body = b'hello world'
    headers = [(b'content-type', b'text/plain')]

    single = apply_byte_ranges(
        method='GET',
        request_headers=[(b'range', b'bytes=0-4')],
        response_headers=headers,
        body=body,
        status=200,
    )
    assert single.status == 206
    assert single.body == b'hello'
    assert get_header(single.headers, b'content-range') == b'bytes 0-4/11'

    multi = apply_byte_ranges(
        method='GET',
        request_headers=[(b'range', b'bytes=0-1,6-10')],
        response_headers=headers,
        body=body,
        status=200,
    )
    assert multi.status == 206
    assert b'multipart/byteranges' in (get_header(multi.headers, b'content-type') or b'')
    assert b'Content-Range: bytes 0-1/11' in multi.body
    assert b'Content-Range: bytes 6-10/11' in multi.body

    unsatisfied = apply_byte_ranges(
        method='GET',
        request_headers=[(b'range', b'bytes=40-50')],
        response_headers=headers,
        body=body,
        status=200,
    )
    assert unsatisfied.status == 416
    assert get_header(unsatisfied.headers, b'content-range') == b'bytes */11'


def test_rfc7233_if_range_honors_matching_etag_and_rejects_stale_date() -> None:
    body = b'hello world'
    headers = [
        (b'content-type', b'text/plain'),
        (b'etag', b'"tag-1"'),
        (b'last-modified', formatdate(1_700_000_000, usegmt=True).encode('ascii')),
    ]
    accepted = apply_byte_ranges(
        method='GET',
        request_headers=[(b'range', b'bytes=0-4'), (b'if-range', b'"tag-1"')],
        response_headers=headers,
        body=body,
        status=200,
    )
    assert accepted.status == 206
    rejected = apply_byte_ranges(
        method='GET',
        request_headers=[(b'range', b'bytes=0-4'), (b'if-range', formatdate(1_699_999_000, usegmt=True).encode('ascii'))],
        response_headers=headers,
        body=body,
        status=200,
    )
    assert rejected.status == 200
    assert rejected.body == body


async def _receive() -> dict:
    return {'type': 'http.request', 'body': b'', 'more_body': False}


def test_rfc7233_static_files_support_range_paths() -> None:
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hello.txt').write_text('hello world', encoding='utf-8')
            app = StaticFilesApp(root)
            await app({'type': 'http', 'method': 'GET', 'path': '/hello.txt', 'headers': [(b'range', b'bytes=0-4')]}, _receive, send)
            assert sent[0]['status'] == 206
            headers = dict(sent[0]['headers'])
            assert headers[b'content-range'] == b'bytes 0-4/11'
            assert sent[1]['body'] == b'hello'

    import asyncio
    asyncio.run(run())
