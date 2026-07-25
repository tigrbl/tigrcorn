from __future__ import annotations

from .imports import *
from .alerts import *
from .utils import *

def _signature_algorithms_for_public_key(public_key: object) -> tuple[int, ...]:
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        return (SIG_ED25519,)
    if isinstance(public_key, rsa.RSAPublicKey):
        return (SIG_RSA_PSS_RSAE_SHA256, SIG_RSA_PSS_PSS_SHA256)
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        if isinstance(public_key.curve, ec.SECP256R1):
            return (SIG_ECDSA_SECP256R1_SHA256,)
        if isinstance(public_key.curve, ec.SECP384R1):
            return (SIG_ECDSA_SECP384R1_SHA384,)
    return ()



def _select_certificate_verify_scheme(offered: Sequence[int], public_key: object) -> int:
    compatible = _signature_algorithms_for_public_key(public_key)
    for scheme in offered:
        if scheme in compatible:
            return scheme
    _raise_tls(AlertDescription.HANDSHAKE_FAILURE, 'no compatible certificate signature algorithm')



def _sign_with_scheme(private_key: object, scheme: int, payload: bytes) -> bytes:
    if scheme == SIG_ED25519:
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'certificate key is not compatible with ed25519')
        return private_key.sign(payload)
    if scheme in {SIG_RSA_PSS_RSAE_SHA256, SIG_RSA_PSS_PSS_SHA256}:
        if not isinstance(private_key, rsa.RSAPrivateKey):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'certificate key is not compatible with RSA-PSS')
        return private_key.sign(
            payload,
            asym_padding.PSS(mgf=asym_padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
            hashes.SHA256(),
        )
    if scheme == SIG_ECDSA_SECP256R1_SHA256:
        if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(private_key.curve, ec.SECP256R1):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'certificate key is not compatible with ECDSA P-256')
        return private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    if scheme == SIG_ECDSA_SECP384R1_SHA384:
        if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(private_key.curve, ec.SECP384R1):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'certificate key is not compatible with ECDSA P-384')
        return private_key.sign(payload, ec.ECDSA(hashes.SHA384()))
    _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'unsupported certificate verify signature algorithm')



def _verify_with_scheme(public_key: object, scheme: int, signature: bytes, payload: bytes) -> None:
    try:
        if scheme == SIG_ED25519:
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer certificate key is not compatible with ed25519')
            public_key.verify(signature, payload)
            return
        if scheme in {SIG_RSA_PSS_RSAE_SHA256, SIG_RSA_PSS_PSS_SHA256}:
            if not isinstance(public_key, rsa.RSAPublicKey):
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer certificate key is not compatible with RSA-PSS')
            public_key.verify(
                signature,
                payload,
                asym_padding.PSS(mgf=asym_padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
                hashes.SHA256(),
            )
            return
        if scheme == SIG_ECDSA_SECP256R1_SHA256:
            if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer certificate key is not compatible with ECDSA P-256')
            public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
            return
        if scheme == SIG_ECDSA_SECP384R1_SHA384:
            if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP384R1):
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer certificate key is not compatible with ECDSA P-384')
            public_key.verify(signature, payload, ec.ECDSA(hashes.SHA384()))
            return
    except TlsAlertError:
        raise
    except Exception as exc:  # pragma: no cover - crypto backend specifics vary.
        _raise_tls(AlertDescription.DECRYPT_ERROR, 'peer CertificateVerify signature is invalid')
    _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'unsupported peer certificate verify signature algorithm')

__all__ = [name for name in globals() if not name.startswith('__')]
