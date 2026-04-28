from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config_from_namespace, build_config_from_sources
from tigrcorn.config.model import ListenerConfig
from tigrcorn.errors import ProtocolError
from tigrcorn.security.policies import build_validation_policy_for_listener
from tigrcorn.security.tls import build_server_ssl_context, verify_certificate_chain
from tigrcorn.security.tls13.handshake import QuicTlsHandshakeDriver
from tigrcorn.security.x509.path import RevocationMode

_NOW = datetime.now(timezone.utc)


def _make_ca(common_name: str) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW - timedelta(days=1))
        .not_valid_after(_NOW + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
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
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _make_leaf(
    common_name: str,
    *,
    issuer_cert: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    eku_oid,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
        .issuer_name(issuer_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW - timedelta(days=1))
        .not_valid_after(_NOW + timedelta(days=90))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
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
        .add_extension(x509.ExtendedKeyUsage([eku_oid]), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), critical=False)
        .sign(issuer_key, hashes.SHA256())
    )
    return cert, key


def _make_crl(
    issuer_cert: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    *,
    revoked_serials: tuple[int, ...],
) -> x509.CertificateRevocationList:
    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(issuer_cert.subject)
        .last_update(_NOW - timedelta(minutes=5))
        .next_update(_NOW + timedelta(days=1))
    )
    for serial in revoked_serials:
        revoked = (
            x509.RevokedCertificateBuilder()
            .serial_number(serial)
            .revocation_date(_NOW - timedelta(minutes=1))
            .build()
        )
        builder = builder.add_revoked_certificate(revoked)
    return builder.sign(private_key=issuer_key, algorithm=hashes.SHA256())


def _pem_certificate(certificate: x509.Certificate) -> bytes:
    return certificate.public_bytes(serialization.Encoding.PEM)


class Phase5TLSOperatorMaterialSurfaceTests(unittest.TestCase):
    def _write_tls_materials(self, root: Path) -> tuple[Path, Path, Path, Path, Path, x509.Certificate]:
        ca_cert, ca_key = _make_ca('phase5-test-ca')
        server_cert, server_key = _make_leaf(
            'server.phase5.local',
            issuer_cert=ca_cert,
            issuer_key=ca_key,
            eku_oid=ExtendedKeyUsageOID.SERVER_AUTH,
        )
        client_cert, _client_key = _make_leaf(
            'client.phase5.local',
            issuer_cert=ca_cert,
            issuer_key=ca_key,
            eku_oid=ExtendedKeyUsageOID.CLIENT_AUTH,
        )
        crl = _make_crl(ca_cert, ca_key, revoked_serials=(client_cert.serial_number,))

        cert_path = root / 'server-cert.pem'
        key_path = root / 'server-key.pem'
        encrypted_key_path = root / 'server-key-encrypted.pem'
        ca_path = root / 'client-ca.pem'
        crl_path = root / 'revocations.pem'

        cert_path.write_bytes(_pem_certificate(server_cert))
        key_path.write_bytes(
            server_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        encrypted_key_path.write_bytes(
            server_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.BestAvailableEncryption(b'hunter2'),
            )
        )
        ca_path.write_bytes(_pem_certificate(ca_cert))
        crl_path.write_bytes(crl.public_bytes(serialization.Encoding.PEM))
        return cert_path, key_path, encrypted_key_path, ca_path, crl_path, client_cert

    def test_cli_and_env_wiring_accept_ssl_keyfile_password_and_ssl_crl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cert_path, key_path, _encrypted_key_path, _ca_path, crl_path, _client_cert = self._write_tls_materials(root)

            parser = build_parser()
            namespace = parser.parse_args(
                [
                    'tests.fixtures_pkg.appmod:app',
                    '--ssl-certfile', str(cert_path),
                    '--ssl-keyfile', str(key_path),
                    '--ssl-keyfile-password', 'cli-secret',
                    '--ssl-crl', str(crl_path),
                    '--ssl-crl-mode', 'soft-fail',
                ]
            )
            config = build_config_from_namespace(namespace)
            self.assertEqual(config.tls.keyfile_password, 'cli-secret')
            self.assertEqual(config.tls.crl, str(crl_path))
            self.assertEqual(config.listeners[0].ssl_keyfile_password, 'cli-secret')
            self.assertEqual(config.listeners[0].ssl_crl, str(crl_path))
            self.assertEqual(config.listeners[0].crl_mode, 'soft-fail')

            env_file = root / '.env'
            env_file.write_text(
                f'TIGRCORN_SSL_KEYFILE_PASSWORD=env-secret\nTIGRCORN_SSL_CRL={crl_path}\n',
                encoding='utf-8',
            )
            env_config = build_config_from_sources(
                config_source={
                    'app': {'target': 'tests.fixtures_pkg.appmod:app'},
                    'tls': {'certfile': str(cert_path), 'keyfile': str(key_path)},
                },
                env_prefix='TIGRCORN',
                env_file=str(env_file),
            )
            self.assertEqual(env_config.tls.keyfile_password, 'env-secret')
            self.assertEqual(env_config.tls.crl, str(crl_path))
            self.assertEqual(env_config.listeners[0].ssl_keyfile_password, 'env-secret')
            self.assertEqual(env_config.listeners[0].ssl_crl, str(crl_path))

    def test_encrypted_private_key_material_loads_through_server_tls_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cert_path, _key_path, encrypted_key_path, _ca_path, _crl_path, _client_cert = self._write_tls_materials(root)
            listener = ListenerConfig(
                kind='tcp',
                host='127.0.0.1',
                port=4433,
                ssl_certfile=str(cert_path),
                ssl_keyfile=str(encrypted_key_path),
                ssl_keyfile_password='hunter2',
            )
            context = build_server_ssl_context(listener)
            self.assertIsNotNone(context)
            assert context is not None
            self.assertEqual(context.private_key_password, b'hunter2')
            driver = QuicTlsHandshakeDriver(
                is_client=False,
                transport_mode='stream',
                certificate_pem=context.certificate_pem,
                private_key_pem=context.private_key_pem,
                private_key_password=context.private_key_password,
                trusted_certificates=context.trusted_certificates,
                validation_policy=context.validation_policy,
            )
            self.assertIsNotNone(driver._private_key)

    def test_local_crl_material_is_loaded_and_revoked_client_cert_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cert_path, key_path, _encrypted_key_path, ca_path, crl_path, client_cert = self._write_tls_materials(root)
            listener = ListenerConfig(
                kind='tcp',
                host='127.0.0.1',
                port=4433,
                ssl_certfile=str(cert_path),
                ssl_keyfile=str(key_path),
                ssl_ca_certs=str(ca_path),
                ssl_require_client_cert=True,
                crl_mode='require',
                ssl_crl=str(crl_path),
            )
            policy = build_validation_policy_for_listener(listener)
            self.assertEqual(policy.revocation_mode, RevocationMode.REQUIRE)
            self.assertEqual(len(policy.revocation_material.crls), 1)
            with self.assertRaisesRegex(ProtocolError, 'revoked'):
                verify_certificate_chain(
                    [_pem_certificate(client_cert)],
                    [ca_path.read_bytes()],
                    policy=policy,
                )


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
