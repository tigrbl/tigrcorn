from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import xor_bytes

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

