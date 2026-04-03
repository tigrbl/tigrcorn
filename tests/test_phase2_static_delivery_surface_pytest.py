from __future__ import annotations

import asyncio
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tigrcorn.cli import main as cli_main
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FrameWriter, serialize_settings
from tigrcorn.protocols.http2.hpack import encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.static import StaticFilesApp, mount_static_app
from tigrcorn.transports.quic import QuicConnection

from tests.test_phase2_entity_semantics_checkpoint import (
    _read_h2_response,
    _read_http1_response,
    _start_server,
)
from tests.test_static_delivery_productionization_checkpoint import (
    _read_h3_response_with_client_progress,
)


@pytest.mark.asyncio
async def test_static_files_app_prefers_standard_pathsend_when_advertised():
    async def receive() -> dict:
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        payload = b'pathsend-static-payload'
        (root / 'blob.bin').write_bytes(payload)
        app = StaticFilesApp(root)
        scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/blob.bin',
            'headers': [],
            'extensions': {'http.response.pathsend': {}},
        }
        await app(scope, receive, send)

        assert sent[0]['type'] == 'http.response.start'
        assert sent[0]['status'] == 200
        assert sent[1]['type'] == 'http.response.pathsend'
        assert Path(sent[1]['path']).resolve(strict=False) == (root / 'blob.bin').resolve(
            strict=False
        )


@pytest.mark.asyncio
async def test_mount_static_app_routes_requests_and_preserves_fallback():
    fallback_events: list[dict] = []

    async def fallback(scope, receive, send) -> None:
        fallback_events.append(
            {
                'scope_type': scope['type'],
                'path': scope.get('path'),
                'root_path': scope.get('root_path', ''),
            }
        )
        await send(
            {
                'type': 'http.response.start',
                'status': 200,
                'headers': [(b'content-type', b'text/plain')],
            }
        )
        await send({'type': 'http.response.body', 'body': b'fallback'})

    async def receive() -> dict:
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'hello.txt').write_text('static hello', encoding='utf-8')
        app = mount_static_app(fallback, route='/assets', directory=root)

        sent_static: list[dict] = []

        async def send_static(message: dict) -> None:
            sent_static.append(message)

        await app(
            {
                'type': 'http',
                'method': 'GET',
                'path': '/assets/hello.txt',
                'raw_path': b'/assets/hello.txt',
                'headers': [],
            },
            receive,
            send_static,
        )
        assert sent_static[0]['status'] == 200
        assert sent_static[1]['type'] == 'http.response.body'
        assert sent_static[1]['body'] == b'static hello'

        sent_fallback: list[dict] = []

        async def send_fallback(message: dict) -> None:
            sent_fallback.append(message)

        await app(
            {'type': 'http', 'method': 'GET', 'path': '/api', 'raw_path': b'/api', 'headers': []},
            receive,
            send_fallback,
        )
        assert sent_fallback[0]['status'] == 200
        assert sent_fallback[1]['body'] == b'fallback'
        assert fallback_events[-1]['path'] == '/api'


@pytest.mark.asyncio
async def test_http11_pathsend_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        payload = b'http11-pathsend-payload' * 1024
        payload_path = Path(tmp) / 'payload.bin'
        payload_path.write_bytes(payload)

        async def app(scope, receive, send):
            assert 'http.response.pathsend' in scope.get('extensions', {})
            await receive()
            await send(
                {
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', b'application/octet-stream'),
                        (b'content-length', str(len(payload)).encode('ascii')),
                    ],
                }
            )
            await send({'type': 'http.response.pathsend', 'path': str(payload_path)})

        server, port = await _start_server(app, http_versions=['1.1'])
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
            await writer.drain()
            _head, headers, body = await _read_http1_response(reader)
            assert headers[b'content-length'] == str(len(payload)).encode('ascii')
            assert body == payload
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()


@pytest.mark.asyncio
async def test_http2_pathsend_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        payload = b'http2-pathsend-payload' * 2048
        payload_path = Path(tmp) / 'payload.bin'
        payload_path.write_bytes(payload)

        async def app(scope, receive, send):
            assert 'http.response.pathsend' in scope.get('extensions', {})
            await receive()
            await send(
                {
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', b'application/octet-stream'),
                        (b'content-length', str(len(payload)).encode('ascii')),
                    ],
                }
            )
            await send({'type': 'http.response.pathsend', 'path': str(payload_path)})

        server, port = await _start_server(app, http_versions=['2'])
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            headers = encode_header_block(
                [
                    (b':method', b'GET'),
                    (b':scheme', b'http'),
                    (b':path', b'/'),
                    (b':authority', b'localhost'),
                ]
            )
            frame_writer = FrameWriter()
            writer.write(frame_writer.headers(1, headers, end_stream=True))
            await writer.drain()
            response_headers, body = await _read_h2_response(reader)
            assert dict(response_headers)[b':status'] == b'200'
            assert body == payload
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()


@pytest.mark.asyncio
async def test_http3_pathsend_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        payload = b'http3-pathsend-payload' * 2048
        payload_path = Path(tmp) / 'payload.bin'
        payload_path.write_bytes(payload)

        async def app(scope, receive, send):
            assert 'http.response.pathsend' in scope.get('extensions', {})
            await receive()
            await send(
                {
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', b'application/octet-stream'),
                        (b'content-length', str(len(payload)).encode('ascii')),
                    ],
                }
            )
            await send({'type': 'http.response.pathsend', 'path': str(payload_path)})

        server, port = await _start_server(app, http_versions=['3'], transport='udp')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-pathsend')
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            target = ('127.0.0.1', port)
            sock.sendto(client.build_initial(), target)
            for _ in range(2):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            request_payload = core.get_request(0).encode_request(
                [
                    (b':method', b'GET'),
                    (b':scheme', b'https'),
                    (b':path', b'/'),
                    (b':authority', b'localhost'),
                ],
                body=b'x' * 6000,
            )
            sock.sendto(client.send_stream_data(0, request_payload, fin=True), target)
            response_headers, body = await _read_h3_response_with_client_progress(
                sock, core, client, target
            )
            assert dict(response_headers)[b':status'] == b'200'
            assert body == payload
        finally:
            sock.close()
            await server.close()


@pytest.mark.asyncio
async def test_cli_main_allows_static_only_mount_without_app_import_string():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'index.html').write_text('ok', encoding='utf-8')
        with patch('tigrcorn.cli.run_config') as run_config:
            rc = cli_main(
                [
                    '--static-path-route',
                    '/assets',
                    '--static-path-mount',
                    str(root),
                    '--static-path-expires',
                    '60',
                ]
            )
    assert rc == 0
    run_config.assert_called_once()
    config = run_config.call_args.args[0]
    assert config.static.route == '/assets'
    assert config.static.mount == str(root)
    assert config.static.expires == 60
    assert config.app.target is None
