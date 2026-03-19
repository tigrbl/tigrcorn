import asyncio
import socket
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import FRAME_DATA as H3_FRAME_DATA, FRAME_HEADERS as H3_FRAME_HEADERS, encode_frame as encode_h3_frame
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(*, http_versions: list[str], transport: str = 'tcp', seen: dict):
    async def app(scope, receive, send):
        seen['extensions'] = dict(scope['extensions'])
        events = []
        while True:
            event = await receive()
            events.append(event)
            if event['type'] == 'http.disconnect':
                break
        seen['events'] = events
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

    kwargs = {'host': '127.0.0.1', 'port': 0, 'lifespan': 'off', 'http_versions': http_versions}
    if transport == 'udp':
        kwargs.update({'transport': 'udp', 'protocols': ['http3'], 'quic_secret': b'shared'})
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    if transport == 'udp':
        port = server._listeners[0].transport.get_extra_info('sockname')[1]
    else:
        port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


async def _read_http1_response(reader: asyncio.StreamReader) -> tuple[bytes, bytes]:
    head = await reader.readuntil(b'\r\n\r\n')
    length = 0
    for line in head.split(b'\r\n')[1:]:
        if line.lower().startswith(b'content-length:'):
            length = int(line.split(b':', 1)[1].strip())
            break
    body = await reader.readexactly(length) if length else b''
    return head, body


class TrailerFieldsRFC9110Tests(unittest.IsolatedAsyncioTestCase):
    async def test_http11_request_trailers_are_exposed(self):
        seen: dict = {}
        server, port = await _start_server(http_versions=['1.1'], seen=seen)
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
            head, body = await _read_http1_response(reader)
            self.assertIn(b'200 OK', head)
            self.assertEqual(body, b'ok')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()
        self.assertIn('tigrcorn.http.request_trailers', seen['extensions'])
        self.assertEqual(seen['events'][0]['type'], 'http.request')
        self.assertEqual(seen['events'][1]['type'], 'http.request')
        self.assertEqual(seen['events'][2]['type'], 'http.request.trailers')
        self.assertEqual(seen['events'][2]['trailers'], [(b'x-trailer-one', b'yes'), (b'x-trailer-two', b'done')])
        self.assertEqual(seen['events'][3]['type'], 'http.disconnect')

    async def test_http2_request_trailers_are_exposed(self):
        seen: dict = {}
        server, port = await _start_server(http_versions=['2'], seen=seen)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            frame_writer = FrameWriter()
            request_headers = encode_header_block([
                (b':method', b'POST'),
                (b':scheme', b'http'),
                (b':path', b'/trailers'),
                (b':authority', b'localhost'),
                (b'te', b'trailers'),
            ])
            writer.write(frame_writer.headers(1, request_headers, end_stream=False))
            writer.write(frame_writer.data(1, b'hello', end_stream=False))
            trailer_headers = encode_header_block([
                (b'x-trailer-one', b'yes'),
                (b'x-trailer-two', b'done'),
            ])
            writer.write(frame_writer.headers(1, trailer_headers, end_stream=True))
            await writer.drain()

            buf = FrameBuffer()
            response_headers: list[tuple[bytes, bytes]] = []
            body = bytearray()
            ended = False
            while not ended:
                data = await asyncio.wait_for(reader.read(65535), 2.0)
                self.assertTrue(data)
                buf.feed(data)
                for frame in buf.pop_all():
                    if frame.frame_type == FRAME_SETTINGS:
                        if frame.payload:
                            decode_settings(frame.payload)
                    elif frame.frame_type == FRAME_HEADERS:
                        response_headers.extend(decode_header_block(frame.payload))
                        if frame.flags & 0x1:
                            ended = True
                    elif frame.frame_type == FRAME_DATA:
                        body.extend(frame.payload)
                        if frame.flags & 0x1:
                            ended = True
                if response_headers and ended:
                    break
            self.assertIn((b':status', b'200'), response_headers)
            self.assertEqual(bytes(body), b'ok')
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

        self.assertIn('tigrcorn.http.request_trailers', seen['extensions'])
        self.assertEqual(seen['events'][0]['type'], 'http.request')
        self.assertEqual(seen['events'][0]['body'], b'hello')
        self.assertFalse(seen['events'][0]['more_body'])
        self.assertEqual(seen['events'][1]['type'], 'http.request.trailers')
        self.assertEqual(seen['events'][1]['trailers'], [(b'x-trailer-one', b'yes'), (b'x-trailer-two', b'done')])
        self.assertEqual(seen['events'][2]['type'], 'http.disconnect')

    async def test_http3_request_trailers_are_exposed(self):
        seen: dict = {}
        server, port = await _start_server(http_versions=['3'], transport='udp', seen=seen)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-trailer')
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ('127.0.0.1', port))
            for _ in range(2):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)

            headers_payload = core.get_request(0).encode_request([
                (b':method', b'POST'),
                (b':scheme', b'https'),
                (b':path', b'/trailers'),
                (b':authority', b'localhost'),
                (b'te', b'trailers'),
            ], body=b'hello')
            trailer_block = core.encode_headers(0, [(b'x-trailer-one', b'yes'), (b'x-trailer-two', b'done')])
            payload = headers_payload + encode_h3_frame(H3_FRAME_HEADERS, trailer_block)
            sock.sendto(client.send_stream_data(0, payload, fin=True), ('127.0.0.1', port))

            response_state = None
            while response_state is None or not response_state.ended:
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream' and event.stream_id == 0:
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            assert response_state is not None
            self.assertIn((b':status', b'200'), response_state.headers)
            self.assertEqual(response_state.body, b'ok')
        finally:
            sock.close()
            await server.close()

        self.assertIn('tigrcorn.http.request_trailers', seen['extensions'])
        self.assertEqual(seen['events'][0]['type'], 'http.request')
        self.assertEqual(seen['events'][0]['body'], b'hello')
        self.assertFalse(seen['events'][0]['more_body'])
        self.assertEqual(seen['events'][1]['type'], 'http.request.trailers')
        self.assertEqual(seen['events'][1]['trailers'], [(b'x-trailer-one', b'yes'), (b'x-trailer-two', b'done')])
        self.assertEqual(seen['events'][2]['type'], 'http.disconnect')


if __name__ == '__main__':
    unittest.main()
