from __future__ import annotations

from .imports import *
from .models import *
from .constraints import *
from .time import *
from .hostname import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
