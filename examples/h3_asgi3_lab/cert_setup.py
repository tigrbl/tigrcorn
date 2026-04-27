from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _write_server_material(out_dir: Path, server_name: str) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cert_path = out_dir / "server-cert.pem"
    key_path = out_dir / "server-key.pem"
    regenerate = True
    if cert_path.exists() and key_path.exists():
        try:
            existing = x509.load_pem_x509_certificate(cert_path.read_bytes())
            regenerate = not isinstance(existing.public_key(), ec.EllipticCurvePublicKey)
        except Exception:
            regenerate = True
    if regenerate:
        private_key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.now(timezone.utc)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, server_name)])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=7))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(server_name)]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
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
            .sign(private_key, hashes.SHA256())
        )
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    return {"certfile": str(cert_path), "keyfile": str(key_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/certs")
    parser.add_argument("--server-name", default="localhost")
    args = parser.parse_args()
    print(json.dumps(_write_server_material(Path(args.out), args.server_name), sort_keys=True))


if __name__ == "__main__":
    main()

