from __future__ import annotations

from .imports import *

class CertificatePurpose(str, Enum):
    SERVER_AUTH = 'server'
    CLIENT_AUTH = 'client'


class RevocationMode(str, Enum):
    OFF = 'off'
    SOFT_FAIL = 'soft-fail'
    REQUIRE = 'require'


@dataclass(frozen=True, slots=True)
class RevocationMaterial:
    crls: tuple[x509.CertificateRevocationList | bytes, ...] = ()
    ocsp_responses: tuple[ocsp.OCSPResponse | bytes, ...] = ()


@dataclass(frozen=True, slots=True)
class RevocationFreshnessPolicy:
    allowed_clock_skew: timedelta = timedelta(minutes=5)
    ocsp_max_age_without_next_update: timedelta = timedelta(hours=12)
    ocsp_max_validity_window: timedelta | None = timedelta(days=7)
    crl_max_validity_window: timedelta | None = timedelta(days=14)


@dataclass(frozen=True, slots=True)
class RevocationCacheEntry:
    payload: bytes
    fetched_at: datetime
    expires_at: datetime | None
    content_type: str | None = None


class RevocationCache:
    def __init__(self, *, max_entries: int = 256) -> None:
        if max_entries < 1:
            raise ValueError('revocation cache max_entries must be at least 1')
        self._max_entries = max_entries
        self._entries: OrderedDict[tuple[str, str, str], RevocationCacheEntry] = OrderedDict()
        self._lock = RLock()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def get(self, kind: str, url: str, fingerprint: str, *, moment: datetime) -> RevocationCacheEntry | None:
        key = (kind, url, fingerprint)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and moment > entry.expires_at:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return entry

    def put(self, kind: str, url: str, fingerprint: str, entry: RevocationCacheEntry) -> None:
        key = (kind, url, fingerprint)
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def delete(self, kind: str, url: str, fingerprint: str) -> None:
        key = (kind, url, fingerprint)
        with self._lock:
            self._entries.pop(key, None)

    def purge(self, *, moment: datetime | None = None) -> int:
        now = _as_utc(moment)
        removed = 0
        with self._lock:
            for key, entry in tuple(self._entries.items()):
                if entry.expires_at is not None and now > entry.expires_at:
                    del self._entries[key]
                    removed += 1
        return removed

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


@dataclass(frozen=True, slots=True)
class RevocationFetchPolicy:
    enable_ocsp_aia: bool = True
    enable_crl_distribution_points: bool = True
    timeout_seconds: float = 5.0
    max_response_bytes: int = 2_000_000
    allowed_schemes: tuple[str, ...] = ('http', 'https')
    freshness: RevocationFreshnessPolicy = field(default_factory=RevocationFreshnessPolicy)
    cache: RevocationCache | None = field(default_factory=RevocationCache)
    user_agent: str = 'tigrcorn/0.3.5'


@dataclass(frozen=True, slots=True)
class CertificateValidationPolicy:
    purpose: CertificatePurpose = CertificatePurpose.SERVER_AUTH
    max_chain_depth: int | None = None
    revocation_mode: RevocationMode = RevocationMode.OFF
    revocation_material: RevocationMaterial = RevocationMaterial()
    revocation_fetch_policy: RevocationFetchPolicy | None = field(default_factory=RevocationFetchPolicy)


@dataclass(frozen=True, slots=True)
class VerifiedCertificatePath:
    leaf: x509.Certificate
    chain: tuple[x509.Certificate, ...]
    trust_anchor: x509.Certificate


@dataclass(frozen=True, slots=True)
class _FetchedRevocationPayload:
    payload: bytes
    fetched_at: datetime
    headers: tuple[tuple[str, str], ...]
    content_type: str | None


@dataclass(frozen=True, slots=True)
class _FetchedRevocationMaterial:
    crls: tuple[x509.CertificateRevocationList, ...] = ()
    ocsp_responses: tuple[ocsp.OCSPResponse, ...] = ()
    errors: tuple[str, ...] = ()


class _RevocationFetchError(ProtocolError):
    pass


if _HAS_X509_VERIFICATION:
    _WEBOOKI_CA_POLICY = verification.ExtensionPolicy.webpki_defaults_ca()
    _WEBOOKI_EE_POLICY = verification.ExtensionPolicy.webpki_defaults_ee()
else:  # pragma: no cover - compatibility path for older cryptography releases
    _WEBOOKI_CA_POLICY = None
    _WEBOOKI_EE_POLICY = None

__all__ = [name for name in globals() if not name.startswith('__')]
