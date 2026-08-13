from time import perf_counter

from tigrcorn_transports.quic import QuicConnection


def test_quic_packet_crypto_sustains_realtime_media_rate() -> None:
    packet_count = 250
    client = QuicConnection(
        is_client=True,
        secret=b"shared",
        local_cid=b"cli1cli1",
        remote_cid=b"srv1srv1",
    )
    server = QuicConnection(
        is_client=False,
        secret=b"shared",
        local_cid=b"srv1srv1",
        remote_cid=b"cli1cli1",
    )
    packets = [
        client.send_stream_data(2, b"x" * 1000, fin=False)
        for _ in range(packet_count)
    ]

    started = perf_counter()
    events = [server.receive_datagram(packet) for packet in packets]
    elapsed = perf_counter() - started

    assert all(any(event.kind == "stream" for event in batch) for batch in events)
    assert packet_count / max(elapsed, 1e-9) >= 1_000
