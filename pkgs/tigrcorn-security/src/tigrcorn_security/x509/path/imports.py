from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from ipaddress import ip_address
from pathlib import Path
import re
from threading import RLock
from typing import Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

class _MissingDependencyProxy:
    def __init__(self, package: str) -> None:
        self._package = package

    def __getattr__(self, name: str):
        raise ModuleNotFoundError(
            f"{self._package} is required for this X.509 validation operation; install tigrcorn[tls-x509]"
        )


try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, ed448, padding as asym_padding, rsa
    from cryptography.x509 import ocsp
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light environments
    x509 = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    hashes = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    serialization = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ec = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ed25519 = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ed448 = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    asym_padding = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    rsa = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ocsp = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]

try:
    from cryptography.x509 import verification  # type: ignore[attr-defined]
    _HAS_X509_VERIFICATION = True
except ImportError:  # pragma: no cover - compatibility path for older cryptography releases
    verification = None  # type: ignore[assignment]
    _HAS_X509_VERIFICATION = False
try:
    from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID, ExtendedKeyUsageOID
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light environments
    AuthorityInformationAccessOID = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ExtensionOID = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]
    ExtendedKeyUsageOID = _MissingDependencyProxy("cryptography")  # type: ignore[assignment]

from tigrcorn_core.errors import ProtocolError


__all__ = [name for name in globals() if not name.startswith('__')]
