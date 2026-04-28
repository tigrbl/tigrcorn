from __future__ import annotations

import asyncio
import base64
import logging
import os
import unittest
from argparse import Namespace
from unittest.mock import patch

from tigrcorn.asgi.receive import QueueReceive
from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config, build_config_from_namespace
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger
from tigrcorn.protocols.http1.parser import ParsedRequest, read_http11_request_head
from tigrcorn.protocols.http2.websocket import H2WebSocketSession
from tigrcorn.protocols.http3.websocket import H3WebSocketSession
from tigrcorn.protocols.websocket.handler import WebSocketConnectionHandler
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.tcp.reader import PrebufferedReader


def _websocket_request_headers() -> list[tuple[bytes, bytes]]:
    return [
        (b'host', b'localhost'),
        (b'upgrade', b'websocket'),
        (b'connection', b'Upgrade'),
        (b'sec-websocket-version', b'13'),
        (b'sec-websocket-key', base64.b64encode(os.urandom(16))),
    ]


def _build_ws_request(path: str = '/ws') -> ParsedRequest:
    return ParsedRequest(
        method='GET',
        target=path,
        path=path,
        raw_path=path.encode('ascii'),
        query_string=b'',
        http_version='1.1',
        headers=_websocket_request_headers(),
        body=b'',
        keep_alive=True,
        expect_continue=False,
        websocket_upgrade=True,
    )


async def _start_http11_server(app, *, config_mutator=None):
    config = build_config(app=None, host='127.0.0.1', port=0, lifespan='off', http_versions=['1.1'])
    if config_mutator is not None:
        config_mutator(config)
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


async def _read_http_response(reader: asyncio.StreamReader) -> tuple[bytes, bytes]:
    head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 1.0)
    length = 0
    for line in head.split(b'\r\n'):
        if line.lower().startswith(b'content-length:'):
            length = int(line.split(b':', 1)[1].strip())
            break
    body = await asyncio.wait_for(reader.readexactly(length), 1.0) if length else b''
    return head, body


