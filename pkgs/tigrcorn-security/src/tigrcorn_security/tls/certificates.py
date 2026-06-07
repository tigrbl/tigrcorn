from __future__ import annotations

from .imports import *

def describe_peer_certificate(certificate: x509.Certificate) -> dict[str, Any]:
    return {
        'subject': certificate.subject.rfc4514_string(),
        'issuer': certificate.issuer.rfc4514_string(),
        'serial_number': hex(certificate.serial_number),
        'not_valid_before': _iso_utc(
            certificate.not_valid_before_utc if hasattr(certificate, 'not_valid_before_utc') else certificate.not_valid_before
        ),
        'not_valid_after': _iso_utc(
            certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else certificate.not_valid_after
        ),
    }


def tls_extension_payload(writer: Any) -> dict[str, Any] | None:
    ssl_object = getattr(writer, 'get_extra_info', lambda *args, **kwargs: None)('ssl_object')
    if ssl_object is None:
        return None
    payload: dict[str, Any] = {}
    selected_alpn = getattr(ssl_object, 'selected_alpn_protocol', lambda: None)()
    if selected_alpn is not None:
        payload['selected_alpn_protocol'] = selected_alpn
    getpeercert = getattr(ssl_object, 'getpeercert', None)
    if callable(getpeercert):
        peer_cert = getpeercert(binary_form=False)
        if peer_cert is not None:
            payload['peer_cert'] = peer_cert
    return payload or None


def verify_certificate_chain(
    chain_pems: Iterable[bytes],
    trust_roots_pems: Iterable[bytes],
    *,
    server_name: str = '',
    moment: datetime | None = None,
    policy: CertificateValidationPolicy | None = None,
) -> x509.Certificate:
    return _verify_certificate_chain(
        chain_pems,
        trust_roots_pems,
        server_name=server_name,
        moment=moment,
        policy=policy,
    )

def _iso_utc(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

__all__ = [name for name in globals() if not name.startswith('__')]
