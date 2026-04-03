import asyncio

from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.websocket.codec import close_frame
from tigrcorn.protocols.websocket.frames import (
import pytest
    OP_CLOSE,
    OP_PING,
    OP_TEXT,
    decode_close_payload,
    encode_close_payload,
    encode_frame,
    parse_frame_bytes,
)
from tigrcorn.protocols.websocket.handler import _WSAppSend


class _FakeWriter:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        return None


class TestWebSocketRFC6455Tests:
    def test_control_frames_must_not_fragment(self):
        with pytest.raises(ProtocolError):
            parse_frame_bytes(encode_frame(OP_PING, b"a", fin=False))

    def test_control_frames_must_be_small(self):
        with pytest.raises(ProtocolError):
            parse_frame_bytes(encode_frame(OP_PING, b"a" * 126, fin=True))

    def test_invalid_reserved_opcode_rejected(self):
        with pytest.raises(ProtocolError):
            parse_frame_bytes(encode_frame(0x3, b"data", fin=True))

    def test_invalid_close_code_rejected(self):
        with pytest.raises(ProtocolError):
            encode_close_payload(1005, "")
        with pytest.raises(ProtocolError):
            decode_close_payload((1005).to_bytes(2, "big"))

    def test_invalid_close_reason_utf8_rejected(self):
        payload = (1000).to_bytes(2, "big") + b"\xff"
        with pytest.raises(ProtocolError):
            decode_close_payload(payload)

    async def test_accept_subprotocol_must_be_offered(self):
        writer = _FakeWriter()
        sender = _WSAppSend(
            writer=writer,
            server_header=None,
            state={
                "accepted": False,
                "closed": False,
                "http_denied": False,
                "http_denial_status": 403,
                "http_denial_headers": [],
                "http_denial_started": False,
                "sec_websocket_key": b"dGhlIHNhbXBsZSBub25jZQ==",
            },
            accepted=asyncio.Event(),
            allowed_subprotocols=["chat"],
        )
        with pytest.raises(RuntimeError):
            await sender(
                {"type": "websocket.accept", "subprotocol": "superchat", "headers": []}
            )

    def test_close_frame_valid(self):
        raw = close_frame(1000, "ok")
        frame = parse_frame_bytes(raw)
        assert frame.opcode == OP_CLOSE
        code, reason = decode_close_payload(frame.payload)
        assert (code == reason), (1000, "ok")