class Phase3H1WebSocketOperatorSurfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_parser_accepts_phase3_flags(self):
        parser = build_parser()
        ns = parser.parse_args(
            [
                'tests.fixtures_pkg.appmod:app',
                '--http1-max-incomplete-event-size', '8192',
                '--http1-buffer-size', '4096',
                '--http1-header-read-timeout', '2.5',
                '--no-http1-keep-alive',
                '--websocket-max-queue', '64',
            ]
        )
        self.assertEqual(ns.http1_max_incomplete_event_size, 8192)
        self.assertEqual(ns.http1_buffer_size, 4096)
        self.assertEqual(ns.http1_header_read_timeout, 2.5)
        self.assertFalse(ns.http1_keep_alive)
        self.assertEqual(ns.websocket_max_queue, 64)

    def test_build_config_from_namespace_maps_phase3_submodels(self):
        parser = build_parser()
        ns = parser.parse_args(
            [
                'tests.fixtures_pkg.appmod:app',
                '--http1-max-incomplete-event-size', '16384',
                '--http1-buffer-size', '2048',
                '--http1-header-read-timeout', '1.25',
                '--no-http1-keep-alive',
                '--websocket-max-message-size', '2048',
                '--websocket-max-queue', '8',
            ]
        )
        config = build_config_from_namespace(ns)
        self.assertEqual(config.http.http1_max_incomplete_event_size, 16384)
        self.assertEqual(config.http.http1_buffer_size, 2048)
        self.assertEqual(config.http.http1_header_read_timeout, 1.25)
        self.assertFalse(config.http.http1_keep_alive)
        self.assertEqual(config.websocket.max_message_size, 2048)
        self.assertEqual(config.websocket.max_queue, 8)

    def test_phase3_env_surface_is_respected(self):
        parser = build_parser()
        ns = parser.parse_args(['--env-prefix', 'PHASE3TEST'])
        with patch.dict(
            os.environ,
            {
                'PHASE3TEST_HTTP1_BUFFER_SIZE': '4096',
                'PHASE3TEST_HTTP1_MAX_INCOMPLETE_EVENT_SIZE': '8192',
                'PHASE3TEST_HTTP1_HEADER_READ_TIMEOUT': '0.75',
                'PHASE3TEST_HTTP1_KEEP_ALIVE': 'false',
                'PHASE3TEST_WEBSOCKET_MAX_QUEUE': '12',
            },
            clear=False,
        ):
            config = build_config_from_namespace(ns)
        self.assertEqual(config.http.http1_buffer_size, 4096)
        self.assertEqual(config.http.http1_max_incomplete_event_size, 8192)
        self.assertEqual(config.http.http1_header_read_timeout, 0.75)
        self.assertFalse(config.http.http1_keep_alive)
        self.assertEqual(config.websocket.max_queue, 12)

    async def test_http11_parser_applies_incomplete_event_cap(self):
        reader = asyncio.StreamReader()
        request = (
            b'GET / HTTP/1.1\r\n'
            b'Host: localhost\r\n'
            b'X-Large: ' + (b'a' * 128) + b'\r\n\r\n'
        )
        reader.feed_data(request)
        reader.feed_eof()
        with self.assertRaises(ProtocolError):
            await read_http11_request_head(
                PrebufferedReader(reader),
                max_header_size=4096,
                max_incomplete_event_size=64,
            )

    async def test_http11_buffer_size_controls_streaming_request_chunks(self):
        seen_chunks: list[int] = []

        async def app(scope, receive, send):
            while True:
                message = await receive()
                if message['type'] != 'http.request':
                    break
                seen_chunks.append(len(message.get('body', b'')))
                if not message.get('more_body', False):
                    break
            body = ','.join(str(size) for size in seen_chunks).encode('ascii')
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': body, 'more_body': False})

        server, port = await _start_http11_server(
            app,
            config_mutator=lambda cfg: setattr(cfg.http, 'http1_buffer_size', 4),
        )
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            payload = b'abcdefghij'
            request = (
                b'POST /upload HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Content-Length: 10\r\n\r\n' + payload
            )
            writer.write(request)
            await writer.drain()
            _head, body = await _read_http_response(reader)
            self.assertEqual(body, b'4,4,2')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http11_keep_alive_disable_forces_connection_close(self):
        seen_paths: list[str] = []

        async def app(scope, receive, send):
            seen_paths.append(scope['path'])
            await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, port = await _start_http11_server(
            app,
            config_mutator=lambda cfg: setattr(cfg.http, 'http1_keep_alive', False),
        )
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
                b'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            )
            await writer.drain()
            head, body = await _read_http_response(reader)
            self.assertIn(b'connection: close', head.lower())
            self.assertEqual(body, b'ok')
            tail = await asyncio.wait_for(reader.read(), 1.0)
            self.assertEqual(tail, b'')
            self.assertEqual(seen_paths, ['/first'])
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http11_header_read_timeout_tightens_generic_timeout(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        def mutate(cfg):
            cfg.http.read_timeout = 5.0
            cfg.http.keep_alive_timeout = 5.0
            cfg.http.http1_header_read_timeout = 0.1

        server, port = await _start_http11_server(app, config_mutator=mutate)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(b'GET / HTTP/1.1\r\nHost: localhost')
            await writer.drain()
            data = await asyncio.wait_for(reader.read(), 1.0)
            self.assertEqual(data, b'')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_queue_receive_honors_max_size(self):
        receive = QueueReceive(max_size=1)
        await receive.put({'type': 'one'})
        blocked = asyncio.create_task(receive.put({'type': 'two'}))
        await asyncio.sleep(0.05)
        self.assertFalse(blocked.done())
        first = await receive()
        self.assertEqual(first['type'], 'one')
        await asyncio.wait_for(blocked, 1.0)
        second = await receive()
        self.assertEqual(second['type'], 'two')
        self.assertEqual(receive.max_size, 1)

    def test_websocket_handlers_receive_queue_size_from_config(self):
        config = build_config(websocket_max_queue=7)
        request = _build_ws_request()
        access_logger = AccessLogger(logging.getLogger('phase3'), enabled=False)

        h1 = WebSocketConnectionHandler(
            app=lambda scope, receive, send: None,
            config=config,
            access_logger=access_logger,
            request=request,
            reader=object(),
            writer=object(),
            client=('127.0.0.1', 1),
            server=('127.0.0.1', 2),
            scheme='ws',
        )
        self.assertEqual(h1.receive.max_size, 7)

        async def _send_headers(status: int, headers: list[tuple[bytes, bytes]], end_stream: bool) -> None:
            return None

        async def _send_data(data: bytes, end_stream: bool) -> None:
            return None

        h2 = H2WebSocketSession(
            app=lambda scope, receive, send: None,
            config=config,
            request=request,
            client=('127.0.0.1', 1),
            server=('127.0.0.1', 2),
            scheme='https',
            send_headers=_send_headers,
            send_data=_send_data,
        )
        self.assertEqual(h2.receive.max_size, 7)

        h3 = H3WebSocketSession(
            app=lambda scope, receive, send: None,
            config=config,
            request=request,
            client=('127.0.0.1', 1),
            server=('127.0.0.1', 2),
            scheme='https',
            send_headers=_send_headers,
            send_data=_send_data,
        )
        self.assertEqual(h3.receive.max_size, 7)
