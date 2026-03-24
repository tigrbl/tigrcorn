from __future__ import annotations

import asyncio
import socket
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import encode_frame as encode_h3_frame, FRAME_DATA as H3_FRAME_DATA
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(*, http_versions: list[str], transport: str = 'tcp', config_mutator=None):
    async def app(scope, receive, send):
        raise AssertionError('CONNECT handling should not dispatch to the ASGI app')

    kwargs = {'host': '127.0.0.1', 'port': 0, 'lifespan': 'off', 'http_versions': http_versions}
    if transport == 'udp':
        kwargs.update({'transport': 'udp', 'protocols': ['http3'], 'quic_secret': b'shared'})
    config = build_config(**kwargs)
    if config_mutator is not None:
        config_mutator(config)
    server = TigrCornServer(app, config)
    await server.start()
    if transport == 'udp':
        port = server._listeners[0].transport.get_extra_info('sockname')[1]
    else:
        port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


async def _issue_h2_connect(port: int, authority: str) -> tuple[list[tuple[bytes, bytes]], bytes, bool]:
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    try:
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        frame_writer = FrameWriter()
        request_headers = encode_header_block([
            (b':method', b'CONNECT'),
            (b':authority', authority.encode('ascii')),
        ])
        writer.write(frame_writer.headers(1, request_headers, end_stream=True))
        await writer.drain()

        buf = FrameBuffer()
        response_headers: list[tuple[bytes, bytes]] = []
        body = bytearray()
        ended = False
        while not ended:
            data = await asyncio.wait_for(reader.read(65535), 1.0)
            if not data:
                break
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS:
                    continue
                if frame.frame_type == FRAME_HEADERS and frame.stream_id == 1:
                    response_headers.extend(decode_header_block(frame.payload))
                    if frame.flags & 0x1:
                        ended = True
                elif frame.frame_type == FRAME_DATA and frame.stream_id == 1:
                    body.extend(frame.payload)
                    if frame.flags & 0x1:
                        ended = True
        return response_headers, bytes(body), ended
    finally:
        writer.close()
        await writer.wait_closed()


async def _issue_h3_connect(port: int, authority: str) -> tuple[list[tuple[bytes, bytes]], bytes, bool]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-connect-neg')
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    try:
        sock.sendto(client.build_initial(), ('127.0.0.1', port))
        for _ in range(2):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == 'stream':
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        connect_payload = core.get_request(0).encode_request([
            (b':method', b'CONNECT'),
            (b':authority', authority.encode('ascii')),
        ])
        sock.sendto(client.send_stream_data(0, connect_payload, fin=True), ('127.0.0.1', port))
        response_state = None
        while response_state is None or not response_state.ended:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == 'stream' and event.stream_id == 0:
                    response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        assert response_state is not None
        return list(response_state.headers), bytes(response_state.body), bool(response_state.ended)
    finally:
        sock.close()


class ConnectRelayPhase9D1LocalNegativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_http2_connect_policy_deny_and_allowlist_rejection_end_stream(self) -> None:
        upstream = await asyncio.start_server(lambda r, w: None, '127.0.0.1', 0)
        upstream_port = upstream.sockets[0].getsockname()[1]
        try:
            def deny(config):
                config.http.connect_policy = 'deny'

            server, port = await _start_server(http_versions=['2'], config_mutator=deny)
            try:
                headers, body, ended = await _issue_h2_connect(port, f'127.0.0.1:{upstream_port}')
                self.assertIn((b':status', b'403'), headers)
                self.assertEqual(body, b'connect denied')
                self.assertTrue(ended)
            finally:
                await server.close()

            def allowlist(config):
                config.http.connect_policy = 'allowlist'
                config.http.connect_allow = ['127.0.0.1:1']

            server, port = await _start_server(http_versions=['2'], config_mutator=allowlist)
            try:
                headers, body, ended = await _issue_h2_connect(port, f'127.0.0.1:{upstream_port}')
                self.assertIn((b':status', b'403'), headers)
                self.assertEqual(body, b'connect denied')
                self.assertTrue(ended)
            finally:
                await server.close()
        finally:
            upstream.close()
            await upstream.wait_closed()

    async def test_http3_connect_policy_deny_and_allowlist_rejection_end_stream(self) -> None:
        upstream = await asyncio.start_server(lambda r, w: None, '127.0.0.1', 0)
        upstream_port = upstream.sockets[0].getsockname()[1]
        try:
            def deny(config):
                config.http.connect_policy = 'deny'

            server, port = await _start_server(http_versions=['3'], transport='udp', config_mutator=deny)
            try:
                headers, body, ended = await _issue_h3_connect(port, f'127.0.0.1:{upstream_port}')
                self.assertIn((b':status', b'403'), headers)
                self.assertEqual(body, b'connect denied')
                self.assertTrue(ended)
            finally:
                await server.close()

            def allowlist(config):
                config.http.connect_policy = 'allowlist'
                config.http.connect_allow = ['127.0.0.1:1']

            server, port = await _start_server(http_versions=['3'], transport='udp', config_mutator=allowlist)
            try:
                headers, body, ended = await _issue_h3_connect(port, f'127.0.0.1:{upstream_port}')
                self.assertIn((b':status', b'403'), headers)
                self.assertEqual(body, b'connect denied')
                self.assertTrue(ended)
            finally:
                await server.close()
        finally:
            upstream.close()
            await upstream.wait_closed()


if __name__ == '__main__':
    unittest.main()
