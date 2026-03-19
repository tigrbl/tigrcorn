import unittest

from tigrcorn.protocols.http1.serializer import finalize_chunked_body, serialize_http11_response_chunk


class HTTP1ChunkedTests(unittest.TestCase):
    def test_chunk_serialization(self):
        self.assertEqual(serialize_http11_response_chunk(b"hello"), b"5\r\nhello\r\n")
        self.assertEqual(finalize_chunked_body(), b"0\r\n\r\n")


if __name__ == "__main__":
    unittest.main()
