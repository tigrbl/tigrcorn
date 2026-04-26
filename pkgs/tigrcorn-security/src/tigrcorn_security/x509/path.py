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

from tigrcorn.errors import ProtocolError


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


def _as_utc(moment: datetime | None) -> datetime:
    now = moment or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)




def _compat_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _certificate_not_valid_before(certificate: x509.Certificate) -> datetime:
    value = getattr(certificate, 'not_valid_before_utc', None)
    if value is None:
        value = certificate.not_valid_before
    return _compat_datetime(value)


def _certificate_not_valid_after(certificate: x509.Certificate) -> datetime:
    value = getattr(certificate, 'not_valid_after_utc', None)
    if value is None:
        value = certificate.not_valid_after
    return _compat_datetime(value)


def _crl_last_update(crl: x509.CertificateRevocationList) -> datetime:
    value = getattr(crl, 'last_update_utc', None)
    if value is None:
        value = crl.last_update
    return _compat_datetime(value)


def _crl_next_update(crl: x509.CertificateRevocationList) -> datetime | None:
    value = getattr(crl, 'next_update_utc', None)
    if value is None:
        value = crl.next_update
    return None if value is None else _compat_datetime(value)


def _ocsp_response_produced_at(response: ocsp.OCSPResponse) -> datetime:
    value = getattr(response, 'produced_at_utc', None)
    if value is None:
        value = response.produced_at
    return _compat_datetime(value)


def _ocsp_single_this_update(single: ocsp.OCSPSingleResponse) -> datetime:
    value = getattr(single, 'this_update_utc', None)
    if value is None:
        value = single.this_update
    return _compat_datetime(value)


def _ocsp_single_next_update(single: ocsp.OCSPSingleResponse) -> datetime | None:
    value = getattr(single, 'next_update_utc', None)
    if value is None:
        value = single.next_update
    return None if value is None else _compat_datetime(value)


def _basic_constraints(certificate: x509.Certificate) -> x509.BasicConstraints:
    try:
        return certificate.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value
    except x509.ExtensionNotFound as exc:
        raise ProtocolError('peer certificate chain verification failed: missing BasicConstraints extension') from exc


def _key_usage(certificate: x509.Certificate) -> x509.KeyUsage | None:
    try:
        return certificate.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
    except x509.ExtensionNotFound:
        return None


def _extended_key_usage(certificate: x509.Certificate) -> x509.ExtendedKeyUsage | None:
    try:
        return certificate.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE).value
    except x509.ExtensionNotFound:
        return None


def _subject_alt_name(certificate: x509.Certificate) -> x509.SubjectAlternativeName | None:
    try:
        return certificate.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound:
        return None


def _name_constraints(certificate: x509.Certificate) -> x509.NameConstraints | None:
    try:
        return certificate.extensions.get_extension_for_oid(ExtensionOID.NAME_CONSTRAINTS).value
    except x509.ExtensionNotFound:
        return None


def _verify_certificate_signature(child: x509.Certificate, issuer: x509.Certificate) -> None:
    if child.issuer != issuer.subject:
        raise ProtocolError('peer certificate chain verification failed: issuer name mismatch')
    try:
        _verify_signature(issuer.public_key(), child.signature, child.tbs_certificate_bytes, child.signature_hash_algorithm)
    except Exception as exc:
        raise ProtocolError('peer certificate chain verification failed: signature verification failed') from exc


def _verify_crl_signature(crl: x509.CertificateRevocationList, issuer: x509.Certificate) -> None:
    verifier = getattr(crl, 'is_signature_valid', None)
    if callable(verifier):
        if not verifier(issuer.public_key()):
            raise ProtocolError('CRL signature verification failed')
        return
    try:
        _verify_signature(issuer.public_key(), crl.signature, crl.tbs_certlist_bytes, crl.signature_hash_algorithm)
    except Exception as exc:
        raise ProtocolError('CRL signature verification failed') from exc


def _dns_within_constraint(name: str, constraint: str) -> bool:
    candidate = _normalized_dns_name(name)
    permitted = _normalized_dns_name(constraint)
    return candidate == permitted or candidate.endswith('.' + permitted)


