
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, TransportParameters, generate_self_signed_certificate
from tigrcorn.transports.quic.recovery import QuicLossRecovery


import pytest
class TestQuicRFCUpgradePathTests:
    def test_transport_parameters_binary_roundtrip_preserves_extensions(self):
        params = TransportParameters(
            max_data=123456,
            max_stream_data_bidi_local=2222,
            max_stream_data_bidi_remote=3333,
            max_stream_data_uni=4444,
            max_streams_bidi=10,
            max_streams_uni=11,
            idle_timeout=45_000,
            active_connection_id_limit=6,
            max_udp_payload_size=1400,
            ack_delay_exponent=4,
            max_ack_delay=31,
            disable_active_migration=True,
            initial_source_connection_id=b'cli-cid',
            original_destination_connection_id=b'orig-cid',
            stateless_reset_token=b'0123456789abcdef',
            unknown_parameters={0x40: b'opaque'},
        )
        decoded = TransportParameters.from_bytes(params.to_bytes())
        assert decoded.max_data == 123456
        assert decoded.max_stream_data_uni == 4444
        assert decoded.active_connection_id_limit == 6
        assert decoded.disable_active_migration
        assert decoded.initial_source_connection_id == b'cli-cid'
        assert decoded.original_destination_connection_id == b'orig-cid'
        assert decoded.stateless_reset_token == b'0123456789abcdef'
        assert decoded.unknown_parameters[0x40] == b'opaque'
    def test_server_handshake_flight_is_split_across_initial_and_handshake_spaces(self):
        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        client = QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem])
        server = QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem)
        server_flight = server.receive(client.initiate())
        flights = server.outbound_flights(server_flight)
        assert [flight.packet_space for flight in flights] == ['initial', 'handshake']
    def test_crypto_reassembly_waits_for_missing_prefix(self):
        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
        client.configure_handshake(QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem]))
        server.configure_handshake(QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem))
        payload = client.handshake_driver.initiate()
        midpoint = len(payload) // 2
        server.receive_datagram(client.send_crypto_data(payload[midpoint:], offset=midpoint, packet_space='initial'))
        assert server.take_handshake_datagrams() == []
        server.receive_datagram(client.send_crypto_data(payload[:midpoint], offset=0, packet_space='initial'))
        assert server.take_handshake_datagrams()
    def test_key_update_allows_post_update_short_packets(self):
        left = QuicConnection(is_client=True, secret=b'shared-secret', local_cid=b'c1c1c1c1', remote_cid=b's1s1s1s1')
        right = QuicConnection(is_client=False, secret=b'shared-secret', local_cid=b's1s1s1s1', remote_cid=b'c1c1c1c1')
        events = right.receive_datagram(left.send_stream_data(0, b'before', fin=True))
        assert any(event.kind == 'stream' and event.data == b'before' for event in events)
        left.initiate_key_update()
        events = right.receive_datagram(left.send_stream_data(4, b'after', fin=True))
        assert any(event.kind == 'stream' and event.data == b'after' for event in events)
class TestQuicRecoveryUpgradePathTests:
    def test_packet_number_spaces_are_isolated(self):
        recovery = QuicLossRecovery(max_datagram_size=1200)
        recovery.on_packet_sent(1, 1200, sent_time=0.0, packet_space='initial')
        recovery.on_packet_sent(1, 1200, sent_time=0.0, packet_space='application')
        recovery.on_ack_received([1], now=0.1, packet_space='application')
        assert 1 in recovery.spaces['initial'].outstanding
        assert 1 not in recovery.spaces['application'].outstanding
    def test_persistent_congestion_collapses_congestion_window(self):
        recovery = QuicLossRecovery(max_datagram_size=1200)
        recovery.on_packet_sent(0, 1200, sent_time=0.0)
        recovery.on_ack_received([0], now=0.1)
        for packet_number, sent_time in [(1, 0.2), (2, 1.0), (3, 2.0), (4, 3.0)]:
            recovery.on_packet_sent(packet_number, 1200, sent_time=sent_time, packet_space='application')
        recovery.on_ack_received([4], now=3.2, packet_space='application')
        assert recovery.persistent_congestion
        assert recovery.congestion_window == recovery.minimum_congestion_window
    def test_pacing_budget_replenishes_after_time_passes(self):
        recovery = QuicLossRecovery(max_datagram_size=1200)
        recovery.on_packet_sent(1, 1200, sent_time=0.0)
        depleted_budget = recovery.pacing_budget
        replenished_budget = recovery.available_send_budget(now=1.0)
        assert depleted_budget < recovery.congestion_window
        assert replenished_budget > depleted_budget
