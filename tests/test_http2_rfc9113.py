import asyncio
import unittest

from tigrcorn.config.defaults import default_config
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.codec import FLAG_END_HEADERS, FRAME_DATA, FRAME_HEADERS, HTTP2Frame, decode_settings
from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn.protocols.http2.state import H2StreamState


class _DummyReader:
    async def readexactly(self, n: int) -> bytes:
        raise EOFError


class _DummyWriter:
    def write(self, data: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None


class HTTP2RFC9113Tests(unittest.TestCase):
    def _handler(self) -> HTTP2ConnectionHandler:
        async def app(scope, receive, send):
            return None

        return HTTP2ConnectionHandler(
            app=app,
            config=default_config(),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
            reader=_DummyReader(),
            writer=_DummyWriter(),
            client=None,
            server=None,
            scheme='http',
        )

    def test_reject_duplicate_pseudo_header(self):
        handler = self._handler()
        state = H2StreamState(1)
        state.headers = [(b':method', b'GET'), (b':method', b'POST'), (b':path', b'/'), (b':scheme', b'http')]
        with self.assertRaises(ProtocolError):
            handler._build_request(state)

    def test_reject_pseudo_after_regular(self):
        handler = self._handler()
        state = H2StreamState(1)
        state.headers = [(b':method', b'GET'), (b'host', b'example'), (b':path', b'/'), (b':scheme', b'http')]
        with self.assertRaises(ProtocolError):
            handler._build_request(state)

    def test_reject_invalid_connection_header(self):
        handler = self._handler()
        state = H2StreamState(1)
        state.headers = [(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'http'), (b'connection', b'close')]
        with self.assertRaises(ProtocolError):
            handler._build_request(state)

    def test_reject_invalid_te_header(self):
        handler = self._handler()
        state = H2StreamState(1)
        state.headers = [(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'http'), (b'te', b'gzip')]
        with self.assertRaises(ProtocolError):
            handler._build_request(state)

    def test_reject_uppercase_header_field_name(self):
        handler = self._handler()
        state = H2StreamState(1)
        state.headers = [(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'http'), (b'Content-Type', b'text/plain')]
        with self.assertRaises(ProtocolError):
            handler._build_request(state)

    def test_reject_even_numbered_request_stream(self):
        handler = self._handler()
        frame = HTTP2Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=2, payload=b'')
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_headers(frame))

    def test_reject_data_before_headers(self):
        handler = self._handler()
        frame = HTTP2Frame(frame_type=FRAME_DATA, flags=0, stream_id=1, payload=b'data')
        with self.assertRaises(ProtocolError):
            asyncio.run(handler._handle_data(frame))

    def test_reject_invalid_settings_values(self):
        with self.assertRaises(ProtocolError):
            decode_settings((0x5).to_bytes(2, 'big') + (16000).to_bytes(4, 'big'))
        with self.assertRaises(ProtocolError):
            decode_settings((0x4).to_bytes(2, 'big') + (0x80000000).to_bytes(4, 'big'))
