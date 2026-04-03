import asyncio
import socket

import pytest

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import FRAME_DATA as H3_FRAME_DATA, encode_frame as encode_h3_frame
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(*, http_versions: list[str], transport: str = "tcp"):
    async def app(scope, receive, send):
        raise AssertionError("CONNECT tunneling should not dispatch to the ASGI app")

    kwargs = {"host": "127.0.0.1", "port": 0, "lifespan": "off", "http_versions": http_versions}
    if transport == "udp":
        kwargs.update({"transport": "udp", "protocols": ["http3"], "quic_secret": b"shared"})
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    if transport == "udp":
        port = server._listeners[0].transport.get_extra_info("sockname")[1]
    else:
        port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


@pytest.mark.asyncio
async def test_http11_connect_relays_bidirectionally() -> None:
    received = bytearray()

    async def upstream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        data = await reader.read(1024)
        received.extend(data)
        writer.write(data[::-1])
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    upstream = await asyncio.start_server(upstream_handler, "127.0.0.1", 0)
    upstream_port = upstream.sockets[0].getsockname()[1]
    server, port = await _start_server(http_versions=["1.1"])
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(f"CONNECT 127.0.0.1:{upstream_port} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("ascii"))
        await writer.drain()
        head = await reader.readuntil(b"\r\n\r\n")
        assert b"200 Connection Established" in head
        writer.write(b"abcdef")
        await writer.drain()
        echoed = await asyncio.wait_for(reader.readexactly(6), 1.0)
        assert echoed == b"fedcba"
        assert bytes(received) == b"abcdef"
        writer.close()
        await writer.wait_closed()
    finally:
        server.request_shutdown()
        await server.close()
        upstream.close()
        await upstream.wait_closed()


@pytest.mark.asyncio
async def test_http2_connect_relays_bidirectionally() -> None:
    received = bytearray()

    async def upstream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        data = await reader.read(1024)
        received.extend(data)
        writer.write(data[::-1])
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    upstream = await asyncio.start_server(upstream_handler, "127.0.0.1", 0)
    upstream_port = upstream.sockets[0].getsockname()[1]
    server, port = await _start_server(http_versions=["2"])
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        frame_writer = FrameWriter()
        request_headers = encode_header_block(
            [
                (b":method", b"CONNECT"),
                (b":authority", f"127.0.0.1:{upstream_port}".encode("ascii")),
            ]
        )
        writer.write(frame_writer.headers(1, request_headers, end_stream=False))
        await writer.drain()

        buf = FrameBuffer()
        response_headers: list[tuple[bytes, bytes]] = []
        while not response_headers:
            data = await asyncio.wait_for(reader.read(65535), 1.0)
            assert data
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS:
                    continue
                if frame.frame_type == FRAME_HEADERS and frame.stream_id == 1:
                    response_headers.extend(decode_header_block(frame.payload))
                    break
        assert (b":status", b"200") in response_headers
        writer.write(frame_writer.data(1, b"abcdef", end_stream=True))
        await writer.drain()

        echoed = bytearray()
        ended = False
        while not ended:
            data = await asyncio.wait_for(reader.read(65535), 1.0)
            assert data
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_DATA and frame.stream_id == 1:
                    echoed.extend(frame.payload)
                    if frame.flags & 0x1:
                        ended = True
        assert bytes(echoed) == b"fedcba"
        assert bytes(received) == b"abcdef"
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()
        upstream.close()
        await upstream.wait_closed()


@pytest.mark.asyncio
async def test_http3_connect_relays_bidirectionally() -> None:
    received = bytearray()

    async def upstream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        data = await reader.read(1024)
        received.extend(data)
        writer.write(data[::-1])
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    upstream = await asyncio.start_server(upstream_handler, "127.0.0.1", 0)
    upstream_port = upstream.sockets[0].getsockname()[1]
    server, port = await _start_server(http_versions=["3"], transport="udp")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(is_client=True, secret=b"shared", local_cid=b"cli-connect")
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    try:
        sock.sendto(client.build_initial(), ("127.0.0.1", port))
        for _ in range(2):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == "stream":
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)

        connect_payload = core.get_request(0).encode_request(
            [
                (b":method", b"CONNECT"),
                (b":authority", f"127.0.0.1:{upstream_port}".encode("ascii")),
            ]
        )
        sock.sendto(client.send_stream_data(0, connect_payload, fin=False), ("127.0.0.1", port))

        response_state = None
        while response_state is None or (b":status", b"200") not in response_state.headers:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == "stream":
                    state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                    if event.stream_id == 0:
                        response_state = state
        assert response_state is not None
        assert (b":status", b"200") in response_state.headers

        tunnel_payload = encode_h3_frame(H3_FRAME_DATA, b"abcdef")
        sock.sendto(client.send_stream_data(0, tunnel_payload, fin=True), ("127.0.0.1", port))

        while response_state is None or not response_state.ended:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == "stream" and event.stream_id == 0:
                    response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        assert response_state is not None
        assert response_state.body == b"fedcba"
        assert bytes(received) == b"abcdef"
    finally:
        sock.close()
        await server.close()
        upstream.close()
        await upstream.wait_closed()
