from __future__ import annotations

from tigrcorn_core.errors import ConfigError

CIPHER_TLS_AES_128_GCM_SHA256 = 0x1301
CIPHER_TLS_AES_256_GCM_SHA384 = 0x1302

SUPPORTED_TLS13_CIPHER_SUITES = (
    CIPHER_TLS_AES_256_GCM_SHA384,
    CIPHER_TLS_AES_128_GCM_SHA256,
)

CIPHER_SUITE_NAME_TO_ID = {
    'TLS_AES_128_GCM_SHA256': CIPHER_TLS_AES_128_GCM_SHA256,
    'TLS_AES_256_GCM_SHA384': CIPHER_TLS_AES_256_GCM_SHA384,
}


def tls13_cipher_suite_name(cipher_suite: int) -> str:
    for name, value in CIPHER_SUITE_NAME_TO_ID.items():
        if value == cipher_suite:
            return name
    return f'0x{cipher_suite:04x}'


def parse_tls13_cipher_allowlist(value: str | None) -> tuple[int, ...]:
    if value is None:
        return ()
    tokens = [token.strip() for token in value.replace(',', ':').split(':') if token.strip()]
    if not tokens:
        raise ConfigError('ssl_ciphers must contain at least one TLS 1.3 cipher suite name')
    resolved: list[int] = []
    for token in tokens:
        if token not in CIPHER_SUITE_NAME_TO_ID:
            raise ConfigError(f'unsupported TLS 1.3 cipher suite: {token!r}')
        cipher_suite = CIPHER_SUITE_NAME_TO_ID[token]
        if cipher_suite not in resolved:
            resolved.append(cipher_suite)
    return tuple(resolved)


def format_tls13_cipher_allowlist(cipher_suites: tuple[int, ...] | list[int]) -> str:
    return ':'.join(tls13_cipher_suite_name(cipher_suite) for cipher_suite in cipher_suites)
