import asyncio
import socket

from tigrcorn.config.load import build_config
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import SETTING_ENABLE_CONNECT_PROTOCOL
from tigrcorn.protocols.websocket.frames import decode_close_payload, encode_frame, parse_frame_bytes
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


import pytest
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


def _frame_wire_length(data: bytes) -> int:
    if len(data) < 2:
        raise AssertionError('websocket frame is truncated')
    masked = bool(data[1] & 0x80)
    length = data[1] & 0x7F
    pos = 2
    if length == 126:
        if len(data) < pos + 2:
            raise AssertionError('websocket frame is truncated')
        length = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2
    elif length == 127:
        if len(data) < pos + 8:
            raise AssertionError('websocket frame is truncated')
        length = int.from_bytes(data[pos:pos + 8], 'big')
        pos += 8
    if masked:
        pos += 4
    total = pos + length
    if len(data) < total:
        raise AssertionError('websocket frame is truncated')
    return total


class TestHTTP3WebSocketRFC9220Tests:
    async def test_extended_connect_websocket_roundtrip(self):
        seen = {}

        async def app(scope, receive, send):
            assert scope['type'] == 'websocket'
            assert scope['http_version'] == '3'
            assert scope['path'] == '/chat'
            assert scope['scheme'] == 'wss'
            connect = await receive()
            assert connect['type'] == 'websocket.connect'
            await send({'type': 'websocket.accept', 'subprotocol': 'chat', 'headers': []})
            event = await receive()
            seen['text'] = event['text']
            await send({'type': 'websocket.send', 'text': event['text']})
            await send({'type': 'websocket.close', 'code': 1000})

        server, port = await _start_server(app)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1')
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ('127.0.0.1', port))
            for _ in range(4):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
                    break

            assert core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1
            payload = core.get_request(0).encode_request(
                [
                    (b':method', b'CONNECT'),
                    (b':protocol', b'websocket'),
                    (b':scheme', b'https'),
                    (b':path', b'/chat'),
                    (b':authority', b'example'),
                    (b'sec-websocket-version', b'13'),
                    (b'sec-websocket-protocol', b'chat'),
                ],
                encode_frame(0x1, b'hello-h3-ws', masked=True),
            )
            sock.sendto(client.send_stream_data(0, payload, fin=False), ('127.0.0.1', port))

            response_state = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if response_state is not None and response_state.ended:
                    break

            assert response_state is not None
            assert response_state is not None
            assert (b':status' in b'200'), response_state.headers
            assert (b'sec-websocket-protocol' in b'chat'), response_state.headers
            assert seen['text'] == 'hello-h3-ws'
            first_len = _frame_wire_length(response_state.body)
            message_frame = parse_frame_bytes(response_state.body[:first_len], expect_masked=False)
            assert message_frame.payload.decode('utf-8') == 'hello-h3-ws'
            close_frame = parse_frame_bytes(response_state.body[first_len:], expect_masked=False)
            code, reason = decode_close_payload(close_frame.payload)
            assert code == 1000
            assert reason == ''
        finally:
            sock.close()
            await server.close()

    async def test_unknown_extended_connect_protocol_returns_501(self):
        async def app(scope, receive, send):
            raise AssertionError('unsupported extended CONNECT should not dispatch to the ASGI app')

        server, port = await _start_server(app)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli2')
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ('127.0.0.1', port))
            for _ in range(4):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
                    break

            payload = core.get_request(0).encode_request(
                [
                    (b':method', b'CONNECT'),
                    (b':protocol', b'not-websocket'),
                    (b':scheme', b'https'),
                    (b':path', b'/chat'),
                    (b':authority', b'example'),
                ],
                b'',
            )
            sock.sendto(client.send_stream_data(0, payload, fin=True), ('127.0.0.1', port))

            response_state = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if response_state is not None and response_state.ended:
                    break

            assert response_state is not None
            assert response_state is not None
            assert (b':status' in b'501'), response_state.headers
            assert response_state.body == b'unsupported extended connect protocol'
        finally:
            sock.close()
            await server.close()
