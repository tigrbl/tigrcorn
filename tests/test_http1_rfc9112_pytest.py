import asyncio

import pytest

from tigrcorn.config.load import build_config
from tigrcorn.errors import ProtocolError, UnsupportedFeature
from tigrcorn.protocols.http1.parser import read_http11_request_head
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.tcp.reader import PrebufferedReader


async def _start_server(app):
    config = build_config(host="127.0.0.1", port=0, lifespan="off", http_versions=["1.1"])
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


async def _read_response(reader: asyncio.StreamReader) -> tuple[bytes, bytes]:
    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 1.0)
    length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
            break
    body = await asyncio.wait_for(reader.readexactly(length), 1.0) if length else b""
    return head, body


@pytest.mark.asyncio
async def test_absolute_form_request_target() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET http://example.com/alpha?x=1 HTTP/1.1\r\nHost: example.com\r\n\r\n")
    reader.feed_eof()
    request = await read_http11_request_head(PrebufferedReader(reader))
    assert request is not None
    assert request.path == "/alpha"
    assert request.query_string == b"x=1"
    assert request.target_form == "absolute"


@pytest.mark.asyncio
async def test_asterisk_form_restricted_to_options() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET * HTTP/1.1\r\nHost: example.com\r\n\r\n")
    reader.feed_eof()
    with pytest.raises(ProtocolError):
        await read_http11_request_head(PrebufferedReader(reader))


@pytest.mark.asyncio
async def test_missing_host_rejected_for_http11() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET / HTTP/1.1\r\n\r\n")
    reader.feed_eof()
    with pytest.raises(ProtocolError):
        await read_http11_request_head(PrebufferedReader(reader))


@pytest.mark.asyncio
async def test_unsupported_transfer_encoding_chain_rejected() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(
        b"POST /upload HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Transfer-Encoding: gzip, chunked\r\n\r\n"
    )
    reader.feed_eof()
    with pytest.raises(UnsupportedFeature):
        await read_http11_request_head(PrebufferedReader(reader))


@pytest.mark.asyncio
async def test_expect_continue_sent_on_first_receive() -> None:
    async def app(scope, receive, send):
        assert scope["path"] == "/upload"
        event = await receive()
        assert event["body"] == b"hello"
        assert not event["more_body"]
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"done", "more_body": False})

    server, port = await _start_server(app)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(
            b"POST /upload HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Expect: 100-continue\r\n"
            b"Content-Length: 5\r\n\r\n"
        )
        await writer.drain()
        interim = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 1.0)
        assert b"100 Continue" in interim
        writer.write(b"hello")
        await writer.drain()
        head, body = await _read_response(reader)
        assert b"200 OK" in head
        assert body == b"done"
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_chunked_request_body_is_streamed_as_multiple_events() -> None:
    seen_events: list[tuple[bytes, bool]] = []

    async def app(scope, receive, send):
        while True:
            event = await receive()
            seen_events.append((event["body"], event["more_body"]))
            if not event["more_body"]:
                break
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    server, port = await _start_server(app)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(
            b"POST /stream HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n"
            b"3\r\nhel\r\n"
            b"2\r\nlo\r\n"
            b"0\r\nX-Trailer: yes\r\n\r\n"
        )
        await writer.drain()
        head, body = await _read_response(reader)
        assert b"200 OK" in head
        assert body == b"ok"
        assert seen_events == [(b"hel", True), (b"lo", True), (b"", False)]
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()
