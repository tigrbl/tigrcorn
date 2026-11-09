from __future__ import annotations

from tigrcorn_transports.quic.connection import QuicConnection
from tigrcorn_security.tls13.extensions import TransportParameters


def test_default_transport_credit_supports_realtime_stream_bursts() -> None:
    parameters = TransportParameters()

    assert parameters.max_data == 16 * 1024 * 1024
    assert parameters.max_stream_data_uni == 2 * 1024 * 1024


def test_stream_receive_replenishes_connection_and_stream_windows() -> None:
    client = QuicConnection(
        is_client=True,
        secret=b"shared",
        local_cid=b"client01",
        remote_cid=b"server01",
    )
    server = QuicConnection(
        is_client=False,
        secret=b"shared",
        local_cid=b"server01",
        remote_cid=b"client01",
    )
    server.flow.configure_local_initial_limits(
        max_data=8,
        max_stream_data_bidi_local=8,
        max_stream_data_bidi_remote=8,
        max_stream_data_uni=8,
    )
    initial_connection_limit = server.flow.local_connection_window
    server.flow.ensure_stream(2)
    initial_stream_limit = server.flow.receive_window_for_stream(2)

    server.receive_datagram(client.send_stream_data(2, b"media", fin=False))

    assert initial_connection_limit == initial_stream_limit == 8
    assert server.flow.local_connection_window == 13
    assert server.flow.receive_window_for_stream(2) == 13
    assert len(server.take_pending_datagrams()) == 1
