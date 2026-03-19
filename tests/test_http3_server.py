import asyncio
import socket
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(app):
    config = build_config(
        transport='udp',
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=['3'],
        protocols=['http3'],
        quic_secret=b'shared',
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.transport.get_extra_info('sockname')[1]
    return server, port


class HTTP3ServerTests(unittest.IsolatedAsyncioTestCase):
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
