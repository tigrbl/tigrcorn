from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from tigrcorn.asgi.errors import ASGIProtocolError
from tigrcorn.asgi.send import materialize_response_body_segments, normalize_response_pathsend_segment
from tigrcorn.config.origin_surface import ORIGIN_CONTRACT, ORIGIN_NEGATIVE_CORPUS, PATH_RESOLUTION_CASES
from tigrcorn.static import StaticFilesApp
from tools.cert.origin_contract import generate as generate_origin_contract


async def _receive() -> dict:
    return {'type': 'http.request', 'body': b'', 'more_body': False}


@contextmanager
def _workspace_tempdir():
    with tempfile.TemporaryDirectory(dir='.') as tmp:
        yield Path(tmp).resolve()


class Phase5OriginContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_origin_contract_matches_metadata(self):
        generate_origin_contract()
        payload = json.loads(Path('docs/conformance/origin_contract.json').read_text(encoding='utf-8'))
        negatives = json.loads(Path('docs/conformance/origin_negatives.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['path_resolution'], ORIGIN_CONTRACT['path_resolution'])
        self.assertEqual(payload['http_semantics'], ORIGIN_CONTRACT['http_semantics'])
        self.assertEqual(payload['path_resolution_cases'], PATH_RESOLUTION_CASES)
        self.assertEqual(negatives['cases'], ORIGIN_NEGATIVE_CORPUS)
        self.assertIn('Parent-reference segments and backslash-separated segments are denied.', Path('docs/ops/origin.md').read_text(encoding='utf-8'))

    async def test_parent_segments_and_backslash_segments_are_denied(self):
        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        with _workspace_tempdir() as root:
            (root / 'hello.txt').write_text('hello', encoding='utf-8')
            app = StaticFilesApp(root)

            await app({'type': 'http', 'method': 'GET', 'path': '/../hello.txt', 'headers': []}, _receive, send)
            self.assertEqual(sent[0]['status'], 404)
            sent.clear()

            await app({'type': 'http', 'method': 'GET', 'path': '/%2e%2e/hello.txt', 'headers': []}, _receive, send)
            self.assertEqual(sent[0]['status'], 404)
            sent.clear()

            await app({'type': 'http', 'method': 'GET', 'path': '/dir\\..\\hello.txt', 'headers': []}, _receive, send)
            self.assertEqual(sent[0]['status'], 404)

    async def test_hidden_files_are_served_mount_relative(self):
        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        with _workspace_tempdir() as root:
            (root / '.well-known.txt').write_text('ok', encoding='utf-8')
            app = StaticFilesApp(root)
            await app({'type': 'http', 'method': 'GET', 'path': '/.well-known.txt', 'headers': []}, _receive, send)
        self.assertEqual(sent[0]['status'], 200)
        self.assertEqual(sent[1]['body'], b'ok')

    async def test_symlink_escape_is_denied_when_symlinks_are_available(self):
        if not hasattr(os, 'symlink'):
            self.skipTest('symlinks unavailable')
        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        with _workspace_tempdir() as root:
            outside = root.parent / f'{root.name}-outside.txt'
            outside.write_text('secret', encoding='utf-8')
            try:
                try:
                    os.symlink(outside, root / 'escape.txt')
                except (OSError, NotImplementedError):
                    self.skipTest('symlink creation unavailable')
                app = StaticFilesApp(root)
                await app({'type': 'http', 'method': 'GET', 'path': '/escape.txt', 'headers': []}, _receive, send)
                self.assertEqual(sent[0]['status'], 404)
            finally:
                outside.unlink(missing_ok=True)

    async def test_directory_index_and_head_parity_are_frozen(self):
        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        with _workspace_tempdir() as root:
            (root / 'docs').mkdir()
            (root / 'docs' / 'index.html').write_text('index-body', encoding='utf-8')
            app = StaticFilesApp(root)
            await app({'type': 'http', 'method': 'HEAD', 'path': '/docs/', 'headers': []}, _receive, send)
        self.assertEqual(sent[0]['status'], 200)
        headers = dict(sent[0]['headers'])
        self.assertEqual(headers[b'content-length'], b'10')
        self.assertEqual(sent[1]['body'], b'')

    async def test_pathsend_snapshots_length_when_dispatched(self):
        with _workspace_tempdir() as root:
            payload_path = root / 'payload.bin'
            payload_path.write_bytes(b'alpha')
            segment = normalize_response_pathsend_segment(str(payload_path))
            payload_path.write_bytes(b'alphabet')
            body = await materialize_response_body_segments((segment,))
        self.assertEqual(segment.count, 5)
        self.assertEqual(body, b'alpha')

    async def test_pathsend_rejects_relative_and_missing_paths(self):
        with self.assertRaises(ASGIProtocolError):
            normalize_response_pathsend_segment('relative.bin')
        with self.assertRaises(ASGIProtocolError):
            normalize_response_pathsend_segment(str(Path(tempfile.gettempdir()) / 'missing-phase5-origin.bin'))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
