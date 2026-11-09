import pytest

from tigrcorn.security.tls13 import CIPHER_TLS_AES_256_GCM_SHA384
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, TlsAlertError, TransportParameters, generate_self_signed_certificate


def test_custom_crypto_handshake_progression_and_certificate_verification() -> None:
    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name="server.example",
        trusted_certificates=[cert_pem],
        transport_parameters=TransportParameters(max_data=12345, active_connection_id_limit=6),
    )
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name="server.example",
        certificate_pem=cert_pem,
        private_key_pem=key_pem,
        transport_parameters=TransportParameters(max_data=99999, active_connection_id_limit=8),
    )
    client_hello = client.initiate()
    server_flight = server.receive(client_hello)
    client_finished = client.receive(server_flight)
    assert client.complete
    assert not server.complete
    assert client.peer_transport_parameters.max_data == 99999
    assert client.peer_transport_parameters.active_connection_id_limit == 8
    server.receive(client_finished)
    assert server.complete
    assert server.peer_transport_parameters.max_data == 12345
    assert server.peer_transport_parameters.active_connection_id_limit == 6


def test_untrusted_certificate_is_rejected() -> None:
    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    other_cert, _other_key = generate_self_signed_certificate("other.example")
    client = QuicTlsHandshakeDriver(is_client=True, trusted_certificates=[other_cert])
    server = QuicTlsHandshakeDriver(is_client=False, certificate_pem=cert_pem, private_key_pem=key_pem)
    with pytest.raises(Exception):
        client.receive(server.receive(client.initiate()))


def test_handshake_can_negotiate_tls_aes_256_gcm_sha384() -> None:
    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    client = QuicTlsHandshakeDriver(is_client=True, server_name="server.example", trusted_certificates=[cert_pem])
    server = QuicTlsHandshakeDriver(is_client=False, server_name="server.example", certificate_pem=cert_pem, private_key_pem=key_pem)
    server_flight = server.receive(client.initiate())
    client_finished = client.receive(server_flight)
    server.receive(client_finished)
    assert client._selected_cipher_suite == CIPHER_TLS_AES_256_GCM_SHA384
    assert server._selected_cipher_suite == CIPHER_TLS_AES_256_GCM_SHA384
    assert client.cipher_parameters.hash_name == "sha384"
    assert server.cipher_parameters.key_length == 32


def test_mutual_tls_handshake_completes_when_client_certificate_is_supplied() -> None:
    server_cert, server_key = generate_self_signed_certificate("server.example", purpose="server")
    client_cert, client_key = generate_self_signed_certificate("client.example", purpose="client")
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name="server.example",
        trusted_certificates=[server_cert],
        certificate_pem=client_cert,
        private_key_pem=client_key,
    )
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name="server.example",
        certificate_pem=server_cert,
        private_key_pem=server_key,
        trusted_certificates=[client_cert],
        require_client_certificate=True,
    )
    server_flight = server.receive(client.initiate())
    client_finished = client.receive(server_flight)
    server.receive(client_finished)
    assert client.complete
    assert server.complete
    assert server.peer_certificate_pem == client_cert


def test_mutual_tls_rejects_a_missing_client_certificate() -> None:
    server_cert, server_key = generate_self_signed_certificate("server.example", purpose="server")
    client_cert, _client_key = generate_self_signed_certificate("client.example", purpose="client")
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name="server.example",
        trusted_certificates=[server_cert],
    )
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name="server.example",
        certificate_pem=server_cert,
        private_key_pem=server_key,
        trusted_certificates=[client_cert],
        require_client_certificate=True,
    )
    server_flight = server.receive(client.initiate())
    client_finished = client.receive(server_flight)
    with pytest.raises(TlsAlertError) as ctx:
        server.receive(client_finished)
    assert ctx.value.description == 116
