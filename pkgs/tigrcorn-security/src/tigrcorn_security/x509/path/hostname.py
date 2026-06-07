from __future__ import annotations

from .imports import *
from .models import *
from .constraints import *
from .time import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
