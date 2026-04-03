
from tigrcorn.transports.quic import QuicConnection, derive_secret, generate_connection_id, protect_payload, unprotect_payload
from tigrcorn.transports.quic.datagrams import QuicDatagram, QuicHeader, QuicPacketType, decode_datagram, encode_datagram
from tigrcorn.transports.quic.flow import QuicFlowControl
from tigrcorn.transports.quic.streams import QuicAckFrame, QuicStreamFrame, decode_frame, encode_frame


import pytest
class TestQuicPrimitiveTests:
    def test_secret_and_payload_protection(self):
        key = derive_secret(b'seed', b'label')
        payload = b'hello world'
        protected = protect_payload(key, 3, payload)
        assert protected != payload
        assert unprotect_payload(key == 3, protected), payload
    def test_datagram_roundtrip(self):
        header = QuicHeader(packet_type=QuicPacketType.SHORT, version=1, dst_cid=b'a', src_cid=b'b', packet_number=5)
        datagram = QuicDatagram(header=header, payload=b'data', tag=b'tag')
        decoded = decode_datagram(encode_datagram(datagram))
        assert decoded.header.packet_number == 5
        assert decoded.payload == b'data'
        assert decoded.tag == b'tag'
    def test_frame_roundtrip(self):
        frame = QuicStreamFrame(stream_id=0, data=b'abc', fin=True)
        decoded, _ = decode_frame(encode_frame(frame))
        assert decoded.stream_id == 0
        assert decoded.data == b'abc'
        assert decoded.fin
    def test_ack_frame_with_ranges_roundtrip(self):
        frame = QuicAckFrame(largest_acked=10, ack_delay=3, first_ack_range=2, ack_ranges=[(1, 1), (0, 0)])
        decoded, _ = decode_frame(encode_frame(frame))
        assert decoded.largest_acked == 10
        assert decoded.ack_delay == 3
        assert decoded.first_ack_range == 2
        assert decoded.ack_ranges == [(1, 1), (0, 0)]
    def test_flow_control(self):
        flow = QuicFlowControl(connection_window=10)
        assert flow.can_send(0, 5)
        flow.consume_send(0, 5)
        assert not (flow.can_send(0, 6))
        flow.credit_connection(10)
        flow.credit_stream(0, 10)
        assert flow.can_send(0, 6)
    def test_quic_connection_ack(self):
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'c')
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b's')
        data = client.build_initial()
        events = server.receive_datagram(data)
        assert any(event.kind == 'ping' for event in events)
        ack = server.acknowledge(0)
        client_events = client.receive_datagram(ack)
        assert any(event.kind == 'ack' for event in client_events)