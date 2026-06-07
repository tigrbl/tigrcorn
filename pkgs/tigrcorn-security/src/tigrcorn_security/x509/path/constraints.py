from __future__ import annotations

from .imports import *
from .models import *
from .time import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
