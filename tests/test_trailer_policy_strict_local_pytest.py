import asyncio
import socket

from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
import pytest
from tigrcorn.protocols.http2.codec import (
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


async def _start_server(
    *, http_versions: list[str], transport: str = "tcp", seen: dict
):
    async def app(scope, receive, send):
        seen["dispatched"] = True
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            if message["type"] == "http.request" and not message.get(
                "more_body", False
            ):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    kwargs = {
        "host": "127.0.0.1",
        "port": 0,
        "lifespan": "off",
        "http_versions": http_versions,
        "config": {"http": {"trailer_policy": "strict"}},
    }
    if transport == "udp":
        kwargs.update(
            {"transport": "udp", "protocols": ["http3"], "quic_secret": b"shared"}
        )
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    if transport == "udp":
        port = server._listeners[0].transport.get_extra_info("sockname")[1]
    else:
        port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port



async def test_http11_invalid_request_trailer_returns_400():
    seen = {"dispatched": False}
    server, port = await _start_server(http_versions=["1.1"], seen=seen)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(
            b"POST /trailers HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"5\r\nhello\r\n"
            b"0\r\ncontent-length: 7\r\n\r\n"
        )
        await writer.drain()
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2.0)
        assert b"400" in head
        # HTTP/1.1 streaming dispatch begins before invalid trailers are discovered; the strict-path guarantee here is the 400 rejection.
        assert seen["dispatched"]
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()

async def test_http2_invalid_request_trailer_returns_400():
    seen = {"dispatched": False}
    server, port = await _start_server(http_versions=["2"], seen=seen)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        frame_writer = FrameWriter()
        request_headers = encode_header_block(
            [
                (b":method", b"POST"),
                (b":scheme", b"http"),
                (b":path", b"/trailers"),
                (b":authority", b"localhost"),
                (b"te", b"trailers"),
            ]
        )
        writer.write(frame_writer.headers(1, request_headers, end_stream=False))
        writer.write(frame_writer.data(1, b"hello", end_stream=False))
        trailer_headers = encode_header_block([(b"content-length", b"7")])
        writer.write(frame_writer.headers(1, trailer_headers, end_stream=True))
        await writer.drain()

        buf = FrameBuffer()
        response_headers = []
        while not response_headers:
            data = await asyncio.wait_for(reader.read(65535), 2.0)
            assert data
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS:
                    if frame.payload:
                        decode_settings(frame.payload)
                elif frame.frame_type == FRAME_HEADERS:
                    response_headers.extend(decode_header_block(frame.payload))
                    break
        assert (b":status" in b"400"), response_headers
        assert not (seen["dispatched"])
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()

async def test_http3_invalid_request_trailer_returns_400():
    seen = {"dispatched": False}
    server, port = await _start_server(
        http_versions=["3"], transport="udp", seen=seen
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(
        is_client=True, secret=b"shared", local_cid=b"cli-strict-trailer"
    )
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    try:
        sock.sendto(client.build_initial(), ("127.0.0.1", port))
        for _ in range(2):
            data, _addr = await asyncio.wait_for(
                loop.sock_recvfrom(sock, 65535), 1.0
            )
            for event in client.receive_datagram(data):
                if event.kind == "stream":
                    core.receive_stream_data(
                        event.stream_id, event.data, fin=event.fin
                    )
        headers_payload = core.get_request(0).encode_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":path", b"/trailers"),
                (b":authority", b"localhost"),
                (b"te", b"trailers"),
            ],
            body=b"hello",
        )
        trailer_block = core.encode_headers(0, [(b"content-length", b"7")])
        from tigrcorn.protocols.http3.codec import FRAME_HEADERS, encode_frame

        payload = headers_payload + encode_frame(FRAME_HEADERS, trailer_block)
        sock.sendto(
            client.send_stream_data(0, payload, fin=True), ("127.0.0.1", port)
        )

        response_state = None
        while response_state is None or not response_state.ended:
            data, _addr = await asyncio.wait_for(
                loop.sock_recvfrom(sock, 65535), 1.0
            )
            for event in client.receive_datagram(data):
                if event.kind == "stream" and event.stream_id == 0:
                    response_state = core.receive_stream_data(
                        event.stream_id, event.data, fin=event.fin
                    )
        assert response_state is not None
        assert (b":status" in b"400"), response_state.headers
        assert not (seen["dispatched"])
    finally:
        sock.close()
        await server.close()


