from __future__ import annotations

import unittest

from cryptography import x509

from tigrcorn.security.tls13.handshake import QuicTlsHandshakeDriver
from tigrcorn.transports.quic.connection import QuicConnection
from tigrcorn.transports.quic.packets import decode_packet


class QuicTlsExternalInteropRegressionTests(unittest.TestCase):
    def test_tls_certificate_entries_are_der_encoded(self):
        driver = QuicTlsHandshakeDriver(is_client=False, server_name='localhost')
        entries = driver._certificate_entry_chain()
        self.assertTrue(entries)
        certificate = x509.load_der_x509_certificate(entries[0].cert_data)
        self.assertEqual(certificate.subject.rfc4514_string(), 'CN=localhost')
        self.assertFalse(entries[0].cert_data.startswith(b'-----BEGIN CERTIFICATE-----'))

    def test_zero_length_remote_cid_is_preserved_when_encoding_initial(self):
        connection = QuicConnection(
            is_client=False,
            secret=b'shared-secret',
            local_cid=b'servercid',
            remote_cid=b'',
        )
        raw = connection._encode_initial([])
        packet = decode_packet(raw)
        self.assertEqual(packet.destination_connection_id, b'')
        self.assertEqual(packet.source_connection_id, b'servercid')
        self.assertEqual(connection.remote_cid, b'')
