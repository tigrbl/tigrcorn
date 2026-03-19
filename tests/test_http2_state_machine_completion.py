import asyncio
import unittest

from tigrcorn.config.defaults import default_config
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import (
    FLAG_ACK,
    FLAG_END_HEADERS,
    FLAG_END_STREAM,
    FRAME_CONTINUATION,
    FRAME_DATA,
    FRAME_GOAWAY,
    FRAME_HEADERS,
    FRAME_PRIORITY,
    FRAME_PUSH_PROMISE,
    FRAME_SETTINGS,
    FRAME_WINDOW_UPDATE,
    FrameBuffer,
    HTTP2Frame,
    parse_goaway,
    serialize_goaway,
)
from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn.protocols.http2.hpack import encode_header_block
from tigrcorn.protocols.http2.state import H2StreamLifecycle, H2StreamState


class _DummyReader:
    async def readexactly(self, n: int) -> bytes:
        raise EOFError


class _CapturingWriter:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return None


class HTTP2StateMachineCompletionTests(unittest.TestCase):
    def _handler(self) -> HTTP2ConnectionHandler:
        async def app(scope, receive, send):
            return None

        return HTTP2ConnectionHandler(
            app=app,
            config=default_config(),
            access_logger=AccessLogger(configure_logging("warning"), enabled=False),
            reader=_DummyReader(),
            writer=_CapturingWriter(),
            client=None,
            server=None,
            scheme="http",
        )

    def _request_headers(self, *, method: bytes = b"GET") -> bytes:
        return encode_header_block([
            (b":method", method),
            (b":path", b"/"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ])

    def test_stream_lifecycle_transitions_are_explicit(self):
        state = H2StreamState(1)
        self.assertEqual(state.lifecycle, H2StreamLifecycle.IDLE)
        state.open_remote(end_stream=False)
        self.assertEqual(state.lifecycle, H2StreamLifecycle.OPEN)
        state.receive_end_stream()
        self.assertEqual(state.lifecycle, H2StreamLifecycle.HALF_CLOSED_REMOTE)
        state.send_end_stream()
        self.assertEqual(state.lifecycle, H2StreamLifecycle.CLOSED)
        self.assertTrue(state.closed)

    def test_reserved_local_stream_transitions_are_explicit(self):
        state = H2StreamState(2)
        state.reserve_local()
        self.assertEqual(state.lifecycle, H2StreamLifecycle.RESERVED_LOCAL)
        state.open_local_reserved(end_stream=False)
        self.assertEqual(state.lifecycle, H2StreamLifecycle.HALF_CLOSED_REMOTE)
        state.send_end_stream()
        self.assertEqual(state.lifecycle, H2StreamLifecycle.CLOSED)
        self.assertTrue(state.closed)

    def test_first_frame_after_preface_must_be_settings(self):
        handler = self._handler()
        frame = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=b"")
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_frame(frame))

    def test_max_concurrent_streams_are_enforced(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        handler.state.local_settings[0x3] = 1
        first = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=self._request_headers())
        second = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=3, payload=self._request_headers())
        asyncio.run(handler._handle_headers(first))
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_headers(second))

    def test_continuation_does_not_interpret_end_stream_flag(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        first = HTTP2Frame(
            frame_type=FRAME_HEADERS,
            flags=0,
            stream_id=1,
            payload=self._request_headers(),
        )
        asyncio.run(handler._handle_headers(first))
        state = handler.streams.find(1)
        self.assertIsNotNone(state)
        self.assertTrue(state.awaiting_continuation)
        cont = HTTP2Frame(
            frame_type=FRAME_CONTINUATION,
            flags=FLAG_END_HEADERS | FLAG_END_STREAM,
            stream_id=1,
            payload=b"",
        )
        asyncio.run(handler._handle_continuation(cont))
        state = handler.streams.find(1)
        self.assertIsNotNone(state)
        self.assertFalse(state.end_stream_received)
        self.assertEqual(state.lifecycle, H2StreamLifecycle.OPEN)

    def test_priority_self_dependency_is_rejected(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        payload = (1).to_bytes(4, "big") + bytes([16])
        frame = HTTP2Frame(frame_type=FRAME_PRIORITY, flags=0, stream_id=1, payload=payload)
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_frame(frame))

    def test_client_push_promise_is_rejected(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        frame = HTTP2Frame(frame_type=FRAME_PUSH_PROMISE, flags=0, stream_id=1, payload=b"\x00\x00\x00\x02")
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_frame(frame))

    def test_window_update_is_thresholded_not_immediate(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        writer = handler.writer
        headers = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=self._request_headers())
        asyncio.run(handler._handle_headers(headers))
        data_small = HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"a" * 32_000)
        asyncio.run(handler._handle_data(data_small))
        self.assertEqual(writer.writes, [])
        data_threshold = HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"b" * 1_000)
        asyncio.run(handler._handle_data(data_threshold))
        buf = FrameBuffer()
        for raw in writer.writes:
            buf.feed(raw)
        frames = buf.pop_all()
        self.assertEqual([frame.frame_type for frame in frames], [FRAME_WINDOW_UPDATE, FRAME_WINDOW_UPDATE])
        self.assertEqual(frames[0].stream_id, 0)
        self.assertEqual(frames[1].stream_id, 1)

    def test_stream_receive_flow_control_overflow_is_rejected(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        headers = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=self._request_headers())
        asyncio.run(handler._handle_headers(headers))
        state = handler.streams.find(1)
        self.assertIsNotNone(state)
        state.receive_window.available = 8
        frame = HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b"0123456789")
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_data(frame))

    def test_goaway_last_stream_id_must_not_increase(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        first = HTTP2Frame(frame_type=FRAME_GOAWAY, flags=0, stream_id=0, payload=serialize_goaway(5)[9:])
        second = HTTP2Frame(frame_type=FRAME_GOAWAY, flags=0, stream_id=0, payload=serialize_goaway(7)[9:])
        asyncio.run(handler._handle_frame(first))
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_frame(second))

    def test_new_stream_after_peer_goaway_is_rejected(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        goaway = HTTP2Frame(frame_type=FRAME_GOAWAY, flags=0, stream_id=0, payload=serialize_goaway(0)[9:])
        asyncio.run(handler._handle_frame(goaway))
        frame = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=self._request_headers())
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_headers(frame))

    def test_window_update_on_closed_stream_is_ignored(self):
        handler = self._handler()
        handler.state.remote_settings_seen = True
        headers = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=1, payload=self._request_headers())
        asyncio.run(handler._handle_headers(headers))
        handler.streams.close(1)
        frame = HTTP2Frame(frame_type=FRAME_WINDOW_UPDATE, flags=0, stream_id=1, payload=(1).to_bytes(4, "big"))
        asyncio.run(handler._handle_frame(frame))

    def test_goaway_payload_roundtrip_used_by_handler(self):
        last_stream_id, error_code, debug = parse_goaway(serialize_goaway(3, error_code=2, debug_data=b"dbg")[9:])
        self.assertEqual((last_stream_id, error_code, debug), (3, 2, b"dbg"))


if __name__ == "__main__":
    unittest.main()
