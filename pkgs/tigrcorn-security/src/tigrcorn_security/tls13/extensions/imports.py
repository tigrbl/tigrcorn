from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable, Sequence

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint

TLS_VERSION_1_3 = 0x0304
TLS_LEGACY_VERSION = 0x0303

CIPHER_TLS_AES_128_GCM_SHA256 = 0x1301
CIPHER_TLS_AES_256_GCM_SHA384 = 0x1302

GROUP_SECP256R1 = 0x0017
GROUP_X25519 = 0x001D

SIG_RSA_PKCS1_SHA256 = 0x0401
SIG_ECDSA_SECP256R1_SHA256 = 0x0403
SIG_RSA_PSS_RSAE_SHA256 = 0x0804
SIG_ED25519 = 0x0807
SIG_RSA_PSS_PSS_SHA256 = 0x0809

PSK_MODE_KE = 0
PSK_MODE_DHE_KE = 1

QUIC_EARLY_DATA_SENTINEL = 0xFFFFFFFF


__all__ = [name for name in globals() if not name.startswith('__')]
