from __future__ import annotations

import threading
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import ocsp
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtendedKeyUsageOID, NameOID

from tigrcorn.errors import ProtocolError
from tigrcorn.security.tls import (
    CertificateValidationPolicy,
    RevocationFetchPolicy,
    RevocationMaterial,
    RevocationMode,
    verify_certificate_chain,
)
from tigrcorn.transports.quic.handshake import generate_self_signed_certificate


_NOW = datetime.now(timezone.utc)


@dataclass(slots=True)
class _ResponseSpec:
    body: bytes
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)


class _RevocationRequestHandler(BaseHTTPRequestHandler):
    server_version = 'tigrcorn-test-revocation'
    sys_version = ''

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return

    def _dispatch(self) -> None:
        length = int(self.headers.get('Content-Length', '0') or '0')
        body = self.rfile.read(length) if length else b''
        self.server.request_counts[(self.command, self.path)] += 1
        self.server.requests.append((self.command, self.path, body, dict(self.headers.items())))
        spec = self.server.responses.get((self.command, self.path))
        if spec is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'not found')
            return
        self.send_response(spec.status)
        for key, value in spec.headers.items():
            self.send_header(key, value)
        self.send_header('Content-Length', str(len(spec.body)))
        self.end_headers()
        self.wfile.write(spec.body)


class _RevocationHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, responses: dict[tuple[str, str], _ResponseSpec]) -> None:
        super().__init__(('127.0.0.1', 0), _RevocationRequestHandler)
        self.responses = responses
        self.request_counts: Counter[tuple[str, str]] = Counter()
        self.requests: list[tuple[str, str, bytes, dict[str, str]]] = []

    def url(self, path: str) -> str:
        return f'http://127.0.0.1:{self.server_port}{path}'

    def count(self, method: str, path: str) -> int:
        return self.request_counts[(method, path)]


@contextmanager

def revocation_http_server(responses: dict[tuple[str, str], _ResponseSpec]):
    server = _RevocationHTTPServer(responses)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class CertificateFactory:
    def __init__(self) -> None:
        self._now = _NOW

    def make_ca(
        self,
        common_name: str,
        *,
        issuer_cert: x509.Certificate | None = None,
        issuer_key=None,
        path_length: int | None = 1,
        name_constraints: x509.NameConstraints | None = None,
    ) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
        issuer = issuer_cert.subject if issuer_cert is not None else subject
        signer = issuer_key or key
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(self._now - timedelta(days=1))
            .not_valid_after(self._now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=path_length), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key((issuer_key or key).public_key()),
                critical=False,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
        )
        if name_constraints is not None:
            builder = builder.add_extension(name_constraints, critical=True)
        return builder.sign(signer, hashes.SHA256()), key

    def make_server_leaf(
        self,
        common_name: str,
        *,
        issuer_cert: x509.Certificate,
        issuer_key,
        san_dns: tuple[str, ...] = (),
        san_ips: tuple[str, ...] = (),
        ocsp_uris: tuple[str, ...] = (),
        crl_uris: tuple[str, ...] = (),
    ) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
            .issuer_name(issuer_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(self._now - timedelta(days=1))
            .not_valid_after(self._now + timedelta(days=90))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), critical=False)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
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
        )
        general_names: list[x509.GeneralName] = [x509.DNSName(name) for name in san_dns]
        general_names.extend(x509.IPAddress(__import__('ipaddress').ip_address(value)) for value in san_ips)
        if general_names:
            builder = builder.add_extension(x509.SubjectAlternativeName(general_names), critical=False)
        if ocsp_uris:
            builder = builder.add_extension(
                x509.AuthorityInformationAccess(
                    [
                        x509.AccessDescription(
                            AuthorityInformationAccessOID.OCSP,
                            x509.UniformResourceIdentifier(uri),
                        )
                        for uri in ocsp_uris
                    ]
                ),
                critical=False,
            )
        if crl_uris:
            builder = builder.add_extension(
                x509.CRLDistributionPoints(
                    [
                        x509.DistributionPoint(
                            full_name=[x509.UniformResourceIdentifier(uri)],
                            relative_name=None,
                            reasons=None,
                            crl_issuer=None,
                        )
                        for uri in crl_uris
                    ]
                ),
                critical=False,
            )
        return builder.sign(issuer_key, hashes.SHA256()), key

    def make_crl(
        self,
        issuer_cert: x509.Certificate,
        issuer_key,
        *,
        revoked_serials: tuple[int, ...],
        next_update: datetime | None = None,
    ) -> x509.CertificateRevocationList:
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(issuer_cert.subject)
            .last_update(self._now - timedelta(minutes=5))
            .next_update(next_update or (self._now + timedelta(days=1)))
        )
        for serial in revoked_serials:
            revoked = (
                x509.RevokedCertificateBuilder()
                .serial_number(serial)
                .revocation_date(self._now - timedelta(minutes=1))
                .build()
            )
            builder = builder.add_revoked_certificate(revoked)
        return builder.sign(private_key=issuer_key, algorithm=hashes.SHA256())

    def make_ocsp_response(
        self,
        certificate: x509.Certificate,
        issuer_cert: x509.Certificate,
        issuer_key,
        *,
        cert_status: ocsp.OCSPCertStatus = ocsp.OCSPCertStatus.GOOD,
        next_update: datetime | None = None,
        this_update: datetime | None = None,
    ) -> ocsp.OCSPResponse:
        status_kwargs = {
            'revocation_time': None,
            'revocation_reason': None,
        }
        if cert_status is ocsp.OCSPCertStatus.REVOKED:
            status_kwargs['revocation_time'] = self._now - timedelta(minutes=1)
            status_kwargs['revocation_reason'] = x509.ReasonFlags.key_compromise
        builder = (
            ocsp.OCSPResponseBuilder()
            .add_response(
                cert=certificate,
                issuer=issuer_cert,
                algorithm=hashes.SHA1(),
                cert_status=cert_status,
                this_update=this_update or (self._now - timedelta(minutes=1)),
                next_update=next_update,
                **status_kwargs,
            )
            .responder_id(ocsp.OCSPResponderEncoding.HASH, issuer_cert)
        )
        return builder.sign(issuer_key, hashes.SHA256())



def _pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)



def _der_ocsp(response: ocsp.OCSPResponse) -> bytes:
    return response.public_bytes(serialization.Encoding.DER)



def _der_crl(crl: x509.CertificateRevocationList) -> bytes:
    return crl.public_bytes(serialization.Encoding.DER)


