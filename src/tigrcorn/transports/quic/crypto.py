from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Iterable

from tigrcorn.errors import ProtocolError
from tigrcorn.utils.bytes import xor_bytes

QUIC_V1_INITIAL_SALT = bytes.fromhex('38762cf7f55934b34d179ae6a4c80cadccbb7f0a')
RETRY_INTEGRITY_KEY = bytes.fromhex('be0c690b9f66575a1d766b54e368c84e')
RETRY_INTEGRITY_NONCE = bytes.fromhex('461599d35d632bf2239825bb')


@dataclass(slots=True)
class QuicPacketProtectionKeys:
    secret: bytes
    key: bytes
    iv: bytes
    hp: bytes


# --- HKDF / QUIC-TLS key schedule -------------------------------------------------

def hkdf_extract(salt: bytes, ikm: bytes, *, hash_name: str = 'sha256') -> bytes:
    return hmac.new(salt, ikm, getattr(hashlib, hash_name)).digest()



def hkdf_expand(prk: bytes, info: bytes, length: int, *, hash_name: str = 'sha256') -> bytes:
    if length < 0:
        raise ValueError('HKDF length must be non-negative')
    hash_len = getattr(hashlib, hash_name)().digest_size
    if length > 255 * hash_len:
        raise ValueError('HKDF length too large')
    output = bytearray()
    block = b''
    counter = 1
    while len(output) < length:
        block = hmac.new(prk, block + info + bytes([counter]), getattr(hashlib, hash_name)).digest()
        output.extend(block)
        counter += 1
    return bytes(output[:length])



def hkdf_expand_label(
    secret: bytes,
    label: bytes | str,
    context: bytes = b'',
    length: int = 32,
    *,
    hash_name: str = 'sha256',
) -> bytes:
    raw_label = label.encode('ascii') if isinstance(label, str) else label
    full_label = b'tls13 ' + raw_label
    if len(full_label) > 255:
        raise ValueError('HKDF label too large')
    if len(context) > 255:
        raise ValueError('HKDF context too large')
    info = length.to_bytes(2, 'big') + bytes([len(full_label)]) + full_label + bytes([len(context)]) + context
    return hkdf_expand(secret, info, length, hash_name=hash_name)



def derive_secret(secret: bytes, label: bytes, *, length: int = 32) -> bytes:
    normalized = hkdf_extract(b'tigrcorn-quic', secret)
    return hkdf_expand_label(normalized, label, b'', length)



def derive_initial_secret(connection_id: bytes, *, salt: bytes = QUIC_V1_INITIAL_SALT) -> bytes:
    return hkdf_extract(salt, connection_id)



def derive_quic_packet_protection_keys(
    secret: bytes,
    *,
    key_length: int = 16,
    iv_length: int = 12,
    hp_length: int = 16,
    hash_name: str = 'sha256',
) -> QuicPacketProtectionKeys:
    return QuicPacketProtectionKeys(
        secret=secret,
        key=hkdf_expand_label(secret, 'quic key', b'', key_length, hash_name=hash_name),
        iv=hkdf_expand_label(secret, 'quic iv', b'', iv_length, hash_name=hash_name),
        hp=hkdf_expand_label(secret, 'quic hp', b'', hp_length, hash_name=hash_name),
    )



def derive_initial_packet_protection_keys(connection_id: bytes) -> tuple[QuicPacketProtectionKeys, QuicPacketProtectionKeys]:
    initial_secret = derive_initial_secret(connection_id)
    client_secret = hkdf_expand_label(initial_secret, 'client in', b'', 32)
    server_secret = hkdf_expand_label(initial_secret, 'server in', b'', 32)
    return (
        derive_quic_packet_protection_keys(client_secret),
        derive_quic_packet_protection_keys(server_secret),
    )



def update_quic_secret(secret: bytes, *, hash_name: str = 'sha256') -> bytes:
    return hkdf_expand_label(secret, 'quic ku', b'', len(secret), hash_name=hash_name)



def packet_nonce(iv: bytes, packet_number: int) -> bytes:
    if packet_number < 0:
        raise ValueError('packet number must be non-negative')
    padded_pn = packet_number.to_bytes(len(iv), 'big')
    return xor_bytes(iv, padded_pn)


# --- AES block cipher --------------------------------------------------------------


