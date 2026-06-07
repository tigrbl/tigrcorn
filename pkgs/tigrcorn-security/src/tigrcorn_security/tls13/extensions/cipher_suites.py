from __future__ import annotations

from .imports import *
from .models import *

def cipher_suite_name(cipher_suite: int) -> str:
    return _CIPHER_SUITE_NAMES.get(cipher_suite, f'0x{cipher_suite:04x}')


def parse_cipher_suite_allowlist(value: str | None) -> tuple[int, ...]:
    if value is None:
        return ()
    tokens = [token.strip() for token in value.replace(',', ':').split(':') if token.strip()]
    if not tokens:
        raise ProtocolError('ssl_ciphers must contain at least one supported TLS 1.3 cipher suite')
    resolved: list[int] = []
    for token in tokens:
        cipher_suite = _CIPHER_SUITE_NAME_TO_ID.get(token)
        if cipher_suite is None:
            raise ProtocolError(f'unsupported TLS cipher suite: {token!r}')
        if cipher_suite not in resolved:
            resolved.append(cipher_suite)
    return tuple(resolved)


def format_cipher_suite_allowlist(cipher_suites: Sequence[int]) -> str:
    return ':'.join(cipher_suite_name(cipher_suite) for cipher_suite in cipher_suites)


def cipher_suite_parameters(cipher_suite: int) -> CipherSuiteParameters:
    try:
        return _CIPHER_SUITE_PARAMETERS[cipher_suite]
    except KeyError as exc:
        raise ProtocolError(f'unsupported TLS cipher suite: {cipher_suite:#06x}') from exc

__all__ = [name for name in globals() if not name.startswith('__')]