def _enforce_name_constraints(chain: Sequence[x509.Certificate]) -> None:
    leaf = chain[0]
    leaf_san = _subject_alt_name(leaf)
    leaf_dns = tuple(_normalized_dns_name(name) for name in leaf_san.get_values_for_type(x509.DNSName)) if leaf_san is not None else ()
    leaf_ips = tuple(leaf_san.get_values_for_type(x509.IPAddress)) if leaf_san is not None else ()
    for issuer in chain[1:]:
        constraints = _name_constraints(issuer)
        if constraints is None:
            continue
        permitted = constraints.permitted_subtrees or ()
        excluded = constraints.excluded_subtrees or ()
        for subtree in excluded:
            if isinstance(subtree, x509.DNSName) and any(_dns_within_constraint(name, subtree.value) for name in leaf_dns):
                raise ProtocolError('peer certificate chain verification failed: name constraints violated')
            if isinstance(subtree, x509.IPAddress) and any(ip == subtree.value for ip in leaf_ips):
                raise ProtocolError('peer certificate chain verification failed: name constraints violated')
        if permitted:
            permitted_dns = [subtree.value for subtree in permitted if isinstance(subtree, x509.DNSName)]
            permitted_ips = [subtree.value for subtree in permitted if isinstance(subtree, x509.IPAddress)]
            if leaf_dns and permitted_dns and not all(any(_dns_within_constraint(name, constraint) for constraint in permitted_dns) for name in leaf_dns):
                raise ProtocolError('peer certificate chain verification failed: name constraints violated')
            if leaf_ips and permitted_ips and not all(any(ip == constraint for constraint in permitted_ips) for ip in leaf_ips):
                raise ProtocolError('peer certificate chain verification failed: name constraints violated')
            if (leaf_dns and not permitted_dns) or (leaf_ips and not permitted_ips):
                raise ProtocolError('peer certificate chain verification failed: name constraints violated')


def _manual_verified_chain(
    chain: Sequence[x509.Certificate],
    trust_roots: Sequence[x509.Certificate],
    *,
    server_name: str,
    moment: datetime,
    policy: CertificateValidationPolicy,
) -> tuple[x509.Certificate, ...]:
    if not chain:
        raise ProtocolError('peer certificate chain verification failed: empty certificate chain')

    verified_chain = list(chain)
    for certificate in verified_chain:
        verify_certificate_validity(certificate, moment=moment)

    trust_anchor: x509.Certificate | None = None
    top = verified_chain[-1]
    for root in trust_roots:
        if root.fingerprint(hashes.SHA256()) == top.fingerprint(hashes.SHA256()):
            trust_anchor = root
            verified_chain[-1] = root
            break
        try:
            _verify_certificate_signature(top, root)
        except ProtocolError:
            continue
        trust_anchor = root
        verified_chain.append(root)
        break
    if trust_anchor is None:
        raise ProtocolError('peer certificate chain verification failed: unable to locate a trusted issuer')

    if len(verified_chain) > 1:
        for child, issuer in zip(verified_chain, verified_chain[1:]):
            _verify_certificate_signature(child, issuer)

    if policy.max_chain_depth is not None:
        intermediate_count = max(0, len(verified_chain) - 2)
        if intermediate_count > policy.max_chain_depth:
            raise ProtocolError('peer certificate chain verification failed: maximum chain depth exceeded')

    for index in range(1, len(verified_chain)):
        issuer = verified_chain[index]
        verify_certificate_validity(issuer, moment=moment)
        constraints = _basic_constraints(issuer)
        if not constraints.ca and index != len(verified_chain) - 1:
            raise ProtocolError('peer certificate chain verification failed: issuer is not a CA certificate')
        usage = _key_usage(issuer)
        if usage is not None and not usage.key_cert_sign and index != 0:
            raise ProtocolError('peer certificate chain verification failed: issuer is not permitted to sign certificates')
        if constraints.path_length is not None:
            subordinate_ca_count = sum(1 for candidate in verified_chain[1:index] if _basic_constraints(candidate).ca)
            if subordinate_ca_count > constraints.path_length:
                raise ProtocolError('peer certificate chain verification failed: path length constraint violated')

    leaf = verified_chain[0]
    leaf_constraints = _basic_constraints(leaf)
    if leaf_constraints.ca:
        raise ProtocolError('peer certificate chain verification failed: leaf certificate must not be a CA certificate')
    eku = _extended_key_usage(leaf)
    if eku is not None:
        required = ExtendedKeyUsageOID.CLIENT_AUTH if policy.purpose is CertificatePurpose.CLIENT_AUTH else ExtendedKeyUsageOID.SERVER_AUTH
        if required not in eku:
            raise ProtocolError('peer certificate chain verification failed: leaf certificate does not satisfy the required extended key usage')
    usage = _key_usage(leaf)
    if usage is not None and not usage.digital_signature:
        raise ProtocolError('peer certificate chain verification failed: leaf certificate is not permitted for digital signatures')

    _enforce_name_constraints(verified_chain)

    if policy.purpose is CertificatePurpose.SERVER_AUTH:
        verify_certificate_hostname(leaf, server_name)

    return tuple(verified_chain)

def _looks_like_pem(data: bytes) -> bool:
    return data.lstrip().startswith(b'-----BEGIN ')


def _split_pem_certificates(data: bytes) -> tuple[bytes, ...]:
    if not _looks_like_pem(data):
        return (data,)
    matches = tuple(
        match.strip() + b'\n'
        for match in re.findall(rb'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', data, flags=re.DOTALL)
    )
    return matches or (data,)


