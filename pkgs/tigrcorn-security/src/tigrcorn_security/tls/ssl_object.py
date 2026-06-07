from __future__ import annotations

from .imports import *
from .models import *

class PackageOwnedSSLObject:
    def __init__(
        self,
        *,
        selected_alpn_protocol: str | None,
        cipher_suite: int,
        peer_certificate: x509.Certificate | None,
    ) -> None:
        self._selected_alpn_protocol = selected_alpn_protocol
        self._cipher_suite = cipher_suite
        self._peer_certificate = peer_certificate
        self._peer_certificate_der = (
            peer_certificate.public_bytes(serialization.Encoding.DER)
            if peer_certificate is not None
            else None
        )

    def selected_alpn_protocol(self) -> str | None:
        return self._selected_alpn_protocol

    def version(self) -> str:
        return 'TLSv1.3'

    def cipher(self) -> tuple[str, str, int]:
        name, bits = _CIPHER_NAMES.get(self._cipher_suite, ('TLS_UNKNOWN', 0))
        return name, 'TLSv1.3', bits

    def getpeercert(self, binary_form: bool = False) -> dict[str, Any] | bytes | None:
        if self._peer_certificate is None:
            return None
        if binary_form:
            return self._peer_certificate_der
        return describe_peer_certificate(self._peer_certificate)

__all__ = [name for name in globals() if not name.startswith('__')]
