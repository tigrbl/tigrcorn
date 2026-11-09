from __future__ import annotations

from email.utils import formatdate
from pathlib import Path
import tempfile

from tigrcorn.http.conditional import apply_conditional_request
from tigrcorn.http.etag import generate_entity_tag
from tigrcorn.static import StaticFilesApp


def test_rfc7232_conditional_engine_evaluates_entity_tags_and_dates() -> None:
    etag = generate_entity_tag(b'payload')
    last_modified = formatdate(1_700_000_000, usegmt=True).encode('ascii')

    not_modified = apply_conditional_request(
        method='GET',
        request_headers=[(b'if-none-match', etag)],
        response_headers=[(b'etag', etag), (b'last-modified', last_modified)],
        body=b'payload',
        status=200,
    )
    assert not_modified.status == 304
    assert not_modified.body == b''

    precondition_failed = apply_conditional_request(
        method='PUT',
        request_headers=[(b'if-match', b'"other"')],
        response_headers=[(b'etag', etag), (b'last-modified', last_modified)],
        body=b'payload',
        status=200,
    )
    assert precondition_failed.status == 412

    ims = apply_conditional_request(
        method='GET',
        request_headers=[(b'if-modified-since', last_modified)],
        response_headers=[(b'last-modified', last_modified)],
        body=b'payload',
        status=200,
    )
    assert ims.status == 304

    ius = apply_conditional_request(
        method='GET',
        request_headers=[(b'if-unmodified-since', formatdate(1_699_999_000, usegmt=True).encode('ascii'))],
        response_headers=[(b'last-modified', last_modified)],
        body=b'payload',
        status=200,
    )
    assert ius.status == 412


async def _receive() -> dict:
    return {'type': 'http.request', 'body': b'', 'more_body': False}


def test_rfc7232_static_files_supports_not_modified_paths() -> None:
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hello.txt').write_text('hello world', encoding='utf-8')
            app = StaticFilesApp(root)
            await app({'type': 'http', 'method': 'GET', 'path': '/hello.txt', 'headers': []}, _receive, send)
            headers = dict(sent[0]['headers'])
            etag = headers[b'etag']
            sent.clear()
            await app({'type': 'http', 'method': 'GET', 'path': '/hello.txt', 'headers': [(b'if-none-match', etag)]}, _receive, send)
            assert sent[0]['status'] == 304
            assert sent[1]['body'] == b''

    import asyncio
    asyncio.run(run())
