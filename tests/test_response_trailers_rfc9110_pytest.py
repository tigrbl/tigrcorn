import asyncio
import socket

import pytest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import (
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_SETTINGS,
    FrameBuffer,
    FrameWriter,
    decode_settings,
    serialize_settings,
)
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(*, http_versions: list[str], transport: str = 'tcp'):
    from tests.fixtures_pkg.interop_trailer_app import app

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


@pytest.mark.asyncio
async def test_http11_response_trailers_are_emitted():
    server, port = await _start_server(http_versions=['1.1'])
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(b'GET /trailers HTTP/1.1\r\nHost: localhost\r\n\r\n')
        await writer.drain()
        head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 2.0)
        rest = await asyncio.wait_for(
            reader.readuntil(b'0\r\nx-trailer-one: yes\r\nx-trailer-two: done\r\n\r\n'),
            2.0,
        )
        response = head + rest
        assert b'transfer-encoding: chunked' in response.lower()
        assert b'0\r\nx-trailer-one: yes\r\nx-trailer-two: done\r\n\r\n' in response.lower()
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http2_response_trailers_are_emitted():
    server, port = await _start_server(http_versions=['2'])
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        frame_writer = FrameWriter()
        request_headers = encode_header_block(
            [
                (b':method', b'GET'),
                (b':scheme', b'http'),
                (b':path', b'/trailers'),
                (b':authority', b'localhost'),
            ]
        )
        writer.write(frame_writer.headers(1, request_headers, end_stream=True))
        await writer.drain()

        buf = FrameBuffer()
        response_headers = []
        response_trailers = []
        body = bytearray()
        ended = False
        while not ended:
            data = await asyncio.wait_for(reader.read(65535), 2.0)
            assert data
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS:
                    if frame.payload:
                        decode_settings(frame.payload)
                elif frame.frame_type == FRAME_HEADERS:
                    decoded = decode_header_block(frame.payload)
                    if response_headers:
                        response_trailers.extend(decoded)
                    else:
                        response_headers.extend(decoded)
                    if frame.flags & 0x1:
                        ended = True
                elif frame.frame_type == FRAME_DATA:
                    body.extend(frame.payload)
                    if frame.flags & 0x1:
                        ended = True
        assert (b':status', b'200') in response_headers
        assert bytes(body) == b'ok'
        assert (b'x-trailer-one', b'yes') in response_trailers
        assert (b'x-trailer-two', b'done') in response_trailers
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http3_response_trailers_are_emitted():
    server, port = await _start_server(http_versions=['3'], transport='udp')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-response-trailer')
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    try:
        sock.sendto(client.build_initial(), ('127.0.0.1', port))
        for _ in range(2):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == 'stream':
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)

        headers_payload = core.get_request(0).encode_request(
            [
                (b':method', b'GET'),
                (b':scheme', b'https'),
                (b':path', b'/trailers'),
                (b':authority', b'localhost'),
            ]
        )
        sock.sendto(client.send_stream_data(0, headers_payload, fin=True), ('127.0.0.1', port))

        response_state = None
        while response_state is None or not response_state.ended:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == 'stream' and event.stream_id == 0:
                    response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        assert response_state is not None
        assert (b':status', b'200') in response_state.headers
        assert response_state.body == b'ok'
        assert (b'x-trailer-one', b'yes') in response_state.trailers
        assert (b'x-trailer-two', b'done') in response_state.trailers
    finally:
        sock.close()
        await server.close()
