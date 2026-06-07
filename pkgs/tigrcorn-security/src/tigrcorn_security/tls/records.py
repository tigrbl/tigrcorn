from __future__ import annotations

from .imports import *
from .models import *

def _build_record_state(secret: bytes, *, key_length: int, iv_length: int, hash_name: str) -> _RecordProtectionState:
    schedule = Tls13KeySchedule(hash_name=hash_name)
    return _RecordProtectionState(
        key=schedule.expand_label(secret, 'key', b'', key_length),
        iv=schedule.expand_label(secret, 'iv', b'', iv_length),
    )


def _encode_plain_record(content_type: int, payload: bytes) -> bytes:
    return bytes([content_type]) + _TLS_LEGACY_RECORD_VERSION.to_bytes(2, 'big') + len(payload).to_bytes(2, 'big') + payload


def _encrypt_record(payload: bytes, inner_content_type: int, state: _RecordProtectionState) -> bytes:
    inner = payload + bytes([inner_content_type])
    nonce = state.next_nonce()
    body_length = len(inner) + 16
    header = (
        bytes([_TLS_CONTENT_APPLICATION_DATA])
        + _TLS_LEGACY_RECORD_VERSION.to_bytes(2, 'big')
        + body_length.to_bytes(2, 'big')
    )
    ciphertext, tag = aes_gcm_encrypt(state.key, nonce, inner, aad=header)
    return header + ciphertext + tag


def _decrypt_record(payload: bytes, state: _RecordProtectionState) -> tuple[bytes, int]:
    if len(payload) < 16:
        raise ProtocolError('truncated TLS application-data record')
    header = (
        bytes([_TLS_CONTENT_APPLICATION_DATA])
        + _TLS_LEGACY_RECORD_VERSION.to_bytes(2, 'big')
        + len(payload).to_bytes(2, 'big')
    )
    ciphertext = payload[:-16]
    tag = payload[-16:]
    nonce = state.next_nonce()
    plaintext = aes_gcm_decrypt(state.key, nonce, ciphertext, tag, aad=header)
    index = len(plaintext) - 1
    while index >= 0 and plaintext[index] == 0:
        index -= 1
    if index < 0:
        raise ProtocolError('TLS inner plaintext is missing a content type')
    return plaintext[:index], plaintext[index]

__all__ = [name for name in globals() if not name.startswith('__')]
