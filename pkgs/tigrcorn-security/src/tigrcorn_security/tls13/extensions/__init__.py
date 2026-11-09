from __future__ import annotations

from .imports import *
from .models import *
from .cipher_suites import *
from .vectors import *
from .common import *
from .key_share import *
from .psk import *
from .quic import *
from .registry import *

SUPPORTED_CIPHER_SUITES = (CIPHER_TLS_AES_256_GCM_SHA384, CIPHER_TLS_AES_128_GCM_SHA256)
SUPPORTED_GROUPS = (GROUP_X25519, GROUP_SECP256R1)
SUPPORTED_SIGNATURE_SCHEMES = (SIG_ED25519, SIG_ECDSA_SECP256R1_SHA256, SIG_ECDSA_SECP384R1_SHA384, SIG_RSA_PSS_RSAE_SHA256, SIG_RSA_PSS_PSS_SHA256)
SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES = SUPPORTED_SIGNATURE_SCHEMES

__all__ = [name for name in globals() if not name.startswith('__')]
