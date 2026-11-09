from __future__ import annotations

from .imports import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
