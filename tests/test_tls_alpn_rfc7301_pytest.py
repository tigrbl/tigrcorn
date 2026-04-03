
from tigrcorn.security.tls13.handshake import QuicTlsHandshakeDriver
import pytest
from tigrcorn.transports.quic.handshake import (
    TransportParameters,
    generate_self_signed_certificate,
)



def test_tls13_handshake_selects_first_mutual_alpn():
    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name="server.example",
        trusted_certificates=[cert_pem],
        alpn=("h3", "h2"),
        transport_parameters=TransportParameters(max_data=11111),
    )
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name="server.example",
        certificate_pem=cert_pem,
        private_key_pem=key_pem,
        alpn=("h2", "h3"),
        transport_parameters=TransportParameters(max_data=22222),
    )
    client_hello = client.initiate()
    server_flight = server.receive(client_hello)
    client_finished = client.receive(server_flight)
    server.receive(client_finished)
    assert client.complete
    assert server.complete
    assert client.selected_alpn == "h3"
    assert server.selected_alpn == "h3"
def test_tls13_handshake_rejects_when_no_mutual_alpn_exists():
    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name="server.example",
        trusted_certificates=[cert_pem],
        alpn=("h3",),
    )
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name="server.example",
        certificate_pem=cert_pem,
        private_key_pem=key_pem,
        alpn=("h2",),
    )
    with pytest.raises(Exception, match="ALPN negotiation failed"):
        server.receive(client.initiate())


