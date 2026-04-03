from tigrcorn.transports.quic import QuicConnection, decode_packet
from tigrcorn.transports.quic.connection import PACKET_SPACE_INITIAL
from tigrcorn.transports.quic.handshake import (
    QuicTlsHandshakeDriver,
    TransportParameters,
    generate_self_signed_certificate,
)
from tigrcorn.transports.quic.packets import (
    QuicVersionNegotiationPacket,
    split_coalesced_packets,
)
from tigrcorn.transports.quic.streams import FRAME_PING


def _issue_0rtt_ticket() -> tuple[bytes, bytes, object]:
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name='server.example',
        trusted_certificates=[cert_pem],
        enable_early_data=True,
    )
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name='server.example',
        certificate_pem=cert_pem,
        private_key_pem=key_pem,
        enable_early_data=True,
    )
    client_finished = client.receive(server.receive(client.initiate()))
    server.receive(client_finished)
    ticket_bytes = server.issue_session_ticket(max_early_data_size=1)
    client.receive(ticket_bytes)
    assert client.received_session_ticket is not None
    return cert_pem, key_pem, client.received_session_ticket


def test_client_initial_packets_roundtrip_even_when_minimum_size_padding_prevents_coalescing():
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
    server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
    datagrams = client.build_coalesced_datagrams(
        [
            (PACKET_SPACE_INITIAL, [FRAME_PING], None),
            (PACKET_SPACE_INITIAL, [FRAME_PING], None),
        ]
    )
    assert all(len(datagram) <= client.max_datagram_size for datagram in datagrams)
    packets = []
    events = []
    for datagram in datagrams:
        packets.extend(split_coalesced_packets(datagram))
        events.extend(server.receive_datagram(datagram))
    assert len(packets) == 2
    assert sum(1 for event in events if event.kind == 'packet') == 2
    assert all(event.packet_space == PACKET_SPACE_INITIAL for event in events if event.kind == 'packet')


def test_version_negotiation_is_generated_and_client_switches_to_supported_version():
    client = QuicConnection(
        is_client=True,
        version=0x1A2A3A4A,
        supported_versions=(1, 0x1A2A3A4A),
        secret=b'shared',
        local_cid=b'cli1cli1',
        remote_cid=b'srv1srv1',
    )
    server = QuicConnection(
        is_client=False,
        version=1,
        supported_versions=(1, 2),
        secret=b'shared',
        local_cid=b'srv1srv1',
    )
    events = server.receive_datagram(client.build_initial(), addr=('127.0.0.1', 4444))
    assert any(event.kind == 'version_negotiation_sent' for event in events)
    outbound = server.take_pending_datagrams()
    assert len(outbound) == 1
    negotiated = decode_packet(outbound[0])
    assert isinstance(negotiated, QuicVersionNegotiationPacket)
    client_events = client.receive_datagram(outbound[0])
    assert any(event.kind == 'version_negotiation' for event in client_events)
    assert client.version == 1
    assert client.state == 'version_negotiated'


def test_retry_roundtrip_and_new_token_runtime_validation():
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
    server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', require_retry=True)
    first_initial = client.build_initial()
    events = server.receive_datagram(first_initial, addr=('127.0.0.1', 4444))
    assert any(event.kind == 'retry' for event in events)
    retry_datagram = server.take_pending_datagrams()[0]
    retry_events = client.receive_datagram(retry_datagram)
    assert any(event.kind == 'retry' for event in retry_events)
    second_initial = client.build_initial()
    post_retry_events = server.receive_datagram(second_initial, addr=('127.0.0.1', 4444))
    assert any(event.kind == 'packet' for event in post_retry_events)
    assert server.address_validated

    token_server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
    token_client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
    token, new_token_datagram = token_server.issue_new_token(addr=('127.0.0.1', 5555))
    token_events = token_client.receive_datagram(new_token_datagram)
    assert any(event.kind == 'new_token' for event in token_events)
    assert token_client.peer_new_tokens == (token,)


def test_zero_rtt_stream_data_is_decrypted_after_client_hello():
    cert_pem, key_pem, ticket = _issue_0rtt_ticket()
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
    server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
    client.configure_handshake(
        QuicTlsHandshakeDriver(
            is_client=True,
            server_name='server.example',
            trusted_certificates=[cert_pem],
            session_ticket=ticket,
            enable_early_data=True,
        )
    )
    server.configure_handshake(
        QuicTlsHandshakeDriver(
            is_client=False,
            server_name='server.example',
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
            enable_early_data=True,
        )
    )
    server.receive_datagram(client.start_handshake(), addr=('127.0.0.1', 1111))
    zero_rtt_events = server.receive_datagram(client.send_early_stream_data(0, b'early', fin=False), addr=('127.0.0.1', 1111))
    assert any(
        event.kind == 'stream'
        and event.packet_space == '0rtt'
        and event.stream_id == 0
        and event.data == b'early'
        for event in zero_rtt_events
    )


def test_blocked_frames_and_connection_close_surface_runtime_events():
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
    server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
    blocked_events = server.receive_datagram(client.send_data_blocked())
    blocked_events.extend(server.receive_datagram(client.send_stream_data_blocked(0)))
    blocked_events.extend(server.receive_datagram(client.send_streams_blocked(10, bidirectional=False)))
    assert any(event.kind == 'data_blocked' for event in blocked_events)
    assert any(event.kind == 'stream_data_blocked' and event.stream_id == 0 for event in blocked_events)
    assert any(event.kind == 'streams_blocked' for event in blocked_events)

    close_events = server.receive_datagram(client.close(error_code=7, reason='bye', application=True))
    assert any(event.kind == 'application_close' for event in close_events)
    assert any(event.kind == 'close' and getattr(event.detail, 'application', False) for event in close_events)


def test_disable_active_migration_rejects_rebinding_and_preferred_address_is_reported():
    mover = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
    stationary = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
    stationary.local_transport_parameters = TransportParameters(disable_active_migration=True)
    stationary.address_validated = True
    stationary.receive_datagram(mover.send_stream_data(0, b'a'), addr=('127.0.0.1', 1000))
    migration_events = stationary.receive_datagram(mover.send_stream_data(4, b'b'), addr=('127.0.0.1', 1001))
    assert any(event.kind == 'close' for event in migration_events)
    assert stationary.take_pending_datagrams()

    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli2cli2', remote_cid=b'srv2srv2')
    server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv2srv2', remote_cid=b'cli2cli2')
    client.configure_handshake(QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem]))
    server.configure_handshake(
        QuicTlsHandshakeDriver(
            is_client=False,
            server_name='server.example',
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
            transport_parameters=TransportParameters(preferred_address=b'new-path'),
        )
    )
    server.receive_datagram(client.start_handshake(), addr=('127.0.0.1', 2000))
    client_events = []
    for datagram in server.take_handshake_datagrams():
        client_events.extend(client.receive_datagram(datagram, addr=('127.0.0.1', 2001)))
    assert any(event.kind == 'preferred_address' and event.detail == b'new-path' for event in client_events)
