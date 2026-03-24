from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from tigrcorn.config.model import ListenerConfig
from tigrcorn.security.x509.path import (
    CertificatePurpose,
    CertificateValidationPolicy,
    RevocationCache,
    RevocationFetchPolicy,
    RevocationFreshnessPolicy,
    RevocationMode,
)


@dataclass(slots=True)
class TLSPolicy:
    require_client_cert: bool = False


def revocation_mode_from_listener(listener: ListenerConfig) -> RevocationMode:
    mode = getattr(listener, 'ocsp_mode', 'off') or 'off'
    if mode == 'require':
        return RevocationMode.REQUIRE
    if mode == 'soft-fail' or (getattr(listener, 'ocsp_soft_fail', False) and mode != 'off'):
        return RevocationMode.SOFT_FAIL
    return RevocationMode.OFF


def build_validation_policy_for_listener(listener: ListenerConfig) -> CertificateValidationPolicy:
    ocsp_max_age = getattr(listener, 'ocsp_max_age', None)
    freshness = RevocationFreshnessPolicy(
        ocsp_max_age_without_next_update=timedelta(seconds=ocsp_max_age) if ocsp_max_age is not None else RevocationFreshnessPolicy().ocsp_max_age_without_next_update,
    )
    fetch_policy = RevocationFetchPolicy(
        enable_ocsp_aia=getattr(listener, 'revocation_fetch', True),
        enable_crl_distribution_points=getattr(listener, 'crl_mode', 'off') != 'off' and getattr(listener, 'revocation_fetch', True),
        freshness=freshness,
        cache=RevocationCache(max_entries=max(1, int(getattr(listener, 'ocsp_cache_size', 128) or 128))),
    )
    if not getattr(listener, 'revocation_fetch', True):
        fetch_policy = None
    return CertificateValidationPolicy(
        purpose=CertificatePurpose.CLIENT_AUTH,
        revocation_mode=revocation_mode_from_listener(listener),
        revocation_fetch_policy=fetch_policy,
    )


__all__ = [
    'TLSPolicy',
    'build_validation_policy_for_listener',
    'revocation_mode_from_listener',
]
