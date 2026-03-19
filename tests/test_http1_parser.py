import asyncio
import unittest

from tigrcorn.protocols.http1.parser import read_http11_request
from tigrcorn.transports.tcp.reader import PrebufferedReader


class HTTP1ParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_simple_request(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b"GET /hello?x=1 HTTP/1.1\r\nHost: example\r\nContent-Length: 0\r\n\r\n")
        reader.feed_eof()
        req = await read_http11_request(PrebufferedReader(reader))
        self.assertIsNotNone(req)
        assert req is not None
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.path, "/hello")
        self.assertEqual(req.query_string, b"x=1")


if __name__ == "__main__":
    unittest.main()
