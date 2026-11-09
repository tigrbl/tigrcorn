from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from tigrcorn_config.model import ListenerConfig
from tigrcorn_security.x509.path import (
    CertificatePurpose,
    CertificateValidationPolicy,
    RevocationCache,
    RevocationFetchPolicy,
    RevocationFreshnessPolicy,
    RevocationMaterial,
    RevocationMode,
    load_crls_from_file,
)


@dataclass(slots=True)
class TLSPolicy:
    require_client_cert: bool = False


def revocation_mode_from_listener(listener: ListenerConfig) -> RevocationMode:
    ocsp_mode = getattr(listener, 'ocsp_mode', 'off') or 'off'
    crl_mode = getattr(listener, 'crl_mode', 'off') or 'off'
    if 'require' in {ocsp_mode, crl_mode}:
        return RevocationMode.REQUIRE
    if (
        'soft-fail' in {ocsp_mode, crl_mode}
        or (getattr(listener, 'ocsp_soft_fail', False) and ocsp_mode != 'off')
    ):
        return RevocationMode.SOFT_FAIL
    return RevocationMode.OFF


def build_validation_policy_for_listener(listener: ListenerConfig) -> CertificateValidationPolicy:
    ocsp_max_age = getattr(listener, 'ocsp_max_age', None)
    freshness = RevocationFreshnessPolicy(
        ocsp_max_age_without_next_update=timedelta(seconds=ocsp_max_age) if ocsp_max_age is not None else RevocationFreshnessPolicy().ocsp_max_age_without_next_update,
    )
    revocation_fetch_enabled = getattr(listener, 'revocation_fetch', True)
    ocsp_enabled = getattr(listener, 'ocsp_mode', 'off') != 'off'
    crl_enabled = getattr(listener, 'crl_mode', 'off') != 'off'
    fetch_policy = RevocationFetchPolicy(
        enable_ocsp_aia=revocation_fetch_enabled and ocsp_enabled,
        enable_crl_distribution_points=revocation_fetch_enabled and crl_enabled,
        freshness=freshness,
        cache=RevocationCache(max_entries=max(1, int(getattr(listener, 'ocsp_cache_size', 128) or 128))),
    )
    if not revocation_fetch_enabled or (not ocsp_enabled and not crl_enabled):
        fetch_policy = None
    local_crls = ()
    if getattr(listener, 'ssl_crl', None):
        local_crls = load_crls_from_file(str(listener.ssl_crl))
    return CertificateValidationPolicy(
        purpose=CertificatePurpose.CLIENT_AUTH,
        revocation_mode=revocation_mode_from_listener(listener),
        revocation_material=RevocationMaterial(crls=local_crls),
        revocation_fetch_policy=fetch_policy,
    )


__all__ = [
    'TLSPolicy',
    'build_validation_policy_for_listener',
    'revocation_mode_from_listener',
]