def _load_certificate(data: bytes) -> x509.Certificate:
    if _looks_like_pem(data):
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


def load_pem_certificates(pems: Iterable[bytes]) -> list[x509.Certificate]:
    certificates: list[x509.Certificate] = []
    for pem in pems:
        for certificate_blob in _split_pem_certificates(pem):
            certificates.append(_load_certificate(certificate_blob))
    return certificates


def _load_crl(data: x509.CertificateRevocationList | bytes) -> x509.CertificateRevocationList:
    if isinstance(data, x509.CertificateRevocationList):
        return data
    if _looks_like_pem(data):
        return x509.load_pem_x509_crl(data)
    return x509.load_der_x509_crl(data)


def _split_pem_crls(data: bytes) -> tuple[bytes, ...]:
    matches = tuple(
        match.strip() + b'\n'
        for match in re.findall(
            rb'-----BEGIN (?:X509 )?CRL-----.*?-----END (?:X509 )?CRL-----',
            data,
            flags=re.DOTALL,
        )
    )
    return matches or (data,)


def load_crls_from_file(path: str | Path) -> tuple[x509.CertificateRevocationList, ...]:
    data = Path(path).read_bytes()
    if _looks_like_pem(data):
        return tuple(_load_crl(blob) for blob in _split_pem_crls(data))
    return (_load_crl(data),)


def _load_ocsp_response(data: ocsp.OCSPResponse | bytes) -> ocsp.OCSPResponse:
    if isinstance(data, ocsp.OCSPResponse):
        return data
    return ocsp.load_der_ocsp_response(data)


def _normalized_dns_name(value: str) -> str:
    return value.rstrip('.').encode('idna').decode('ascii').lower()


def _certificate_time_bounds(certificate: x509.Certificate) -> tuple[datetime, datetime]:
    return _certificate_not_valid_before(certificate), _certificate_not_valid_after(certificate)


def verify_certificate_validity(certificate: x509.Certificate, *, moment: datetime | None = None) -> None:
    now = _as_utc(moment)
    not_before, not_after = _certificate_time_bounds(certificate)
    if now < not_before or now > not_after:
        raise ProtocolError('peer certificate is not currently valid')


def _dnsname_match(pattern: str, hostname: str) -> bool:
    left = _normalized_dns_name(pattern)
    right = _normalized_dns_name(hostname)
    if left == right:
        return True
    if not left.startswith('*.'):
        return False
    suffix = left[1:]
    if not right.endswith(suffix):
        return False
    prefix = right[: -len(suffix)]
    return prefix.count('.') == 0 and bool(prefix)


def _server_subject(server_name: str):
    if not _HAS_X509_VERIFICATION:
        return server_name
    try:
        return verification.IPAddress(ip_address(server_name))
    except ValueError:
        return verification.DNSName(_normalized_dns_name(server_name))


def _first_subject_alt_name(certificate: x509.Certificate):
    try:
        san = certificate.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound as exc:
        raise ProtocolError('peer certificate does not contain a subjectAltName extension') from exc
    dns_names = san.get_values_for_type(x509.DNSName)
    if dns_names:
        return _normalized_dns_name(dns_names[0]) if not _HAS_X509_VERIFICATION else verification.DNSName(_normalized_dns_name(dns_names[0]))
    ip_names = san.get_values_for_type(x509.IPAddress)
    if ip_names:
        return ip_names[0] if not _HAS_X509_VERIFICATION else verification.IPAddress(ip_names[0])
    raise ProtocolError('peer certificate subjectAltName extension does not contain a DNS or IP subject')


def verify_certificate_hostname(certificate: x509.Certificate, server_name: str) -> None:
    if not server_name:
        return
    try:
        san = certificate.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound as exc:
        raise ProtocolError('peer certificate does not contain a subjectAltName extension') from exc
    try:
        target_ip = ip_address(server_name)
    except ValueError:
        target_ip = None
    if target_ip is not None:
        if any(candidate == target_ip for candidate in san.get_values_for_type(x509.IPAddress)):
            return
        raise ProtocolError('peer certificate does not match requested IP address')
    dns_names = tuple(_normalized_dns_name(name) for name in san.get_values_for_type(x509.DNSName))
    if not dns_names:
        raise ProtocolError('peer certificate does not contain a DNS subjectAltName')
    if any(_dnsname_match(pattern, server_name) for pattern in dns_names):
        return
    raise ProtocolError('peer certificate does not match requested server name')


