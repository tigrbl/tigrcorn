from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    """Encrypt one AES block using the platform's native crypto backend."""
    if len(key) not in {16, 24, 32}:
        raise ValueError("AES key must be 16, 24, or 32 bytes long")
    if len(block) != 16:
        raise ValueError("AES block must be exactly 16 bytes")
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(block) + encryptor.finalize()
