import asyncio
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.http1.parser import read_http11_request_head
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.tcp.reader import PrebufferedReader


async def _start_server(app):
    config = build_config(host='127.0.0.1', port=0, lifespan='off', http_versions=['1.1'])
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


async def _read_response(reader: asyncio.StreamReader, *, expect_body: bool = True) -> tuple[bytes, bytes]:
    head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 1.0)
    length = 0
    chunked = False
    for line in head.split(b'\r\n'):
        lower = line.lower()
        if lower.startswith(b'content-length:'):
            length = int(line.split(b':', 1)[1].strip())
        elif lower.startswith(b'transfer-encoding:') and b'chunked' in lower:
            chunked = True
    if chunked:
        chunks = bytearray()
        while True:
            size_line = await asyncio.wait_for(reader.readuntil(b'\r\n'), 1.0)
            size = int(size_line[:-2], 16)
            if size == 0:
                await asyncio.wait_for(reader.readuntil(b'\r\n'), 1.0)
                return head, bytes(chunks)
            chunks.extend(await asyncio.wait_for(reader.readexactly(size), 1.0))
            self_terminator = await asyncio.wait_for(reader.readexactly(2), 1.0)
            assert self_terminator == b'\r\n'
    body = await asyncio.wait_for(reader.readexactly(length), 1.0) if length and expect_body else b''
    return head, body


class HTTP1HardeningPassTests(unittest.IsolatedAsyncioTestCase):
    async def test_parser_rejects_invalid_header_field_name(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'GET / HTTP/1.1\r\nHost: example.com\r\nBad Header: value\r\n\r\n')
        reader.feed_eof()
        with self.assertRaises(ProtocolError):
            await read_http11_request_head(PrebufferedReader(reader))

    async def test_parser_rejects_invalid_header_field_value(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'GET / HTTP/1.1\r\nHost: example.com\r\nX-Test: bad\x00value\r\n\r\n')
        reader.feed_eof()
        with self.assertRaises(ProtocolError):
            await read_http11_request_head(PrebufferedReader(reader))

    async def test_http11_emits_informational_response_before_final_response(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 103, 'headers': [(b'link', b'</style.css>; rel=preload; as=style')]})
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, port = await _start_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
            await writer.drain()
            interim = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 1.0)
            self.assertIn(b'103 Early Hints', interim)
            self.assertIn(b'link: </style.css>; rel=preload; as=style', interim.lower())
            head, body = await _read_response(reader)
            self.assertIn(b'200 OK', head)
            self.assertEqual(body, b'ok')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_head_response_suppresses_body_and_preserves_content_length(self):
        async def app(scope, receive, send):
            await receive()
            if scope['method'] == 'HEAD':
                await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
                await send({'type': 'http.response.body', 'body': b'hello', 'more_body': False})
                return
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'next', 'more_body': False})

        server, port = await _start_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'HEAD /head HTTP/1.1\r\nHost: localhost\r\n\r\n'
                b'GET /next HTTP/1.1\r\nHost: localhost\r\n\r\n'
            )
            await writer.drain()
            head, body = await _read_response(reader, expect_body=False)
            self.assertIn(b'200 OK', head)
            self.assertIn(b'content-length: 5', head.lower())
            self.assertEqual(body, b'')
            head2, body2 = await _read_response(reader)
            self.assertIn(b'200 OK', head2)
            self.assertEqual(body2, b'next')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_pipelined_requests_and_204_no_body_do_not_desynchronize_connection(self):
        async def app(scope, receive, send):
            await receive()
            if scope['path'] == '/empty':
                await send({'type': 'http.response.start', 'status': 204, 'headers': []})
                await send({'type': 'http.response.body', 'body': b'should-not-be-sent', 'more_body': False})
                return
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': scope['path'].encode('ascii'), 'more_body': False})

        server, port = await _start_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'GET /empty HTTP/1.1\r\nHost: localhost\r\n\r\n'
                b'GET /after HTTP/1.1\r\nHost: localhost\r\n\r\n'
            )
            await writer.drain()
            head1, body1 = await _read_response(reader)
            self.assertIn(b'204 No Content', head1)
            self.assertNotIn(b'should-not-be-sent', head1)
            self.assertEqual(body1, b'')
            head2, body2 = await _read_response(reader)
            self.assertIn(b'200 OK', head2)
            self.assertEqual(body2, b'/after')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()