def _verify_signature(public_key: object, signature: bytes, payload: bytes, algorithm: object | None) -> None:
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        public_key.verify(signature, payload)
        return
    if isinstance(public_key, ed448.Ed448PublicKey):
        public_key.verify(signature, payload)
        return
    if isinstance(public_key, rsa.RSAPublicKey):
        if algorithm is None:
            raise ProtocolError('RSA signature is missing a hash algorithm')
        public_key.verify(signature, payload, asym_padding.PKCS1v15(), algorithm)
        return
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        if algorithm is None:
            raise ProtocolError('EC signature is missing a hash algorithm')
        public_key.verify(signature, payload, ec.ECDSA(algorithm))
        return
    raise ProtocolError('unsupported signature public key type')


def _subject_key_identifier_bytes(certificate: x509.Certificate) -> bytes:
    try:
        return certificate.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_KEY_IDENTIFIER).value.digest
    except x509.ExtensionNotFound:
        return x509.SubjectKeyIdentifier.from_public_key(certificate.public_key()).digest


def _build_policy_builder(
    trust_roots: Sequence[x509.Certificate],
    *,
    moment: datetime,
    max_chain_depth: int | None,
):
    if not _HAS_X509_VERIFICATION:
        return None
    builder = verification.PolicyBuilder().store(verification.Store(trust_roots)).time(moment)
    builder = builder.extension_policies(ca_policy=_WEBOOKI_CA_POLICY, ee_policy=_WEBOOKI_EE_POLICY)
    if max_chain_depth is not None:
        builder = builder.max_chain_depth(max_chain_depth)
    return builder


def _verify_server_path(
    chain: Sequence[x509.Certificate],
    trust_roots: Sequence[x509.Certificate],
    *,
    server_name: str,
    moment: datetime,
    policy: CertificateValidationPolicy,
) -> tuple[x509.Certificate, ...]:
    if not _HAS_X509_VERIFICATION:
        return _manual_verified_chain(chain, trust_roots, server_name=server_name, moment=moment, policy=policy)
    subject = _server_subject(server_name) if server_name else _first_subject_alt_name(chain[0])
    builder = _build_policy_builder(trust_roots, moment=moment, max_chain_depth=policy.max_chain_depth)
    verifier = builder.build_server_verifier(subject)
    return tuple(verifier.verify(chain[0], list(chain[1:])))


def _verify_client_path(
    chain: Sequence[x509.Certificate],
    trust_roots: Sequence[x509.Certificate],
    *,
    moment: datetime,
    policy: CertificateValidationPolicy,
) -> tuple[x509.Certificate, ...]:
    if not _HAS_X509_VERIFICATION:
        return _manual_verified_chain(chain, trust_roots, server_name='', moment=moment, policy=policy)
    builder = _build_policy_builder(trust_roots, moment=moment, max_chain_depth=policy.max_chain_depth)
    verifier = builder.build_client_verifier()
    result = verifier.verify(chain[0], list(chain[1:]))
    return tuple(result.chain)


def _load_revocation_material(material: RevocationMaterial) -> tuple[tuple[x509.CertificateRevocationList, ...], tuple[ocsp.OCSPResponse, ...]]:
    crls = tuple(_load_crl(item) for item in material.crls)
    responses = tuple(_load_ocsp_response(item) for item in material.ocsp_responses)
    return crls, responses


def _verify_crl(
    crl: x509.CertificateRevocationList,
    issuer: x509.Certificate,
    *,
    moment: datetime,
    freshness: RevocationFreshnessPolicy,
) -> None:
    if crl.issuer != issuer.subject:
        raise ProtocolError('CRL issuer does not match certificate issuer')
    last_update = _crl_last_update(crl)
    next_update = _crl_next_update(crl)
    skew = freshness.allowed_clock_skew
    if moment + skew < last_update:
        raise ProtocolError('CRL is not yet valid at the requested validation time')
    if next_update is None:
        raise ProtocolError('CRL does not contain a nextUpdate value')
    expiry = next_update + skew
    if freshness.crl_max_validity_window is not None:
        expiry = min(expiry, last_update + freshness.crl_max_validity_window)
    if moment > expiry:
        raise ProtocolError('CRL is not valid at the requested validation time')
    _verify_crl_signature(crl, issuer)
    try:
        key_usage = issuer.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
    except x509.ExtensionNotFound:
        key_usage = None
    if key_usage is not None and not key_usage.crl_sign:
        raise ProtocolError('CRL issuer is not permitted to sign CRLs')


def _crl_status(
    certificate: x509.Certificate,
    issuer: x509.Certificate,
    *,
    crls: Sequence[x509.CertificateRevocationList],
    moment: datetime,
    freshness: RevocationFreshnessPolicy,
) -> str:
    for crl in crls:
        if crl.issuer != issuer.subject:
            continue
        _verify_crl(crl, issuer, moment=moment, freshness=freshness)
        revoked = crl.get_revoked_certificate_by_serial_number(certificate.serial_number)
        if revoked is not None:
            return 'revoked'
        return 'good'
    return 'unknown'




