
from tigrcorn.protocols.http3 import HTTP3ConnectionCore, decode_field_section, encode_field_section, encode_frame, parse_frames
from tigrcorn.protocols.http3.codec import FRAME_HEADERS
from tigrcorn.transports.quic import QuicConnection


import pytest
class TestQuicHttp3CoreTests:
    def test_quic_stream_roundtrip(self):
        client = QuicConnection(is_client=True, local_cid=b'c1', remote_cid=b's1', secret=b'shared-secret')
        server = QuicConnection(is_client=False, local_cid=b's1', remote_cid=b'c1', secret=b'shared-secret')
        data = client.send_stream_data(0, b'hello', fin=True)
        events = server.receive_datagram(data)
        stream_events = [event for event in events if event.kind == 'stream']
        assert len(stream_events) == 1
        assert stream_events[0].data == b'hello'
        assert stream_events[0].fin
    def test_http3_field_section_roundtrip(self):
        headers = [(b':method', b'GET'), (b':path', b'/'), (b'content-type', b'text/plain')]
        encoded = encode_field_section(headers)
        assert decode_field_section(encoded) == headers
    def test_http3_request_stream(self):
        core = HTTP3ConnectionCore()
        request = core.get_request(0)
        payload = request.encode_request([(b':method', b'GET'), (b':path', b'/')], b'hello')
        state = core.receive_stream_data(0, payload)
        assert state is not None
        assert state is not None
        assert state.body == b'hello'
        assert (b':method' in b'GET'), state.headers
