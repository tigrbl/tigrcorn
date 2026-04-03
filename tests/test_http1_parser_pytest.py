import asyncio

import pytest

from tigrcorn.protocols.http1.parser import read_http11_request
from tigrcorn.transports.tcp.reader import PrebufferedReader


@pytest.mark.asyncio
async def test_simple_request() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET /hello?x=1 HTTP/1.1\r\nHost: example\r\nContent-Length: 0\r\n\r\n")
    reader.feed_eof()
    req = await read_http11_request(PrebufferedReader(reader))
    assert req is not None
    assert req.method == "GET"
    assert req.path == "/hello"
    assert req.query_string == b"x=1"
