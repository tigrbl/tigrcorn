from tigrcorn.protocols.websocket.frames import decode_frame, encode_frame


def test_encode_decode_text() -> None:
    raw = encode_frame(opcode=1, payload=b"hello", fin=True, masked=False)
    frame = decode_frame(raw)
    assert frame.opcode == 1
    assert frame.payload == b"hello"
