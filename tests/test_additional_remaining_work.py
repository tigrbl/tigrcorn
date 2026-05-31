import asyncio
import base64
import os
import socket
import unittest
import zlib

from tigrcorn.config.defaults import default_config
from tigrcorn.config.load import build_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.udp.packet import UDPPacket
from tigrcorn.protocols.websocket.frames import encode_frame, read_frame


async def _start_http_server(app):
    config = build_config(host='127.0.0.1', port=0, lifespan='off', http_versions=['1.1'])
    config.http.connect_policy = 'relay'
    config.websocket.compression = 'permessage-deflate'
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


def _compress_ws_message(payload: bytes) -> bytes:
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(payload) + compressor.flush(zlib.Z_SYNC_FLUSH)
    return compressed[:-4]


class RemainingWorkHTTP1Tests(unittest.IsolatedAsyncioTestCase):
    async def test_chunked_request_trailers_are_exposed(self):
        seen = {}

        async def app(scope, receive, send):
            seen['extensions'] = scope['extensions']
            seen['events'] = [await receive(), await receive(), await receive()]
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

        server, port = await _start_http_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(
                b'POST /trailers HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Transfer-Encoding: chunked\r\n\r\n'
                b'5\r\nhello\r\n'
                b'0\r\nX-Trailer-One: yes\r\nX-Trailer-Two: done\r\n\r\n'
            )
            await writer.drain()
            await reader.readuntil(b'\r\n\r\n')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()
        self.assertIn('tigrcorn.http.request_trailers', seen['extensions'])
        self.assertEqual(seen['events'][0]['type'], 'http.request')
        self.assertEqual(seen['events'][1]['type'], 'http.request')
        self.assertFalse(seen['events'][1]['more_body'])
        self.assertEqual(seen['events'][2]['type'], 'http.request.trailers')
        self.assertEqual(seen['events'][2]['trailers'], [(b'x-trailer-one', b'yes'), (b'x-trailer-two', b'done')])

    async def test_connect_tunnel_relays_bytes(self):
        received = bytearray()

        async def upstream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            data = await reader.read(1024)
            received.extend(data)
            writer.write(data[::-1])
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        upstream = await asyncio.start_server(upstream_handler, '127.0.0.1', 0)
        upstream_port = upstream.sockets[0].getsockname()[1]

        async def app(scope, receive, send):
            raise AssertionError('CONNECT tunnel should be handled before ASGI app dispatch')

        server, port = await _start_http_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(f'CONNECT 127.0.0.1:{upstream_port} HTTP/1.1\r\nHost: localhost\r\n\r\n'.encode('ascii'))
            await writer.drain()
            head = await reader.readuntil(b'\r\n\r\n')
            self.assertIn(b'200 Connection Established', head)
            writer.write(b'abcdef')
            await writer.drain()
            echoed = await asyncio.wait_for(reader.readexactly(6), 1.0)
            self.assertEqual(echoed, b'fedcba')
            self.assertEqual(bytes(received), b'abcdef')
            writer.close()
            await writer.wait_closed()
        finally:
            server.request_shutdown()
            await server.close()
            upstream.close()
            await upstream.wait_closed()


class RemainingWorkWebSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_permessage_deflate_negotiates_and_roundtrips(self):
        seen = {}

        async def app(scope, receive, send):
            await receive()
            await send({'type': 'websocket.accept', 'headers': []})
            event = await receive()
            seen['event'] = event
            await send({'type': 'websocket.send', 'text': event['text']})
            await send({'type': 'websocket.close', 'code': 1000})

        server, port = await _start_http_server(app)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            key = base64.b64encode(os.urandom(16))
            writer.write(
                b'GET /ws HTTP/1.1\r\n'
                b'Host: localhost\r\n'
                b'Upgrade: websocket\r\n'
                b'Connection: Upgrade\r\n'
                b'Sec-WebSocket-Version: 13\r\n'
                b'Sec-WebSocket-Key: ' + key + b'\r\n'
                b'Sec-WebSocket-Extensions: permessage-deflate\r\n\r\n'
            )
            await writer.drain()
            response = await reader.readuntil(b'\r\n\r\n')
            self.assertIn(b'sec-websocket-extensions: permessage-deflate', response.lower())
            compressed = _compress_ws_message(b'hello compressed')
            writer.write(encode_frame(0x1, compressed, fin=True, masked=True, rsv1=True))
            await writer.drain()
            frame = await asyncio.wait_for(read_frame(reader, max_payload_size=4096, expect_masked=False, allow_rsv1=True), 1.0)
            self.assertTrue(frame.rsv1)
            decompressor = zlib.decompressobj(wbits=-15)
            echoed = decompressor.decompress(frame.payload + b'\x00\x00\xff\xff')
            self.assertEqual(echoed, b'hello compressed')
            self.assertEqual(seen['event']['text'], 'hello compressed')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()


class RemainingWorkQuicRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_http3_session_survives_address_rebinding_via_connection_id(self):
        async def app(scope, receive, send):
            event = await receive()
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3'], quic_secret=b'shared'),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )

        class Endpoint:
            def __init__(self):
                self.sent = []
                self.local_addr = ('127.0.0.1', 4433)
            def send(self, data, addr):
                self.sent.append((data, addr))

        endpoint = Endpoint()
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1')
        await handler.handle_packet(UDPPacket(data=client.build_initial(), addr=('127.0.0.1', 50000)), endpoint)
        self.assertEqual(len(handler.sessions_by_local_cid), 1)
        core = HTTP3ConnectionCore()
        # Consume control stream response if any.
        for raw, _addr in endpoint.sent:
            for event in client.receive_datagram(raw):
                if event.kind == 'stream':
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        endpoint.sent.clear()
        request_payload = core.get_request(0).encode_request([(b':method', b'POST'), (b':path', b'/rebind'), (b':scheme', b'https')], b'hi')
        await handler.handle_packet(UDPPacket(data=client.send_stream_data(0, request_payload, fin=True), addr=('127.0.0.1', 50001)), endpoint)
        self.assertEqual(len(handler.sessions_by_local_cid), 1)
        self.assertEqual(len(handler.sessions), 1)
        session = next(iter(handler.sessions.values()))
        self.assertEqual(session.addr, ('127.0.0.1', 50001))
