from __future__ import annotations

import asyncio
import contextlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from cryptography.x509 import ocsp

from tests.fixtures_pkg.interop_ocsp_fixtures import (
    CertificateFactory,
    ResponseSpec,
    der_ocsp,
    pem_certificate,
    revocation_http_server,
)
from tigrcorn.config.model import ListenerConfig
from tigrcorn.constants import H2_PREFACE
from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.http2.codec import (
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_SETTINGS,
    FrameBuffer,
    FrameWriter,
    decode_settings,
    serialize_frame,
    serialize_settings,
)
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.security.tls import (
    _TLS_ALERT_CLOSE_NOTIFY,
    _build_record_state,
    _decrypt_record,
    _encrypt_record,
    PackageOwnedTLSConnection,
    build_server_ssl_context,
    verify_certificate_chain,
)
from tigrcorn.security.tls13 import SIG_ECDSA_SECP384R1_SHA384
from tigrcorn.security.tls13.handshake import (
    Certificate,
    CertificateVerify,
    EncryptedExtensions,
    Finished,
    QuicTlsHandshakeDriver,
    ServerHello,
    generate_self_signed_certificate,
)
from tigrcorn.security.tls13.messages import decode_handshake_message, decode_handshake_messages
from tigrcorn.security.x509.path import CertificatePurpose, CertificateValidationPolicy, RevocationFetchPolicy, RevocationMode


from tests.support.tls_identity_interop import (
    INDEPENDENT,
    _FakeReader,
    _FakeWriter,
    _NOW,
    _client_context,
    _start_tls_server,
)

def test_external_peer_interop_artifact_is_preserved_and_passing() -> None:
    result = json.loads((INDEPENDENT / 'tls-server-ocsp-validation-openssl-client' / 'result.json').read_text(encoding='utf-8'))
    assert result['passed'] is True
    assert result['peer']['exit_code'] == 0
    assert result['transcript']['peer']['handshake_established'] is True
    assert result['negotiation']['peer']['verification'] == 'OK'


def test_backend_control_builds_tls_context_with_explicit_alpn_and_client_auth() -> None:
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cert_path = root / 'cert.pem'
        key_path = root / 'key.pem'
        ca_path = root / 'ca.pem'
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)
        ca_path.write_bytes(cert_pem)
        listener = ListenerConfig(
            kind='tcp',
            host='server.example',
            port=443,
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
            ssl_ca_certs=str(ca_path),
            ssl_require_client_cert=True,
            alpn_protocols=['h2', 'http/1.1'],
            ocsp_mode='require',
            revocation_fetch=False,
        )
        context = build_server_ssl_context(listener)
    assert context is not None
    assert context.alpn_protocols == ('h2', 'http/1.1')
    assert context.require_client_certificate is True
    assert context.validation_policy.revocation_mode is RevocationMode.REQUIRE


def test_tls13_record_layer_round_trips_application_plaintext() -> None:
    secret = bytes.fromhex('11' * 32)
    outbound = _build_record_state(secret, key_length=16, iv_length=12, hash_name='sha256')
    inbound = _build_record_state(secret, key_length=16, iv_length=12, hash_name='sha256')
    record = _encrypt_record(b'hello-tls-record', 23, outbound)
    plaintext, inner_type = _decrypt_record(record[5:], inbound)
    assert plaintext == b'hello-tls-record'
    assert inner_type == 23


def test_tls13_state_transition_completes_bidirectional_handshake() -> None:
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem])
    server = QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem)
    client_hello = client.initiate()
    server_flight = server.receive(client_hello)
    client_finished = client.receive(server_flight)
    assert client.complete is True
    assert server.complete is False
    server.receive(client_finished)
    assert server.complete is True


def test_tls13_server_transcript_preserves_exact_client_hello_wire_bytes() -> None:
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem])
    server = QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem)
    encoded = client.initiate()
    message, consumed = decode_handshake_message(encoded)
    assert consumed == len(encoded)
    wire_marker = b'wire-preservation-marker'

    server._handle_client_hello(message, raw_message=encoded + wire_marker)

    assert server._last_client_hello_bytes == encoded + wire_marker
    assert server._transcript.as_bytes().startswith(encoded + wire_marker)


def test_tls13_state_transition_supports_p384_certificate() -> None:
    key = ec.generate_private_key(ec.SECP384R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'server.example')])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('server.example')]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(key, hashes.SHA384())
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name='server.example',
        trusted_certificates=[cert_pem],
    )
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name='server.example',
        certificate_pem=cert_pem,
        private_key_pem=key_pem,
    )
    server_flight = server.receive(client.initiate())
    messages = decode_handshake_messages(server_flight)
    certificate_verify = next(message for message in messages if isinstance(message, CertificateVerify))
    assert certificate_verify.algorithm == SIG_ECDSA_SECP384R1_SHA384
    client_finished = client.receive(server_flight)
    server.receive(client_finished)
    assert client.complete is True
    assert server.complete is True

