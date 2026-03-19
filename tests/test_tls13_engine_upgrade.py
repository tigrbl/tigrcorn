import unittest

from tigrcorn.security.tls13.extensions import ExtensionType, OfferedPsks, TransportParameters, extension_dict
from tigrcorn.security.tls13.handshake import TlsAlertError
from tigrcorn.security.tls13.messages import ClientHello, KeyUpdate, ServerHello, decode_handshake_messages
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate


class Tls13EngineUpgradeTests(unittest.TestCase):
    def _complete_handshake(self, *, cert_pem: bytes, key_pem: bytes, server_name: str = 'server.example', enable_early_data: bool = False, session_ticket=None):
        client = QuicTlsHandshakeDriver(
            is_client=True,
            server_name=server_name,
            trusted_certificates=[cert_pem],
            session_ticket=session_ticket,
            enable_early_data=enable_early_data,
        )
        server = QuicTlsHandshakeDriver(
            is_client=False,
            server_name=server_name,
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
            enable_early_data=enable_early_data,
        )
        client_hello = client.initiate()
        server_flight = server.receive(client_hello)
        client_finished = client.receive(server_flight)
        server.receive(client_finished)
        return client, server

    def test_client_hello_is_real_tls_binary_and_carries_quic_transport_parameters(self):
        cert_pem, _key_pem = generate_self_signed_certificate('server.example')
        client = QuicTlsHandshakeDriver(
            is_client=True,
            server_name='server.example',
            trusted_certificates=[cert_pem],
            transport_parameters=TransportParameters(max_data=33333, active_connection_id_limit=6),
        )
        payload = client.initiate()
        self.assertEqual(payload[0], 1)
        messages = decode_handshake_messages(payload)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], ClientHello)
        offered = extension_dict(messages[0].extensions)
        self.assertEqual(offered[ExtensionType.ALPN], ('h3',))
        self.assertIsInstance(offered[ExtensionType.QUIC_TRANSPORT_PARAMETERS], TransportParameters)
        self.assertEqual(offered[ExtensionType.QUIC_TRANSPORT_PARAMETERS].max_data, 33333)
        self.assertEqual(offered[ExtensionType.QUIC_TRANSPORT_PARAMETERS].active_connection_id_limit, 6)

    def test_server_emits_hello_retry_request_when_client_key_share_is_missing(self):
        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        client = QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem])
        server = QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem)
        original = decode_handshake_messages(client.initiate())[0]
        retry_input = original.with_extensions(
            tuple(extension for extension in original.extensions if int(extension.extension_type) != ExtensionType.KEY_SHARE)
        )
        response = server.receive(retry_input.encode())
        messages = decode_handshake_messages(response)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], ServerHello)
        self.assertTrue(messages[0].is_hello_retry_request)

    def test_session_ticket_resumption_accepts_quic_0rtt_when_policy_allows(self):
        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        first_client, first_server = self._complete_handshake(cert_pem=cert_pem, key_pem=key_pem, enable_early_data=True)
        ticket_bytes = first_server.issue_session_ticket(max_early_data_size=1)
        first_client.receive(ticket_bytes)
        ticket = first_client.received_session_ticket
        self.assertIsNotNone(ticket)

        resumed_client = QuicTlsHandshakeDriver(
            is_client=True,
            server_name='server.example',
            trusted_certificates=[cert_pem],
            session_ticket=ticket,
            enable_early_data=True,
        )
        resumed_server = QuicTlsHandshakeDriver(
            is_client=False,
            server_name='server.example',
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
            enable_early_data=True,
        )
        client_hello = resumed_client.initiate()
        hello = decode_handshake_messages(client_hello)[0]
        self.assertIsInstance(hello, ClientHello)
        client_extensions = extension_dict(hello.extensions)
        self.assertTrue(client_extensions[ExtensionType.EARLY_DATA])
        self.assertIsInstance(client_extensions[ExtensionType.PRE_SHARED_KEY], OfferedPsks)

        server_flight = resumed_server.receive(client_hello)
        server_messages = decode_handshake_messages(server_flight)
        self.assertGreaterEqual(len(server_messages), 3)
        server_extensions = extension_dict(server_messages[1].extensions)
        self.assertTrue(server_extensions[ExtensionType.EARLY_DATA])

        client_finished = resumed_client.receive(server_flight)
        resumed_server.receive(client_finished)
        self.assertTrue(resumed_client.early_data_accepted)
        self.assertTrue(resumed_server.early_data_accepted)
        self.assertTrue(resumed_client.complete)
        self.assertTrue(resumed_server.complete)

    def test_0rtt_ticket_replay_is_not_accepted_twice(self):
        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        first_client, first_server = self._complete_handshake(cert_pem=cert_pem, key_pem=key_pem, enable_early_data=True)
        ticket_bytes = first_server.issue_session_ticket(max_early_data_size=1)
        first_client.receive(ticket_bytes)
        ticket = first_client.received_session_ticket
        self.assertIsNotNone(ticket)

        accepted_client = QuicTlsHandshakeDriver(
            is_client=True,
            server_name='server.example',
            trusted_certificates=[cert_pem],
            session_ticket=ticket,
            enable_early_data=True,
        )
        accepted_server = QuicTlsHandshakeDriver(
            is_client=False,
            server_name='server.example',
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
            enable_early_data=True,
        )
        accepted_finished = accepted_client.receive(accepted_server.receive(accepted_client.initiate()))
        accepted_server.receive(accepted_finished)
        self.assertTrue(accepted_server.early_data_accepted)

        replay_client = QuicTlsHandshakeDriver(
            is_client=True,
            server_name='server.example',
            trusted_certificates=[cert_pem],
            session_ticket=ticket,
            enable_early_data=True,
        )
        replay_server = QuicTlsHandshakeDriver(
            is_client=False,
            server_name='server.example',
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
            enable_early_data=True,
        )
        replay_flight = replay_server.receive(replay_client.initiate())
        replay_finished = replay_client.receive(replay_flight)
        replay_server.receive(replay_finished)
        self.assertFalse(replay_server.early_data_accepted)
        self.assertFalse(replay_client.early_data_accepted)

    def test_tls_key_update_handshake_message_is_rejected_for_quic(self):
        cert_pem, _key_pem = generate_self_signed_certificate('server.example')
        client = QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem])
        with self.assertRaises(TlsAlertError) as ctx:
            client.receive(KeyUpdate(request_update=1).encode())
        self.assertEqual(ctx.exception.description, 10)
        self.assertEqual(ctx.exception.quic_error_code, 0x0100 + 10)


if __name__ == '__main__':
    unittest.main()