def _ocsp_response_items(response: ocsp.OCSPResponse) -> tuple[object, ...]:
    items = getattr(response, 'responses', None)
    if items is not None:
        return tuple(items)
    if response.response_status is not ocsp.OCSPResponseStatus.SUCCESSFUL:
        return ()
    return (response,)

def _matching_ocsp_responses(
    response: ocsp.OCSPResponse,
    certificate: x509.Certificate,
    issuer: x509.Certificate,
) -> tuple[ocsp.OCSPSingleResponse, ...]:
    if response.response_status is not ocsp.OCSPResponseStatus.SUCCESSFUL:
        return ()
    candidates = _ocsp_response_items(response)
    matches: list[ocsp.OCSPSingleResponse] = []
    for single in candidates:
        request = ocsp.OCSPRequestBuilder().add_certificate(certificate, issuer, single.hash_algorithm).build()
        if single.serial_number != certificate.serial_number:
            continue
        if single.issuer_name_hash != request.issuer_name_hash:
            continue
        if single.issuer_key_hash != request.issuer_key_hash:
            continue
        matches.append(single)
    return tuple(matches)


def _is_valid_ocsp_signer(candidate: x509.Certificate, issuer: x509.Certificate, *, moment: datetime) -> bool:
    verify_certificate_validity(candidate, moment=moment)
    if candidate == issuer:
        return True
    try:
        eku = candidate.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE).value
    except x509.ExtensionNotFound:
        return False
    if ExtendedKeyUsageOID.OCSP_SIGNING not in eku:
        return False
    if candidate.issuer != issuer.subject:
        return False
    try:
        _verify_signature(
            issuer.public_key(),
            candidate.signature,
            candidate.tbs_certificate_bytes,
            candidate.signature_hash_algorithm,
        )
    except Exception:
        return False
    return True


def _resolve_ocsp_signer(
    response: ocsp.OCSPResponse,
    issuer: x509.Certificate,
    trust_roots: Sequence[x509.Certificate],
    *,
    moment: datetime,
) -> x509.Certificate | None:
    candidates: list[x509.Certificate] = []
    candidates.extend(response.certificates)
    candidates.append(issuer)
    candidates.extend(trust_roots)
    responder_name = response.responder_name
    responder_key_hash = response.responder_key_hash
    for candidate in candidates:
        if responder_name is not None and candidate.subject == responder_name:
            if _is_valid_ocsp_signer(candidate, issuer, moment=moment):
                return candidate
        if responder_key_hash is not None and _subject_key_identifier_bytes(candidate) == responder_key_hash:
            if _is_valid_ocsp_signer(candidate, issuer, moment=moment):
                return candidate
    return None


def _ocsp_single_expiry(
    single: ocsp.OCSPSingleResponse,
    *,
    response: ocsp.OCSPResponse,
    freshness: RevocationFreshnessPolicy,
) -> datetime | None:
    base = max(_ocsp_single_this_update(single), _ocsp_response_produced_at(response))
    candidates: list[datetime] = []
    next_update = _ocsp_single_next_update(single)
    if next_update is not None:
        candidates.append(next_update + freshness.allowed_clock_skew)
    elif freshness.ocsp_max_age_without_next_update is not None:
        candidates.append(base + freshness.ocsp_max_age_without_next_update)
    if freshness.ocsp_max_validity_window is not None:
        candidates.append(base + freshness.ocsp_max_validity_window)
    if not candidates:
        return None
    return min(candidates)


def _ocsp_status(
    certificate: x509.Certificate,
    issuer: x509.Certificate,
    *,
    responses: Sequence[ocsp.OCSPResponse],
    trust_roots: Sequence[x509.Certificate],
    moment: datetime,
    freshness: RevocationFreshnessPolicy,
) -> str:
    skew = freshness.allowed_clock_skew
    for response in responses:
        matches = _matching_ocsp_responses(response, certificate, issuer)
        if not matches:
            continue
        signer = _resolve_ocsp_signer(response, issuer, trust_roots, moment=moment)
        if signer is None:
            continue
        try:
            _verify_signature(
                signer.public_key(),
                response.signature,
                response.tbs_response_bytes,
                response.signature_hash_algorithm,
            )
        except Exception:
            continue
        produced_at = _ocsp_response_produced_at(response)
        if produced_at > moment + skew:
            continue
        for single in matches:
            if _ocsp_single_this_update(single) > moment + skew:
                continue
            expiry = _ocsp_single_expiry(single, response=response, freshness=freshness)
            if expiry is not None and moment > expiry:
                continue
            if single.certificate_status is ocsp.OCSPCertStatus.REVOKED:
                return 'revoked'
            if single.certificate_status is ocsp.OCSPCertStatus.GOOD:
                return 'good'
            return 'unknown'
    return 'unknown'