def test_tls13_shutdown_emits_close_notify_once() -> None:
    async def scenario() -> None:
        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cert_path = root / 'cert.pem'
            key_path = root / 'key.pem'
            cert_path.write_bytes(cert_pem)
            key_path.write_bytes(key_pem)
            context = build_server_ssl_context(
                ListenerConfig(
                    kind='tcp',
                    host='server.example',
                    port=443,
                    ssl_certfile=str(cert_path),
                    ssl_keyfile=str(key_path),
                    alpn_protocols=['http/1.1'],
                )
            )
            assert context is not None
            writer = _FakeWriter()
            connection = PackageOwnedTLSConnection(_FakeReader(), writer, context)
            secret = bytes.fromhex('22' * 32)
            connection._application_outbound = _build_record_state(secret, key_length=16, iv_length=12, hash_name='sha256')
            inbound = _build_record_state(secret, key_length=16, iv_length=12, hash_name='sha256')
            connection.close()
            connection.close()
            assert len(writer.records) == 1
            plaintext, inner_type = _decrypt_record(writer.records[0][5:], inbound)
            assert inner_type == 21
            assert plaintext == bytes([1, _TLS_ALERT_CLOSE_NOTIFY])

    asyncio.run(scenario())


def test_tls13_handshake_messages_include_certificate_verify_and_finished() -> None:
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem], alpn='h2')
    server = QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem, alpn='h2')
    server_flight = server.receive(client.initiate())
    messages = decode_handshake_messages(server_flight)
    assert isinstance(messages[0], ServerHello)
    assert any(isinstance(message, EncryptedExtensions) for message in messages)
    assert any(isinstance(message, Certificate) for message in messages)
    assert any(isinstance(message, CertificateVerify) for message in messages)
    assert any(isinstance(message, Finished) for message in messages)


def test_tls_alpn_policy_prefers_first_mutual_protocol() -> None:
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem], alpn=('h3', 'h2'))
    server = QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem, alpn=('h2', 'h3'))
    client_finished = client.receive(server.receive(client.initiate()))
    server.receive(client_finished)
    assert client.selected_alpn == 'h3'
    assert server.selected_alpn == 'h3'


def test_tls_server_name_indication_rejects_hostname_mismatch() -> None:
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicTlsHandshakeDriver(is_client=True, server_name='wrong.example', trusted_certificates=[cert_pem], alpn='h2')
    server = QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem, alpn='h2')
    with pytest.raises(Exception, match='subjectAltName'):
        client.receive(server.receive(client.initiate()))


def test_tls_status_request_policy_rejects_stale_ocsp_in_require_mode() -> None:
    factory = CertificateFactory()
    root, root_key = factory.make_ca('Root CA')
    with revocation_http_server({}) as server:
        leaf, _leaf_key = factory.make_client_leaf(
            'client.example',
            issuer_cert=root,
            issuer_key=root_key,
            ocsp_uris=(server.url('/stale-ocsp'),),
        )
        stale_response = factory.make_ocsp_response(
            leaf,
            root,
            root_key,
            cert_status=ocsp.OCSPCertStatus.GOOD,
            next_update=_NOW - timedelta(hours=1),
            this_update=_NOW - timedelta(days=1),
        )
        server.responses[('POST', '/stale-ocsp')] = ResponseSpec(
            body=der_ocsp(stale_response),
            headers={'Content-Type': 'application/ocsp-response'},
        )
        policy = CertificateValidationPolicy(purpose=CertificatePurpose.CLIENT_AUTH, revocation_mode=RevocationMode.REQUIRE)
        with pytest.raises(ProtocolError, match='revocation status could not be established'):
            verify_certificate_chain([pem_certificate(leaf)], [pem_certificate(root)], policy=policy)


def test_x509_certificate_profiles_reject_client_auth_only_leaf_for_server_use() -> None:
    cert_pem, _key_pem = generate_self_signed_certificate('server.example', purpose='client')
    with pytest.raises(ProtocolError, match='required EKU not found'):
        verify_certificate_chain([cert_pem], [cert_pem], server_name='server.example')


def test_x509_path_validation_rejects_path_length_violation() -> None:
    factory = CertificateFactory()
    root, root_key = factory.make_ca('Root CA', path_length=0)
    intermediate, intermediate_key = factory.make_ca('Intermediate CA', issuer_cert=root, issuer_key=root_key, path_length=0)
    leaf, _leaf_key = factory.make_server_leaf(
        'service.example',
        issuer_cert=intermediate,
        issuer_key=intermediate_key,
        san_dns=('service.example',),
    )
    with pytest.raises(ProtocolError, match='chain verification failed'):
        verify_certificate_chain([pem_certificate(leaf), pem_certificate(intermediate)], [pem_certificate(root)], server_name='service.example')


