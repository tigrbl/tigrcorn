from __future__ import annotations

from .imports import *
from .models import *
from .time import *
from .constraints import *
from .loading import *
from .hostname import *
from .chain import *
from .revocation_material import *
from .revocation_fetch import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
