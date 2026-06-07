from __future__ import annotations

import hmac
from typing import Iterable

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import xor_bytes
from .aes import aes_encrypt_block

_GHASH_R = 0xE1000000000000000000000000000000



def _galois_mul128(left: int, right: int) -> int:
    z = 0
    v = right
    for bit_index in range(128):
        if (left >> (127 - bit_index)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ _GHASH_R
        else:
            v >>= 1
    return z



def _iter_blocks(data: bytes, block_size: int = 16) -> Iterable[bytes]:
    for index in range(0, len(data), block_size):
        yield data[index:index + block_size]



def _pad16(data: bytes) -> bytes:
    if len(data) % 16 == 0:
        return data
    return data + (b'\x00' * (16 - (len(data) % 16)))



def _ghash(hash_subkey: bytes, aad: bytes, ciphertext: bytes) -> bytes:
    h = int.from_bytes(hash_subkey, 'big')
    y = 0
    blocks = _pad16(aad) + _pad16(ciphertext) + (len(aad) * 8).to_bytes(8, 'big') + (len(ciphertext) * 8).to_bytes(8, 'big')
    for block in _iter_blocks(blocks):
        y = _galois_mul128(y ^ int.from_bytes(block, 'big'), h)
    return y.to_bytes(16, 'big')



def _inc32(counter_block: bytes) -> bytes:
    if len(counter_block) != 16:
        raise ValueError('counter block must be 16 bytes')
    counter = (int.from_bytes(counter_block[-4:], 'big') + 1) & 0xFFFFFFFF
    return counter_block[:-4] + counter.to_bytes(4, 'big')



def _gctr(key: bytes, initial_counter_block: bytes, data: bytes) -> bytes:
    if not data:
        return b''
    out = bytearray()
    counter = initial_counter_block
    for block in _iter_blocks(data):
        counter = _inc32(counter)
        keystream = aes_encrypt_block(key, counter)
        out.extend(bytes(byte ^ mask for byte, mask in zip(block, keystream)))
    return bytes(out)



def aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b'') -> tuple[bytes, bytes]:
    if len(nonce) != 12:
        raise ValueError('AES-GCM nonce must be 12 bytes')
    hash_subkey = aes_encrypt_block(key, b'\x00' * 16)
    j0 = nonce + b'\x00\x00\x00\x01'
    ciphertext = _gctr(key, j0, plaintext)
    s = _ghash(hash_subkey, aad, ciphertext)
    tag = xor_bytes(aes_encrypt_block(key, j0), s)
    return ciphertext, tag



def aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes, aad: bytes = b'') -> bytes:
    if len(nonce) != 12:
        raise ValueError('AES-GCM nonce must be 12 bytes')
    if len(tag) != 16:
        raise ValueError('AES-GCM tag must be 16 bytes')
    hash_subkey = aes_encrypt_block(key, b'\x00' * 16)
    j0 = nonce + b'\x00\x00\x00\x01'
    s = _ghash(hash_subkey, aad, ciphertext)
    expected_tag = xor_bytes(aes_encrypt_block(key, j0), s)
    if not hmac.compare_digest(expected_tag, tag):
        raise ProtocolError('QUIC packet authentication failed')
    return _gctr(key, j0, ciphertext)


# --- QUIC packet protection helpers -----------------------------------------------


