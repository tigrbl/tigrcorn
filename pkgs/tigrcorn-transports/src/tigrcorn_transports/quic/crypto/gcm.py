from __future__ import annotations

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tigrcorn_core.errors import ProtocolError


def aes_gcm_encrypt(
    key: bytes,
    nonce: bytes,
    plaintext: bytes,
    aad: bytes = b"",
) -> tuple[bytes, bytes]:
    if len(nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes")
    sealed = AESGCM(key).encrypt(nonce, plaintext, aad)
    return sealed[:-16], sealed[-16:]


def aes_gcm_decrypt(
    key: bytes,
    nonce: bytes,
    ciphertext: bytes,
    tag: bytes,
    aad: bytes = b"",
) -> bytes:
    if len(nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes")
    if len(tag) != 16:
        raise ValueError("AES-GCM tag must be 16 bytes")
    try:
        return AESGCM(key).decrypt(nonce, ciphertext + tag, aad)
    except InvalidTag as exc:
        raise ProtocolError("QUIC packet authentication failed") from exc
