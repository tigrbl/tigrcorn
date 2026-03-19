import unittest

from tigrcorn.protocols.http2.codec import FrameBuffer, FrameWriter, decode_settings, serialize_settings, serialize_window_update
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block


class HTTP2CodecTests(unittest.TestCase):
    def test_hpack_roundtrip(self):
        headers = [(b':method', b'GET'), (b':path', b'/'), (b'content-type', b'text/plain')]
        encoded = encode_header_block(headers)
        self.assertEqual(decode_header_block(encoded), headers)

    def test_frame_buffer_roundtrip(self):
        writer = FrameWriter(max_frame_size=8)
        raw = writer.headers(1, encode_header_block([(b':status', b'200')]), end_stream=False)
        raw += writer.data(1, b'hello-world', end_stream=True)
        buf = FrameBuffer()
        buf.feed(raw)
        frames = buf.pop_all()
        self.assertGreaterEqual(len(frames), 2)
        self.assertEqual(frames[0].stream_id, 1)

    def test_settings_and_window_update(self):
        raw = serialize_settings({1: 1024, 4: 65535})
        buf = FrameBuffer()
        buf.feed(raw)
        frame = buf.pop_all()[0]
        settings = decode_settings(frame.payload)
        self.assertEqual(settings[1], 1024)
        self.assertEqual(serialize_window_update(1, 1)[3], 8)
