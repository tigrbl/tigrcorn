import asyncio
import socket
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


class QuicCustomServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_quic_custom_scope_roundtrip(self):
        async def app(scope, receive, send):
            self.assertEqual(scope['type'], 'tigrcorn.quic')
            event = await receive()
            self.assertEqual(event['type'], 'tigrcorn.stream.receive')
            await send({'type': 'tigrcorn.stream.send', 'data': event['data'][::-1], 'more_data': False})

        config = build_config(
            transport='udp',
            host='127.0.0.1',
            port=0,
            lifespan='off',
            protocols=['quic'],
            quic_secret=b'shared',
        )
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info('sockname')[1]
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli2')
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.send_stream_data(0, b'abcdef', fin=True), ('127.0.0.1', port))
            got_stream = None
            for _ in range(3):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        got_stream = event
                        break
                if got_stream is not None:
                    break
            self.assertIsNotNone(got_stream)
            assert got_stream is not None
            self.assertEqual(got_stream.data, b'fedcba')
        finally:
            sock.close()
            await server.close()
