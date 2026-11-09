from __future__ import annotations

from .imports import *

@dataclass(frozen=True, slots=True)
class ServerTLSContext:
    certificate_pem: bytes
    private_key_pem: bytes
    private_key_password: bytes | None
    trusted_certificates: tuple[bytes, ...]
    alpn_protocols: tuple[str, ...]
    require_client_certificate: bool
    validation_policy: CertificateValidationPolicy
    cipher_suites: tuple[int, ...] = (0x1302, 0x1301)
    server_name: str = 'localhost'


@dataclass(slots=True)
class _RecordProtectionState:
    key: bytes
    iv: bytes
    sequence_number: int = 0

    def next_nonce(self) -> bytes:
        sequence = self.sequence_number.to_bytes(8, 'big')
        padded = b'\x00' * (len(self.iv) - len(sequence)) + sequence
        nonce = bytes(left ^ right for left, right in zip(self.iv, padded))
        self.sequence_number += 1
        return nonce

__all__ = [name for name in globals() if not name.startswith('__')]
