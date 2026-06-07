from __future__ import annotations

import hashlib
import hmac
import secrets

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import xor_bytes
from .aes import aes_encrypt_block
from .gcm import aes_gcm_decrypt, aes_gcm_encrypt
from .keys import (
    RETRY_INTEGRITY_KEY,
    RETRY_INTEGRITY_NONCE,
    QuicPacketProtectionKeys,
    derive_quic_packet_protection_keys,
    derive_secret,
    packet_nonce,
)

def aes_header_protection_mask(hp_key: bytes, sample: bytes) -> bytes:
    if len(sample) != 16:
        raise ValueError('QUIC header protection sample must be 16 bytes')
    return aes_encrypt_block(hp_key, sample)[:5]



def encode_packet_number(packet_number: int, length: int | None = None) -> bytes:
    if packet_number < 0:
        raise ValueError('packet number must be non-negative')
    if length is None:
        if packet_number <= 0xFF:
            length = 1
        elif packet_number <= 0xFFFF:
            length = 2
        elif packet_number <= 0xFFFFFF:
            length = 3
        else:
            length = 4
    if length < 1 or length > 4:
        raise ValueError('packet number length must be in [1, 4]')
    mask = (1 << (length * 8)) - 1
    return (packet_number & mask).to_bytes(length, 'big')



def reconstruct_packet_number(truncated_pn: int, pn_nbits: int, largest_pn: int) -> int:
    if largest_pn < 0:
        return truncated_pn
    expected_pn = largest_pn + 1
    pn_window = 1 << pn_nbits
    pn_half_window = pn_window // 2
    pn_mask = pn_window - 1
    candidate = (expected_pn & ~pn_mask) | truncated_pn
    if candidate + pn_half_window <= expected_pn and candidate < (1 << 62) - pn_window:
        return candidate + pn_window
    if candidate > expected_pn + pn_half_window and candidate >= pn_window:
        return candidate - pn_window
    return candidate



def apply_header_protection(packet: bytes, *, pn_offset: int, hp_key: bytes) -> bytes:
    protected = bytearray(packet)
    first_byte = protected[0]
    pn_length = (first_byte & 0x03) + 1
    sample_offset = pn_offset + 4
    if sample_offset + 16 > len(packet):
        raise ProtocolError('QUIC packet too short for header protection sample')
    sample = bytes(protected[sample_offset:sample_offset + 16])
    mask = aes_header_protection_mask(hp_key, sample)
    protected[0] ^= mask[0] & (0x0F if first_byte & 0x80 else 0x1F)
    for index in range(pn_length):
        protected[pn_offset + index] ^= mask[index + 1]
    return bytes(protected)



def remove_header_protection(packet: bytes, *, pn_offset: int, hp_key: bytes) -> tuple[bytes, int]:
    if pn_offset + 4 + 16 > len(packet):
        raise ProtocolError('QUIC packet too short for header protection sample')
    unprotected = bytearray(packet)
    first_byte = unprotected[0]
    sample = bytes(unprotected[pn_offset + 4:pn_offset + 20])
    mask = aes_header_protection_mask(hp_key, sample)
    unprotected[0] ^= mask[0] & (0x0F if first_byte & 0x80 else 0x1F)
    pn_length = (unprotected[0] & 0x03) + 1
    for index in range(pn_length):
        unprotected[pn_offset + index] ^= mask[index + 1]
    return bytes(unprotected), pn_length



def protect_quic_packet(
    header: bytes,
    plaintext: bytes,
    *,
    packet_number: int,
    pn_offset: int,
    keys: QuicPacketProtectionKeys,
) -> bytes:
    nonce = packet_nonce(keys.iv, packet_number)
    ciphertext, tag = aes_gcm_encrypt(keys.key, nonce, plaintext, aad=header)
    return apply_header_protection(header + ciphertext + tag, pn_offset=pn_offset, hp_key=keys.hp)



def unprotect_quic_packet(
    packet: bytes,
    *,
    pn_offset: int,
    keys: QuicPacketProtectionKeys,
    largest_pn: int = -1,
) -> tuple[bytes, int, bytes]:
    unprotected, pn_length = remove_header_protection(packet, pn_offset=pn_offset, hp_key=keys.hp)
    if len(unprotected) < pn_offset + pn_length + 16:
        raise ProtocolError('truncated QUIC protected payload')
    truncated_pn = int.from_bytes(unprotected[pn_offset:pn_offset + pn_length], 'big')
    packet_number = reconstruct_packet_number(truncated_pn, pn_length * 8, largest_pn)
    header = unprotected[:pn_offset + pn_length]
    ciphertext_and_tag = unprotected[pn_offset + pn_length:]
    ciphertext = ciphertext_and_tag[:-16]
    tag = ciphertext_and_tag[-16:]
    nonce = packet_nonce(keys.iv, packet_number)
    plaintext = aes_gcm_decrypt(keys.key, nonce, ciphertext, tag, aad=header)
    return header, packet_number, plaintext



def build_retry_pseudo_packet(retry_packet_without_tag: bytes, original_destination_connection_id: bytes) -> bytes:
    if len(original_destination_connection_id) > 255:
        raise ValueError('original destination connection id too long')
    return bytes([len(original_destination_connection_id)]) + original_destination_connection_id + retry_packet_without_tag



def compute_retry_integrity_tag(retry_packet_without_tag: bytes, original_destination_connection_id: bytes) -> bytes:
    pseudo_packet = build_retry_pseudo_packet(retry_packet_without_tag, original_destination_connection_id)
    _ciphertext, tag = aes_gcm_encrypt(RETRY_INTEGRITY_KEY, RETRY_INTEGRITY_NONCE, b'', aad=pseudo_packet)
    return tag



def verify_retry_integrity_tag(retry_packet_without_tag: bytes, original_destination_connection_id: bytes, tag: bytes) -> bool:
    return hmac.compare_digest(compute_retry_integrity_tag(retry_packet_without_tag, original_destination_connection_id), tag)


# --- Compatibility wrappers used by the simplified transport -----------------------

def generate_connection_id(length: int = 8) -> bytes:
    if length <= 0:
        raise ValueError('connection id length must be positive')
    return secrets.token_bytes(length)



def _compat_keys(secret: bytes) -> QuicPacketProtectionKeys:
    traffic_secret = derive_secret(secret, b'compat secret', length=32)
    return derive_quic_packet_protection_keys(traffic_secret)



def protect_payload(key: bytes, packet_number: int, payload: bytes) -> bytes:
    keys = _compat_keys(key)
    ciphertext, tag = aes_gcm_encrypt(keys.key, packet_nonce(keys.iv, packet_number), payload)
    return ciphertext + tag



def unprotect_payload(key: bytes, packet_number: int, payload: bytes) -> bytes:
    if len(payload) < 16:
        raise ProtocolError('truncated protected payload')
    keys = _compat_keys(key)
    ciphertext = payload[:-16]
    tag = payload[-16:]
    return aes_gcm_decrypt(keys.key, packet_nonce(keys.iv, packet_number), ciphertext, tag)



def make_integrity_tag(key: bytes, header: bytes, payload: bytes, *, size: int = 16) -> bytes:
    return hmac.new(key, header + payload, hashlib.sha256).digest()[:size]



def verify_integrity_tag(key: bytes, header: bytes, payload: bytes, tag: bytes) -> bool:
    return hmac.compare_digest(make_integrity_tag(key, header, payload, size=len(tag)), tag)
