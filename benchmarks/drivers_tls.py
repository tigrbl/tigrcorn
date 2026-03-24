from __future__ import annotations

from pathlib import Path

from benchmarks.common import measure_sync
from tigrcorn.config.model import ListenerConfig
from tigrcorn.security.alpn import normalize_alpn_list
from tigrcorn.security.tls import build_server_ssl_context


def _fixture_paths(source_root: Path) -> tuple[str, str, str]:
    cert = source_root / 'tests/fixtures_certs/interop-localhost-cert.pem'
    key = source_root / 'tests/fixtures_certs/interop-localhost-key.pem'
    ca = source_root / 'tests/fixtures_certs/interop-client-cert.pem'
    return str(cert), str(key), str(ca)


def tls_handshake_driver(profile, *, source_root: Path):
    cert, key, _ca = _fixture_paths(source_root)
    def operation():
        listener = ListenerConfig(ssl_certfile=cert, ssl_keyfile=key, alpn_protocols=['h2', 'http/1.1'])
        ctx = build_server_ssl_context(listener)
        return {
            'connections': 1,
            'correctness': {
                'context_built': ctx is not None,
                'default_alpn': ctx is not None and 'h2' in ctx.alpn_protocols,
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def mtls_handshake_driver(profile, *, source_root: Path):
    cert, key, ca = _fixture_paths(source_root)
    def operation():
        listener = ListenerConfig(
            ssl_certfile=cert,
            ssl_keyfile=key,
            ssl_ca_certs=ca,
            ssl_require_client_cert=True,
            alpn_protocols=['h2', 'http/1.1'],
        )
        ctx = build_server_ssl_context(listener)
        return {
            'connections': 1,
            'correctness': {
                'context_built': ctx is not None,
                'requires_client_cert': ctx is not None and ctx.require_client_certificate,
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def ocsp_strict_driver(profile, *, source_root: Path):
    cert, key, ca = _fixture_paths(source_root)
    def operation():
        listener = ListenerConfig(
            ssl_certfile=cert,
            ssl_keyfile=key,
            ssl_ca_certs=ca,
            ssl_require_client_cert=True,
            ocsp_mode='require',
            revocation_fetch=False,
            alpn_protocols=['h2', 'http/1.1'],
        )
        ctx = build_server_ssl_context(listener)
        mode = getattr(ctx.validation_policy.revocation_mode, 'name', None) if ctx is not None else None
        return {
            'connections': 1,
            'correctness': {
                'context_built': ctx is not None,
                'ocsp_mode_require': mode == 'REQUIRE',
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def alpn_negotiation_driver(profile, *, source_root: Path):
    values = list(profile.driver_config.get('values', ['h2', 'http/1.1']))
    def operation():
        normalized = normalize_alpn_list(values, for_udp='h3' in values)
        return {
            'connections': 1,
            'correctness': {
                'normalized_nonempty': bool(normalized),
                'preserves_h2_or_h3': ('h2' in normalized) or ('h3' in normalized),
            },
            'metadata': {'normalized': normalized},
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)
