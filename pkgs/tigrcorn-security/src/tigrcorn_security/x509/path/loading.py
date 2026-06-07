from __future__ import annotations

from .imports import *

def _looks_like_pem(data: bytes) -> bool:
    return data.lstrip().startswith(b'-----BEGIN ')


def _split_pem_certificates(data: bytes) -> tuple[bytes, ...]:
    if not _looks_like_pem(data):
        return (data,)
    matches = tuple(
        match.strip() + b'\n'
        for match in re.findall(rb'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', data, flags=re.DOTALL)
    )
    return matches or (data,)


def _load_certificate(data: bytes) -> x509.Certificate:
    if _looks_like_pem(data):
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


def load_pem_certificates(pems: Iterable[bytes]) -> list[x509.Certificate]:
    certificates: list[x509.Certificate] = []
    for pem in pems:
        for certificate_blob in _split_pem_certificates(pem):
            certificates.append(_load_certificate(certificate_blob))
    return certificates


def _load_crl(data: x509.CertificateRevocationList | bytes) -> x509.CertificateRevocationList:
    if isinstance(data, x509.CertificateRevocationList):
        return data
    if _looks_like_pem(data):
        return x509.load_pem_x509_crl(data)
    return x509.load_der_x509_crl(data)


def _split_pem_crls(data: bytes) -> tuple[bytes, ...]:
    matches = tuple(
        match.strip() + b'\n'
        for match in re.findall(
            rb'-----BEGIN (?:X509 )?CRL-----.*?-----END (?:X509 )?CRL-----',
            data,
            flags=re.DOTALL,
        )
    )
    return matches or (data,)


def load_crls_from_file(path: str | Path) -> tuple[x509.CertificateRevocationList, ...]:
    data = Path(path).read_bytes()
    if _looks_like_pem(data):
        return tuple(_load_crl(blob) for blob in _split_pem_crls(data))
    return (_load_crl(data),)


def _load_ocsp_response(data: ocsp.OCSPResponse | bytes) -> ocsp.OCSPResponse:
    if isinstance(data, ocsp.OCSPResponse):
        return data
    return ocsp.load_der_ocsp_response(data)

__all__ = [name for name in globals() if not name.startswith('__')]