def _header_map(headers: Sequence[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers:
        result[key.lower()] = value
    return result


def _parse_http_cache_headers(
    fetched_at: datetime,
    headers: Sequence[tuple[str, str]],
) -> tuple[datetime | None, bool]:
    mapping = _header_map(headers)
    directives = mapping.get('cache-control', '')
    cacheable = True
    max_age: int | None = None
    for item in directives.split(','):
        token = item.strip()
        if not token:
            continue
        lower = token.lower()
        if lower in {'no-store', 'no-cache'}:
            cacheable = False
        if '=' not in token:
            continue
        key, value = token.split('=', 1)
        if key.strip().lower() != 'max-age':
            continue
        try:
            max_age = max(0, int(value.strip().strip('"')))
        except ValueError:
            continue
    if not cacheable:
        return None, False
    candidates: list[datetime] = []
    if max_age is not None:
        candidates.append(fetched_at + timedelta(seconds=max_age))
    expires = mapping.get('expires')
    if expires:
        try:
            expiry = parsedate_to_datetime(expires)
        except (TypeError, ValueError, IndexError):
            expiry = None
        if expiry is not None:
            candidates.append(_as_utc(expiry))
    if not candidates:
        return None, True
    return min(candidates), True


def _ensure_revocation_uri_allowed(url: str, fetch_policy: RevocationFetchPolicy) -> None:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if not scheme:
        raise _RevocationFetchError('revocation endpoint URI is missing a scheme')
    if scheme not in fetch_policy.allowed_schemes:
        raise _RevocationFetchError(f'revocation endpoint URI scheme {scheme!r} is not allowed')


def _fetch_revocation_payload(
    url: str,
    *,
    fetch_policy: RevocationFetchPolicy,
    method: str = 'GET',
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> _FetchedRevocationPayload:
    _ensure_revocation_uri_allowed(url, fetch_policy)
    request_headers = {'User-Agent': fetch_policy.user_agent}
    if headers:
        request_headers.update(headers)
    request = Request(url=url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=fetch_policy.timeout_seconds) as response:
            status = getattr(response, 'status', None)
            if status is not None and not (200 <= int(status) < 300):
                raise _RevocationFetchError(f'revocation endpoint returned HTTP {status}')
            body = response.read(fetch_policy.max_response_bytes + 1)
            if len(body) > fetch_policy.max_response_bytes:
                raise _RevocationFetchError('revocation endpoint response exceeded configured size limit')
            fetched_at = datetime.now(timezone.utc)
            content_type = None
            if hasattr(response.headers, 'get_content_type'):
                content_type = response.headers.get_content_type()
            if content_type is None:
                content_type = response.headers.get('Content-Type')
            return _FetchedRevocationPayload(
                payload=body,
                fetched_at=fetched_at,
                headers=tuple((key.lower(), value) for key, value in response.headers.items()),
                content_type=content_type,
            )
    except HTTPError as exc:
        raise _RevocationFetchError(f'revocation endpoint returned HTTP {exc.code}') from exc
    except URLError as exc:
        raise _RevocationFetchError(f'revocation endpoint fetch failed: {exc.reason}') from exc
    except OSError as exc:
        raise _RevocationFetchError(f'revocation endpoint fetch failed: {exc}') from exc


def _deduplicated(values: Iterable[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def _ocsp_aia_urls(certificate: x509.Certificate) -> tuple[str, ...]:
    try:
        extension = certificate.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
    except x509.ExtensionNotFound:
        return ()
    uris: list[str] = []
    for access_description in extension:
        if access_description.access_method != AuthorityInformationAccessOID.OCSP:
            continue
        location = access_description.access_location
        if isinstance(location, x509.UniformResourceIdentifier):
            uris.append(location.value)
    return _deduplicated(uris)


def _crl_distribution_point_urls(certificate: x509.Certificate) -> tuple[str, ...]:
    try:
        extension = certificate.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS).value
    except x509.ExtensionNotFound:
        return ()
    uris: list[str] = []
    for point in extension:
        if point.full_name is None:
            continue
        for name in point.full_name:
            if isinstance(name, x509.UniformResourceIdentifier):
                uris.append(name.value)
    return _deduplicated(uris)


def _ocsp_request_bytes(certificate: x509.Certificate, issuer: x509.Certificate) -> bytes:
    request = ocsp.OCSPRequestBuilder().add_certificate(certificate, issuer, hashes.SHA1()).build()
    return request.public_bytes(serialization.Encoding.DER)


def _ocsp_cache_key(url: str, request_bytes: bytes) -> tuple[str, str, str]:
    fingerprint = hashes.Hash(hashes.SHA256())
    fingerprint.update(request_bytes)
    return 'ocsp', url, fingerprint.finalize().hex()


def _crl_cache_key(url: str) -> tuple[str, str, str]:
    return 'crl', url, ''


def _ocsp_cache_expiry(
    response: ocsp.OCSPResponse,
    certificate: x509.Certificate,
    issuer: x509.Certificate,
    *,
    fetched_at: datetime,
    headers: Sequence[tuple[str, str]],
    freshness: RevocationFreshnessPolicy,
) -> datetime | None:
    if response.response_status is not ocsp.OCSPResponseStatus.SUCCESSFUL:
        return None
    matches = _matching_ocsp_responses(response, certificate, issuer)
    if not matches:
        return None
    header_expiry, cacheable = _parse_http_cache_headers(fetched_at, headers)
    if not cacheable:
        return None
    candidates: list[datetime] = []
    if header_expiry is not None:
        candidates.append(header_expiry)
    for single in matches:
        expiry = _ocsp_single_expiry(single, response=response, freshness=freshness)
        if expiry is not None:
            candidates.append(expiry)
    if not candidates:
        return None
    return min(candidates)


def _crl_cache_expiry(
    crl: x509.CertificateRevocationList,
    *,
    fetched_at: datetime,
    headers: Sequence[tuple[str, str]],
    freshness: RevocationFreshnessPolicy,
) -> datetime | None:
    header_expiry, cacheable = _parse_http_cache_headers(fetched_at, headers)
    if not cacheable:
        return None
    candidates: list[datetime] = []
    if header_expiry is not None:
        candidates.append(header_expiry)
    next_update = _crl_next_update(crl)
    if next_update is not None:
        candidates.append(next_update + freshness.allowed_clock_skew)
    if freshness.crl_max_validity_window is not None:
        candidates.append(_crl_last_update(crl) + freshness.crl_max_validity_window)
    if not candidates:
        return None
    return min(candidates)


def _fetch_online_revocation_material(
    certificate: x509.Certificate,
    issuer: x509.Certificate,
    *,
    fetch_policy: RevocationFetchPolicy,
    moment: datetime,
) -> _FetchedRevocationMaterial:
    fetched_crls: list[x509.CertificateRevocationList] = []
    fetched_responses: list[ocsp.OCSPResponse] = []
    errors: list[str] = []
    cache = fetch_policy.cache
    freshness = fetch_policy.freshness

    if fetch_policy.enable_ocsp_aia:
        request_bytes = _ocsp_request_bytes(certificate, issuer)
        for url in _ocsp_aia_urls(certificate):
            kind, endpoint, fingerprint = _ocsp_cache_key(url, request_bytes)
            cached = cache.get(kind, endpoint, fingerprint, moment=moment) if cache is not None else None
            if cached is not None:
                try:
                    fetched_responses.append(_load_ocsp_response(cached.payload))
                    continue
                except ValueError:
                    if cache is not None:
                        cache.delete(kind, endpoint, fingerprint)
            try:
                payload = _fetch_revocation_payload(
                    url,
                    fetch_policy=fetch_policy,
                    method='POST',
                    data=request_bytes,
                    headers={
                        'Accept': 'application/ocsp-response',
                        'Content-Type': 'application/ocsp-request',
                    },
                )
                response = _load_ocsp_response(payload.payload)
                fetched_responses.append(response)
                expiry = _ocsp_cache_expiry(
                    response,
                    certificate,
                    issuer,
                    fetched_at=payload.fetched_at,
                    headers=payload.headers,
                    freshness=freshness,
                )
                if cache is not None and expiry is not None:
                    cache.put(
                        kind,
                        endpoint,
                        fingerprint,
                        RevocationCacheEntry(
                            payload=payload.payload,
                            fetched_at=payload.fetched_at,
                            expires_at=expiry,
                            content_type=payload.content_type,
                        ),
                    )
            except (ValueError, _RevocationFetchError) as exc:
                errors.append(f'OCSP {url}: {exc}')

    if fetch_policy.enable_crl_distribution_points:
        for url in _crl_distribution_point_urls(certificate):
            kind, endpoint, fingerprint = _crl_cache_key(url)
            cached = cache.get(kind, endpoint, fingerprint, moment=moment) if cache is not None else None
            if cached is not None:
                try:
                    fetched_crls.append(_load_crl(cached.payload))
                    continue
                except ValueError:
                    if cache is not None:
                        cache.delete(kind, endpoint, fingerprint)
            try:
                payload = _fetch_revocation_payload(url, fetch_policy=fetch_policy)
                crl = _load_crl(payload.payload)
                fetched_crls.append(crl)
                expiry = _crl_cache_expiry(crl, fetched_at=payload.fetched_at, headers=payload.headers, freshness=freshness)
                if cache is not None and expiry is not None:
                    cache.put(
                        kind,
                        endpoint,
                        fingerprint,
                        RevocationCacheEntry(
                            payload=payload.payload,
                            fetched_at=payload.fetched_at,
                            expires_at=expiry,
                            content_type=payload.content_type,
                        ),
                    )
            except (ValueError, _RevocationFetchError) as exc:
                errors.append(f'CRL {url}: {exc}')

    return _FetchedRevocationMaterial(
        crls=tuple(fetched_crls),
        ocsp_responses=tuple(fetched_responses),
        errors=tuple(errors),
    )


def _enforce_revocation_policy(
    chain: Sequence[x509.Certificate],
    trust_roots: Sequence[x509.Certificate],
    *,
    policy: CertificateValidationPolicy,
    moment: datetime,
) -> None:
    if policy.revocation_mode is RevocationMode.OFF:
        return
    crls, responses = _load_revocation_material(policy.revocation_material)
    fetch_policy = policy.revocation_fetch_policy
    freshness = fetch_policy.freshness if fetch_policy is not None else RevocationFreshnessPolicy()
    if (
        not crls
        and not responses
        and fetch_policy is None
        and policy.revocation_mode is RevocationMode.REQUIRE
    ):
        raise ProtocolError('revocation checking was required but no revocation evidence or fetch policy was provided')

    for index in range(len(chain) - 1):
        certificate = chain[index]
        issuer = chain[index + 1]
        status = _ocsp_status(
            certificate,
            issuer,
            responses=responses,
            trust_roots=trust_roots,
            moment=moment,
            freshness=freshness,
        )
        if status == 'good':
            continue
        if status == 'revoked':
            raise ProtocolError('peer certificate has been revoked')
        status = _crl_status(
            certificate,
            issuer,
            crls=crls,
            moment=moment,
            freshness=freshness,
        )
        if status == 'good':
            continue
        if status == 'revoked':
            raise ProtocolError('peer certificate has been revoked')

        online_errors: tuple[str, ...] = ()
        if fetch_policy is not None:
            fetched = _fetch_online_revocation_material(
                certificate,
                issuer,
                fetch_policy=fetch_policy,
                moment=moment,
            )
            online_errors = fetched.errors
            if fetched.ocsp_responses:
                status = _ocsp_status(
                    certificate,
                    issuer,
                    responses=fetched.ocsp_responses,
                    trust_roots=trust_roots,
                    moment=moment,
                    freshness=freshness,
                )
                if status == 'good':
                    continue
                if status == 'revoked':
                    raise ProtocolError('peer certificate has been revoked')
            if fetched.crls:
                status = _crl_status(
                    certificate,
                    issuer,
                    crls=fetched.crls,
                    moment=moment,
                    freshness=freshness,
                )
                if status == 'good':
                    continue
                if status == 'revoked':
                    raise ProtocolError('peer certificate has been revoked')

        if policy.revocation_mode is RevocationMode.REQUIRE:
            detail = ''
            if online_errors:
                detail = f': {online_errors[0]}'
            raise ProtocolError(f'revocation status could not be established for the certificate chain{detail}')


def verify_certificate_chain(
    chain_pems: Iterable[bytes],
    trust_roots_pems: Iterable[bytes],
    *,
    server_name: str = '',
    moment: datetime | None = None,
    policy: CertificateValidationPolicy | None = None,
) -> x509.Certificate:
    chain = load_pem_certificates(chain_pems)
    if not chain:
        raise ProtocolError('peer did not provide a certificate chain')
    trust_roots = load_pem_certificates(trust_roots_pems)
    if not trust_roots:
        raise ProtocolError('certificate verification requires at least one trusted root or pinned certificate')
    validation_policy = policy or CertificateValidationPolicy()
    validation_time = _as_utc(moment)

    try:
        if validation_policy.purpose is CertificatePurpose.CLIENT_AUTH:
            verified_chain = _verify_client_path(chain, trust_roots, moment=validation_time, policy=validation_policy)
        else:
            verified_chain = _verify_server_path(
                chain,
                trust_roots,
                server_name=server_name,
                moment=validation_time,
                policy=validation_policy,
            )
    except Exception as exc:
        if _HAS_X509_VERIFICATION and isinstance(exc, verification.VerificationError):
            raise ProtocolError(f'peer certificate chain verification failed: {exc}') from exc
        if isinstance(exc, ProtocolError):
            raise
        raise ProtocolError(f'peer certificate chain verification failed: {exc}') from exc
    except ValueError as exc:
        raise ProtocolError(f'peer certificate chain verification failed: {exc}') from exc

    _enforce_revocation_policy(verified_chain, trust_roots, policy=validation_policy, moment=validation_time)
    return verified_chain[0]


__all__ = [
    'CertificatePurpose',
    'CertificateValidationPolicy',
    'RevocationCache',
    'RevocationCacheEntry',
    'RevocationFetchPolicy',
    'RevocationFreshnessPolicy',
    'RevocationMaterial',
    'RevocationMode',
    'VerifiedCertificatePath',
    'load_pem_certificates',
    'load_crls_from_file',
    'verify_certificate_chain',
    'verify_certificate_hostname',
    'verify_certificate_validity',
]
