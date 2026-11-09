from __future__ import annotations

from tigrcorn_transports.quic.connection import QuicConnection


def test_large_stream_write_is_packetized_below_effective_udp_ceiling() -> None:
    connection = QuicConnection(is_client=False, max_datagram_size=1200)
    payload = b"media-segment" * 1000

    packets = connection.send_stream_data_packets(3, payload, fin=True)

    assert len(packets) > 1
    assert all(len(packet) <= 1200 for packet in packets)
    stream = connection.streams.get(3)
    assert stream.send_offset == len(payload)
    assert stream.send_final_size == len(payload)
