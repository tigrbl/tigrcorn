import asyncio
import socket
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import FRAME_DATA, H3_NO_ERROR, encode_frame
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(app, *, max_body_size=None):
    config = build_config(
        transport='udp',
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=['3'],
        protocols=['http3'],
        quic_secret=b'shared',
        max_body_size=max_body_size,
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.transport.get_extra_info('sockname')[1]
    return server, port


class HTTP3ServerTests(unittest.IsolatedAsyncioTestCase):
    def test_http3_oversized_body_limit_is_independent_of_parse_buffer(self):
        core = HTTP3ConnectionCore(role='server', max_body_size=70_000)
        client = HTTP3ConnectionCore(role='client')
        headers = client.get_request(0).encode_request([
            (b':method', b'POST'), (b':path', b'/upload'), (b':scheme', b'https'),
        ])
        core.receive_stream_data(0, headers)
        frame = encode_frame(FRAME_DATA, b'a' * 33_000)
        core.receive_stream_data(0, frame)
        state = core.receive_stream_data(0, frame)
        self.assertEqual(len(state.body), 66_000)
        self.assertFalse(state.parse_buffer)
        self.assertFalse(state.body_too_large)

        state = core.receive_stream_data(0, encode_frame(FRAME_DATA, b'a' * 4_001), fin=True)
        self.assertTrue(state.body_too_large)
        self.assertTrue(state.abandoned)
        self.assertEqual(state.body, b'')

    async def test_http3_oversized_body_preserves_other_streams(self):
        paths = []

        async def app(scope, receive, send):
            paths.append(scope['path'])
            self.assertEqual((await receive())['body'], b'abcde')
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})

        server, port = await _start_server(app, max_body_size=5)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1')
        core = HTTP3ConnectionCore(role='client')
        loop = asyncio.get_running_loop()
        peer = ('127.0.0.1', port)
        responses = {}
        stops = {}

        async def read_packets_until(done):
            async with asyncio.timeout(2):
                while not done():
                    data, _ = await loop.sock_recvfrom(sock, 65535)
                    for event in client.receive_datagram(data):
                        if event.kind == 'stream':
                            state = core.receive_stream_data(
                                event.stream_id, event.data, fin=event.fin,
                            )
                            if state is not None and state.ready:
                                responses[event.stream_id] = dict(state.headers)[b':status']
                        elif event.kind == 'stop_sending':
                            stops[event.stream_id] = event.detail.error_code

        def headers(stream_id, path, fields=()):
            return core.get_request(stream_id).encode_request([
                (b':method', b'POST'), (b':path', path), (b':scheme', b'https'), *fields,
            ])

        try:
            sock.sendto(client.build_initial(), peer)
            await read_packets_until(lambda: core.state.remote_control_stream_id is not None)
            sock.sendto(client.send_stream_data(0, headers(0, b'/streaming') + encode_frame(FRAME_DATA, b'abc')), peer)
            sock.sendto(client.send_stream_data(4, headers(4, b'/sibling')), peer)
            sock.sendto(client.send_stream_data(
                8, headers(8, b'/declared', [(b'content-length', b'6')]),
            ), peer)
            sock.sendto(client.send_stream_data(0, encode_frame(FRAME_DATA, b'def')), peer)
            await read_packets_until(lambda: {0, 8} <= responses.keys() and {0, 8} <= stops.keys())
            self.assertEqual(responses, {8: b'413', 0: b'413'})
            self.assertEqual(stops, {8: H3_NO_ERROR, 0: H3_NO_ERROR})
            sock.sendto(client.send_stream_data(4, encode_frame(FRAME_DATA, b'abcde'), fin=True), peer)
            await read_packets_until(lambda: 4 in responses)
            self.assertEqual(responses[4], b'204')
            self.assertEqual(paths, ['/sibling'])
        finally:
            sock.close()
            await server.close()

    async def test_http3_roundtrip(self):
        async def app(scope, receive, send):
            self.assertEqual(scope['type'], 'http')
            self.assertEqual(scope['http_version'], '3')
            self.assertEqual(scope['path'], '/h3')
            event = await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'echo:' + event['body'], 'more_body': False})

        server, port = await _start_server(app)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1')
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ('127.0.0.1', port))
            pre_events = []
            for _ in range(2):
                data, _addr = await loop.sock_recvfrom(sock, 65535)
                pre_events.extend(client.receive_datagram(data))
            self.assertTrue(any(event.kind == 'ack' for event in pre_events))
            control_streams = [event for event in pre_events if event.kind == 'stream']
            self.assertEqual(len(control_streams), 1)
            self.assertIsNone(core.receive_stream_data(control_streams[0].stream_id, control_streams[0].data, fin=control_streams[0].fin))
            payload = core.get_request(0).encode_request(
                [(b':method', b'POST'), (b':path', b'/h3'), (b':scheme', b'https')],
                b'hello',
            )
            sock.sendto(client.send_stream_data(0, payload, fin=True), ('127.0.0.1', port))
            response_state = None
            for _ in range(3):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                        break
                if response_state is not None:
                    break
            self.assertIsNotNone(response_state)
            assert response_state is not None
            self.assertIn((b':status', b'200'), response_state.headers)
            self.assertEqual(response_state.body, b'echo:hello')
        finally:
            sock.close()
            await server.close()
