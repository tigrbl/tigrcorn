
from tigrcorn.config.defaults import default_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http3.codec import FRAME_GOAWAY, FRAME_SETTINGS, STREAM_TYPE_CONTROL, decode_frame, decode_settings
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn.utils.bytes import decode_quic_varint, encode_quic_varint


import pytest
class TestHTTP3RFC9114Tests:
    def test_control_stream_prefix_and_settings(self):
        core = HTTP3ConnectionCore()
        payload = core.encode_control_stream({1: 0, 6: 1200})
        stream_type, offset = decode_quic_varint(payload, 0)
        assert stream_type == STREAM_TYPE_CONTROL
        frame, _ = decode_frame(payload, offset)
        assert frame.frame_type == FRAME_SETTINGS
        assert decode_settings(frame.payload) == {1: 0, 6: 1200}
    def test_goaway_uses_varint_payload(self):
        core = HTTP3ConnectionCore()
        raw = core.encode_goaway(33)
        frame, _ = decode_frame(raw, 0)
        assert frame.frame_type == FRAME_GOAWAY
        stream_id, _ = decode_quic_varint(frame.payload, 0)
        assert stream_id == 33
    def test_decode_frame_rejects_truncation(self):
        with pytest.raises(ProtocolError):
            decode_frame(encode_quic_varint(1) + encode_quic_varint(5) + b'ab')

    def test_validate_request_headers_rejects_duplicates(self):
        async def app(scope, receive, send):
            return None

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3']),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )
        with pytest.raises(ProtocolError):
            handler._validate_request_headers([(b':method', b'GET'), (b':method', b'POST'), (b':path', b'/'), (b':scheme', b'https')])

    def test_validate_request_headers_rejects_connection_specific(self):
        async def app(scope, receive, send):
            return None

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3']),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )
        with pytest.raises(ProtocolError):
            handler._validate_request_headers([(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'https'), (b'connection', b'close')])
