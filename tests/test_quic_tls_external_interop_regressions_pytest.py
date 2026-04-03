from __future__ import annotations


from cryptography import x509

from tigrcorn.security.tls13.handshake import QuicTlsHandshakeDriver
from tigrcorn.transports.quic.connection import QuicConnection
from tigrcorn.transports.quic.packets import decode_packet


import pytest
class TestQuicTlsExternalInteropRegressionTests:
    def test_tls_certificate_entries_are_der_encoded(self):
        driver = QuicTlsHandshakeDriver(is_client=False, server_name='localhost')
        entries = driver._certificate_entry_chain()
        assert entries
        certificate = x509.load_der_x509_certificate(entries[0].cert_data)
        assert certificate.subject.rfc4514_string() == 'CN=localhost'
        assert not (entries[0].cert_data.startswith(b'-----BEGIN CERTIFICATE-----'))
    def test_zero_length_remote_cid_is_preserved_when_encoding_initial(self):
        connection = QuicConnection(
            is_client=False,
            secret=b'shared-secret',
            local_cid=b'servercid',
            remote_cid=b'',
        )
        raw = connection._encode_initial([])
        packet = decode_packet(raw)
        assert packet.destination_connection_id == b''
        assert packet.source_connection_id == b'servercid'
        assert connection.remote_cid == b''