def test_ocsp_policy_soft_fail_and_require_modes_diverge() -> None:
    factory = CertificateFactory()
    root, root_key = factory.make_ca('Root CA', path_length=1)
    issuer, issuer_key = factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
    leaf, _ = factory.make_client_leaf('client.unreachable.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=('http://127.0.0.1:9/unreachable',))
    soft_policy = CertificateValidationPolicy(
        purpose=CertificatePurpose.CLIENT_AUTH,
        revocation_mode=RevocationMode.SOFT_FAIL,
        revocation_fetch_policy=RevocationFetchPolicy(timeout_seconds=0.25),
    )
    require_policy = CertificateValidationPolicy(
        purpose=CertificatePurpose.CLIENT_AUTH,
        revocation_mode=RevocationMode.REQUIRE,
        revocation_fetch_policy=RevocationFetchPolicy(timeout_seconds=0.25),
    )
    verified = verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], [pem_certificate(root), pem_certificate(issuer)], policy=soft_policy)
    assert verified.serial_number == leaf.serial_number
    with pytest.raises(ProtocolError, match='OCSP http://127.0.0.1:9/unreachable'):
        verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], [pem_certificate(root), pem_certificate(issuer)], policy=require_policy)


def test_https_service_identity_enforces_hostname_match() -> None:
    cert_pem, _key_pem = generate_self_signed_certificate('server.example')
    with pytest.raises(ProtocolError, match='subjectAltName'):
        verify_certificate_chain([cert_pem], [cert_pem], server_name='wrong.example')


def test_https_http11_over_package_owned_tls_negotiates_http11() -> None:
    async def scenario() -> None:
        seen: dict[str, object] = {}

        async def app(scope, receive, send):
            seen['scope'] = scope
            event = await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': event['body'], 'more_body': False})

        server, port = await _start_tls_server(app, http_versions=['1.1'])
        try:
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                port,
                ssl=_client_context(alpn=['http/1.1']),
                server_hostname='localhost',
            )
            writer.write(b'POST /tls HTTP/1.1\r\nHost: localhost\r\nContent-Length: 5\r\n\r\nhello')
            await writer.drain()
            data = await reader.read(65535)
            assert b'200 OK' in data
            tls_ext = seen['scope']['extensions']['tls']
            assert tls_ext['selected_alpn_protocol'] == 'http/1.1'
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        finally:
            await server.close()

    asyncio.run(scenario())


def test_http2_tls_posture_negotiates_h2_and_response_body() -> None:
    async def scenario() -> None:
        seen: dict[str, object] = {}

        async def app(scope, receive, send):
            seen['scope'] = scope
            event = await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': event['body'], 'more_body': False})

        server, port = await _start_tls_server(app, http_versions=['2'])
        try:
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                port,
                ssl=_client_context(alpn=['h2']),
                server_hostname='localhost',
            )
            writer.write(H2_PREFACE)
            writer.write(serialize_settings({}))
            request_headers = encode_header_block([
                (b':method', b'POST'),
                (b':path', b'/h2-tls'),
                (b':scheme', b'https'),
                (b':authority', b'localhost'),
                (b'content-length', b'5'),
            ])
            frame_writer = FrameWriter()
            writer.write(frame_writer.headers(1, request_headers, end_stream=False))
            writer.write(frame_writer.data(1, b'hello', end_stream=True))
            await writer.drain()

            buf = FrameBuffer()
            response_headers: list[tuple[bytes, bytes]] = []
            body = bytearray()
            ended = False
            while not ended:
                data = await reader.read(65535)
                assert data
                buf.feed(data)
                for frame in buf.pop_all():
                    if frame.frame_type == FRAME_SETTINGS and frame.payload:
                        _ = decode_settings(frame.payload)
                    elif frame.frame_type == FRAME_HEADERS:
                        response_headers.extend(decode_header_block(frame.payload))
                        if frame.flags & 0x1:
                            ended = True
                    elif frame.frame_type == FRAME_DATA:
                        body.extend(frame.payload)
                        writer.write(serialize_frame(8, 0, 0, len(frame.payload).to_bytes(4, 'big')))
                        writer.write(serialize_frame(8, 0, frame.stream_id, len(frame.payload).to_bytes(4, 'big')))
                        await writer.drain()
                        if frame.flags & 0x1:
                            ended = True
            assert (b':status', b'200') in response_headers
            assert bytes(body) == b'hello'
            tls_ext = seen['scope']['extensions']['tls']
            assert tls_ext['selected_alpn_protocol'] == 'h2'
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        finally:
            await server.close()

    asyncio.run(scenario())
