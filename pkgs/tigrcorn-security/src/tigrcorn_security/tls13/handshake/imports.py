from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

class _MissingDependencyProxy:
    def __init__(self, package: str) -> None:
        self._package = package

    def __getattr__(self, name: str):
        raise ModuleNotFoundError(
            f"{self._package} is required for this TLS 1.3 certificate operation; install tigrcorn[tls-x509]"
        )


try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa, x25519, padding as asym_padding
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light environments
    x509 = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    hashes = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    serialization = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ec = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ed25519 = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    rsa = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    x25519 = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    asym_padding = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ExtendedKeyUsageOID = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    NameOID = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]

from tigrcorn_core.errors import ProtocolError
from tigrcorn_security.x509.path import (
    CertificatePurpose,
    CertificateValidationPolicy,
    load_pem_certificates,
    verify_certificate_chain,
)
from tigrcorn_security.tls13.extensions import (
    CIPHER_TLS_AES_128_GCM_SHA256,
    CIPHER_TLS_AES_256_GCM_SHA384,
    GROUP_SECP256R1,
    GROUP_X25519,
    PSK_MODE_DHE_KE,
    QUIC_EARLY_DATA_SENTINEL,
    SIG_ECDSA_SECP256R1_SHA256,
    SIG_ECDSA_SECP384R1_SHA384,
    SIG_ED25519,
    SIG_RSA_PSS_PSS_SHA256,
    SIG_RSA_PSS_RSAE_SHA256,
    SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES,
    SUPPORTED_CIPHER_SUITES,
    SUPPORTED_GROUPS,
    SUPPORTED_SIGNATURE_SCHEMES,
    CipherSuiteParameters,
    ExtensionType,
    OfferedPsks,
    PskIdentity,
    TlsExtension,
    TransportParameters,
    cipher_suite_parameters,
    extension_dict,
    encode_pre_shared_key_client_without_binders,
)
from tigrcorn_security.tls13.key_schedule import Tls13KeySchedule
from tigrcorn_security.tls13.messages import (
    HELLO_RETRY_REQUEST_RANDOM,
    Certificate,
    CertificateEntry,
    CertificateRequest,
    CertificateVerify,
    ClientHello,
    EncryptedExtensions,
    Finished,
    HandshakeMessage,
    KeyUpdate,
    NeedMoreData,
    NewSessionTicket,
    ServerHello,
    decode_handshake_message,
)
from tigrcorn_security.tls13.transcript import HandshakeTranscript
from tigrcorn_transports.quic.tls_adapter import split_handshake_flights

_SERVER_CERT_VERIFY_CONTEXT = b'TLS 1.3, server CertificateVerify'
_CLIENT_CERT_VERIFY_CONTEXT = b'TLS 1.3, client CertificateVerify'
_QUIC_TLS_ALERT_BASE = 0x0100
_QUIC_TRANSPORT_ERROR_PROTOCOL_VIOLATION = 0x0A
_MAX_TICKET_LIFETIME_SECONDS = 7 * 24 * 60 * 60
_MAX_AGE_SKEW_MS = 10_000


__all__ = [name for name in globals() if not name.startswith('__')]
