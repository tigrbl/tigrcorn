from __future__ import annotations

from .imports import *
from .alerts import *
from .utils import *

def _generate_key_share(group: int) -> tuple[object, bytes]:
    if group == GROUP_X25519:
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        return private_key, public_key
    if group == GROUP_SECP256R1:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return private_key, public_key
    raise ValueError(f'unsupported TLS key share group: {group}')



def _derive_shared_secret(private_key: object, group: int, peer_key_exchange: bytes) -> bytes:
    try:
        if group == GROUP_X25519:
            if not isinstance(private_key, x25519.X25519PrivateKey):
                _raise_tls(AlertDescription.INTERNAL_ERROR, 'x25519 key share state is unavailable')
            peer_public = x25519.X25519PublicKey.from_public_bytes(peer_key_exchange)
            return private_key.exchange(peer_public)
        if group == GROUP_SECP256R1:
            if not isinstance(private_key, ec.EllipticCurvePrivateKey):
                _raise_tls(AlertDescription.INTERNAL_ERROR, 'secp256r1 key share state is unavailable')
            peer_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), peer_key_exchange)
            return private_key.exchange(ec.ECDH(), peer_public)
    except TlsAlertError:
        raise
    except Exception:  # pragma: no cover - crypto backend specifics vary.
        _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer key share could not be processed')
    _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'unsupported TLS key share group')



def _preferred_supported_group(*, supported_groups: Sequence[int], key_shares: dict[int, bytes]) -> int | None:
    for group in SUPPORTED_GROUPS:
        if group in key_shares:
            return group
    for group in SUPPORTED_GROUPS:
        if group in supported_groups:
            return group
    return None


def _select_cipher_suite(offered: Sequence[int], supported: Sequence[int]) -> int | None:
    for cipher_suite in supported:
        if cipher_suite in offered:
            return cipher_suite
    return None

__all__ = [name for name in globals() if not name.startswith('__')]
