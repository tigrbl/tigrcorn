from __future__ import annotations

from .imports import *

def generate_self_signed_certificate(common_name: str = 'tigrcorn-quic', *, purpose: str = 'server') -> tuple[bytes, bytes]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    if purpose not in {'server', 'client', 'both'}:
        raise ValueError("purpose must be 'server', 'client', or 'both'")
    eku_oids: list[x509.ObjectIdentifier] = []
    if purpose in {'server', 'both'}:
        eku_oids.append(ExtendedKeyUsageOID.SERVER_AUTH)
    if purpose in {'client', 'both'}:
        eku_oids.append(ExtendedKeyUsageOID.CLIENT_AUTH)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(private_key.public_key()), critical=False)
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
        .add_extension(x509.ExtendedKeyUsage(eku_oids), critical=False)
    )
    certificate = builder.sign(private_key, algorithm=None)
    return (
        certificate.public_bytes(serialization.Encoding.PEM),
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )

__all__ = [name for name in globals() if not name.startswith('__')]
