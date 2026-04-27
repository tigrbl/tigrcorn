from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def write_server_material(out_dir: Path, server_name: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cert_path = out_dir / "server-cert.pem"
    key_path = out_dir / "server-key.pem"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
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
    return cert_path, key_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/certs")
    parser.add_argument("--server-name", default="localhost")
    args = parser.parse_args()
    cert_path, key_path = write_server_material(Path(args.out), args.server_name)
    print(f"certfile={cert_path} keyfile={key_path}")


if __name__ == "__main__":
    main()
