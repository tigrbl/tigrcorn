import unittest

from tigrcorn.protocols.websocket.frames import decode_frame, encode_frame


class WebSocketFrameTests(unittest.TestCase):
    def test_encode_decode_text(self):
        raw = encode_frame(opcode=1, payload=b"hello", fin=True, masked=False)
        frame = decode_frame(raw)
        self.assertEqual(frame.opcode, 1)
        self.assertEqual(frame.payload, b"hello")


if __name__ == "__main__":
    unittest.main()