def _rotl8(value: int, shift: int) -> int:
    shift &= 7
    return ((value << shift) | (value >> (8 - shift))) & 0xFF



def _gf_mul8(left: int, right: int) -> int:
    product = 0
    a = left & 0xFF
    b = right & 0xFF
    for _ in range(8):
        if b & 1:
            product ^= a
        carry = a & 0x80
        a = (a << 1) & 0xFF
        if carry:
            a ^= 0x1B
        b >>= 1
    return product



def _gf_pow8(value: int, exponent: int) -> int:
    result = 1
    base = value & 0xFF
    exp = exponent
    while exp:
        if exp & 1:
            result = _gf_mul8(result, base)
        base = _gf_mul8(base, base)
        exp >>= 1
    return result



def _gf_inv8(value: int) -> int:
    if value == 0:
        return 0
    return _gf_pow8(value, 254)



def _generate_aes_sbox() -> list[int]:
    table: list[int] = []
    for byte in range(256):
        inv = _gf_inv8(byte)
        transformed = inv ^ _rotl8(inv, 1) ^ _rotl8(inv, 2) ^ _rotl8(inv, 3) ^ _rotl8(inv, 4) ^ 0x63
        table.append(transformed & 0xFF)
    return table


_AES_SBOX = _generate_aes_sbox()



def _sub_word(word: list[int]) -> list[int]:
    return [_AES_SBOX[byte] for byte in word]



def _rot_word(word: list[int]) -> list[int]:
    return [word[1], word[2], word[3], word[0]]



def _expand_aes_key(key: bytes) -> tuple[list[bytes], int]:
    if len(key) not in {16, 24, 32}:
        raise ValueError('AES key must be 16, 24, or 32 bytes long')
    nk = len(key) // 4
    nr_by_nk = {4: 10, 6: 12, 8: 14}
    nr = nr_by_nk[nk]
    words: list[list[int]] = [list(key[index:index + 4]) for index in range(0, len(key), 4)]
    rcon = 1
    while len(words) < 4 * (nr + 1):
        temp = list(words[-1])
        if len(words) % nk == 0:
            temp = _sub_word(_rot_word(temp))
            temp[0] ^= rcon
            rcon = _gf_mul8(rcon, 2)
        elif nk > 6 and len(words) % nk == 4:
            temp = _sub_word(temp)
        word = [left ^ right for left, right in zip(words[-nk], temp)]
        words.append(word)
    round_keys = [bytes(byte for word in words[index:index + 4] for byte in word) for index in range(0, len(words), 4)]
    return round_keys, nr



def _mix_single_column(column: list[int]) -> list[int]:
    a0, a1, a2, a3 = column
    return [
        _gf_mul8(a0, 2) ^ _gf_mul8(a1, 3) ^ a2 ^ a3,
        a0 ^ _gf_mul8(a1, 2) ^ _gf_mul8(a2, 3) ^ a3,
        a0 ^ a1 ^ _gf_mul8(a2, 2) ^ _gf_mul8(a3, 3),
        _gf_mul8(a0, 3) ^ a1 ^ a2 ^ _gf_mul8(a3, 2),
    ]



def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError('AES block must be exactly 16 bytes')
    round_keys, nr = _expand_aes_key(key)
    state = [left ^ right for left, right in zip(block, round_keys[0])]
    for round_index in range(1, nr):
        state = [_AES_SBOX[byte] for byte in state]
        state = [
            state[0], state[5], state[10], state[15],
            state[4], state[9], state[14], state[3],
            state[8], state[13], state[2], state[7],
            state[12], state[1], state[6], state[11],
        ]
        mixed = [0] * 16
        for column_index in range(4):
            start = column_index * 4
            mixed[start:start + 4] = _mix_single_column(state[start:start + 4])
        state = [left ^ right for left, right in zip(mixed, round_keys[round_index])]
    state = [_AES_SBOX[byte] for byte in state]
    state = [
        state[0], state[5], state[10], state[15],
        state[4], state[9], state[14], state[3],
        state[8], state[13], state[2], state[7],
        state[12], state[1], state[6], state[11],
    ]
    state = [left ^ right for left, right in zip(state, round_keys[nr])]
    return bytes(state)


# --- AES-GCM ----------------------------------------------------------------------

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
