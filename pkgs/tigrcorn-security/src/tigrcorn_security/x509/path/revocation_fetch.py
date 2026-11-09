from __future__ import annotations

from .imports import *
from .models import *
from .time import *
from .loading import *
from .revocation_material import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
