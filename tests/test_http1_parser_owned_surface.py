from __future__ import annotations

import asyncio
import inspect
import unittest

from tigrcorn.protocols.http1 import parser as http1_parser
from tigrcorn.protocols.http1.parser import read_http11_request
from tigrcorn.transports.tcp.reader import PrebufferedReader


class HTTP1ParserOwnedSurfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_parser_module_handles_http11_request_without_peer_backends(self):
        reader = asyncio.StreamReader()
        reader.feed_data(
            b"POST /owned?x=1 HTTP/1.1\r\n"
            b"Host: example\r\n"
            b"Content-Length: 5\r\n\r\n"
            b"hello"
        )
        reader.feed_eof()

        request = await read_http11_request(PrebufferedReader(reader))

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/owned")
        self.assertEqual(request.query_string, b"x=1")
        self.assertEqual(request.body, b"hello")

    def test_parser_module_does_not_import_h11_or_httptools(self):
        source = inspect.getsource(http1_parser)
        self.assertNotIn("import h11", source)
        self.assertNotIn("from h11", source)
        self.assertNotIn("import httptools", source)
        self.assertNotIn("from httptools", source)


if __name__ == "__main__":
    unittest.main()
