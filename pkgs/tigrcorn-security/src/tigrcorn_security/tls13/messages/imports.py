from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar, Sequence

from tigrcorn_core.errors import ProtocolError
from tigrcorn_security.tls13.extensions import (
    ExtensionType,
    TlsExtension,
    TLS_LEGACY_VERSION,
    encode_extensions,
    decode_extensions,
)

HELLO_RETRY_REQUEST_RANDOM = bytes.fromhex(
    'CF21AD74E59A6111BE1D8C021E65B891'
    'C2A211167ABB8C5E079E09E2C8A8339C'
)


__all__ = [name for name in globals() if not name.startswith('__')]
