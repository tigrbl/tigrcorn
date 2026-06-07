from __future__ import annotations

from .imports import *
from .models import *
from .time import *
from .constraints import *
from .loading import *
from .chain import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
