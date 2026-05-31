from __future__ import annotations

import dataclasses
from copy import deepcopy
from typing import Any, Mapping

from .defaults import default_config
from .merge import merge_config_dicts


def _dataclass_to_dict(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: _dataclass_to_dict(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, list):
        return [_dataclass_to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [_dataclass_to_dict(item) for item in value]
    return value


def _profile(
    *,
    profile_id: str,
    extends: str | None,
    description: str,
    claim_ids: list[str],
    rfc_targets: list[str],
    required_overrides: list[str],
    explicit_posture: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        'profile_id': profile_id,
        'extends': extends,
        'description': description,
        'claim_ids': list(claim_ids),
        'rfc_targets': list(rfc_targets),
        'required_overrides': list(required_overrides),
        'explicit_posture': deepcopy(dict(explicit_posture)),
        'config': deepcopy(dict(config)),
    }


_PROFILE_REGISTRY: dict[str, dict[str, Any]] = {
    'default': _profile(
        profile_id='default',
        extends=None,
        description='Safe zero-config baseline with a single TCP HTTP/1.1 listener and deny-by-default transport posture.',
        claim_ids=['TC-PROFILE-DEFAULT-BASELINE'],
        rfc_targets=['RFC 9112'],
        required_overrides=[],
        explicit_posture={
            'protocol_family': 'http1-only',
            'proxy_trust': 'disabled',
            'connect': 'deny',
            'trusted_proxy_behavior': 'disabled',
            'static_serving': 'disabled',
            'early_data': 'deny_or_not_applicable',
            'http3_quic': 'disabled',
        },
        config={
            'app': {'profile': 'default'},
            'http': {
                'http_versions': ['1.1'],
                'enable_h2c': False,
                'connect_policy': 'deny',
                'trailer_policy': 'pass',
                'content_coding_policy': 'allowlist',
                'alt_svc_auto': False,
                'alt_svc_headers': [],
                'alt_svc_persist': False,
            },
            'websocket': {'enabled': False, 'compression': 'off'},
            'proxy': {
                'proxy_headers': False,
                'forwarded_allow_ips': [],
                'include_server_header': False,
            },
            'static': {'route': None, 'mount': None},
            'quic': {'early_data_policy': 'deny', 'require_retry': False, 'quic_secret': None},
            'listeners': [
                {
                    'kind': 'tcp',
                    'host': '127.0.0.1',
                    'port': 8000,
                    'http_versions': ['1.1'],
                    'protocols': ['http1'],
                    'websocket': False,
                    'alpn_protocols': ['http/1.1'],
                }
            ],
        },
    ),
    'strict-h1-origin': _profile(
        profile_id='strict-h1-origin',
        extends='default',
        description='Conservative HTTP/1.1 origin posture with explicit host validation, static disabled unless mounted, and no proxy trust by default.',
        claim_ids=['TC-PROFILE-STRICT-H1-ORIGIN'],
        rfc_targets=['RFC 9112', 'RFC 7232', 'RFC 7233'],
        required_overrides=[],
        explicit_posture={
            'protocol_family': 'http1-origin',
            'proxy_trust': 'disabled',
            'connect': 'deny',
            'trusted_proxy_behavior': 'deny_untrusted_forwarded_headers',
            'static_serving': 'disabled_until_mount_configured',
            'early_data': 'not_applicable',
            'http3_quic': 'disabled',
        },
        config={
            'app': {'profile': 'strict-h1-origin'},
            'proxy': {'server_names': ['localhost']},
            'http': {'http1_keep_alive': True},
            'listeners': [
                {
                    'kind': 'tcp',
                    'host': '127.0.0.1',
                    'port': 8000,
                    'http_versions': ['1.1'],
                    'protocols': ['http1'],
                    'websocket': False,
                    'alpn_protocols': ['http/1.1'],
                }
            ],
        },
    ),
    'strict-h2-origin': _profile(
        profile_id='strict-h2-origin',
        extends='strict-h1-origin',
        description='TLS-backed HTTP/2 origin posture with explicit ALPN and h2-only protocol selection.',
        claim_ids=['TC-PROFILE-STRICT-H2-ORIGIN'],
        rfc_targets=['RFC 9113', 'RFC 8446', 'RFC 7301'],
        required_overrides=['tls.certfile', 'tls.keyfile'],
        explicit_posture={
            'protocol_family': 'h2-origin',
            'proxy_trust': 'disabled',
            'connect': 'deny',
            'trusted_proxy_behavior': 'deny_untrusted_forwarded_headers',
            'static_serving': 'disabled_until_mount_configured',
            'early_data': 'not_applicable',
            'http3_quic': 'disabled',
        },
        config={
            'app': {'profile': 'strict-h2-origin'},
            'tls': {'alpn_protocols': ['h2']},
            'http': {
                'http_versions': ['2'],
                'enable_h2c': False,
                'http2_adaptive_window': False,
            },
            'listeners': [
                {
                    'kind': 'tcp',
                    'host': '127.0.0.1',
                    'port': 8443,
                    'http_versions': ['2'],
                    'protocols': ['http2'],
                    'websocket': False,
                    'alpn_protocols': ['h2'],
                }
            ],
        },
    ),
    'strict-h3-edge': _profile(
        profile_id='strict-h3-edge',
        extends='strict-h2-origin',
        description='Dual TCP+UDP edge posture with explicit HTTP/3 and QUIC listeners, automatic Alt-Svc, Retry, and default 0-RTT denial.',
        claim_ids=['TC-PROFILE-STRICT-H3-EDGE'],
        rfc_targets=['RFC 9114', 'RFC 9000', 'RFC 9001', 'RFC 9002', 'RFC 7838 Section 3'],
        required_overrides=['tls.certfile', 'tls.keyfile'],
        explicit_posture={
            'protocol_family': 'h2-h3-edge',
            'proxy_trust': 'disabled',
            'connect': 'deny',
            'trusted_proxy_behavior': 'deny_untrusted_forwarded_headers',
            'static_serving': 'disabled_until_mount_configured',
            'early_data': 'deny',
            'http3_quic': 'enabled',
        },
        config={
            'app': {'profile': 'strict-h3-edge'},
            'tls': {'alpn_protocols': ['h2', 'http/1.1']},
            'http': {
                'http_versions': ['1.1', '2'],
                'alt_svc_auto': True,
                'alt_svc_max_age': 86400,
                'alt_svc_persist': False,
            },
            'quic': {'require_retry': True, 'early_data_policy': 'deny'},
            'listeners': [
                {
                    'kind': 'tcp',
                    'host': '127.0.0.1',
                    'port': 8443,
                    'http_versions': ['1.1', '2'],
                    'protocols': ['http1', 'http2'],
                    'websocket': False,
                    'alpn_protocols': ['h2', 'http/1.1'],
                },
                {
                    'kind': 'udp',
                    'host': '127.0.0.1',
                    'port': 8443,
                    'http_versions': ['3'],
                    'protocols': ['quic', 'http3'],
                    'websocket': False,
                    'alpn_protocols': ['h3'],
                    'quic_require_retry': True,
                    'quic_secret': None,
                },
            ],
        },
    ),
    'strict-mtls-origin': _profile(
        profile_id='strict-mtls-origin',
        extends='strict-h2-origin',
        description='HTTP/2 TLS origin posture with mandatory client certificates and explicit trust-store requirements.',
        claim_ids=['TC-PROFILE-STRICT-MTLS-ORIGIN'],
        rfc_targets=['RFC 8446', 'RFC 5280', 'RFC 7301', 'RFC 9113'],
        required_overrides=['tls.certfile', 'tls.keyfile', 'tls.ca_certs'],
        explicit_posture={
            'protocol_family': 'h2-mtls-origin',
            'proxy_trust': 'disabled',
            'connect': 'deny',
            'trusted_proxy_behavior': 'deny_untrusted_forwarded_headers',
            'static_serving': 'disabled_until_mount_configured',
            'early_data': 'not_applicable',
            'http3_quic': 'disabled',
        },
        config={
            'app': {'profile': 'strict-mtls-origin'},
            'tls': {
                'require_client_cert': True,
                'ocsp_mode': 'soft-fail',
                'crl_mode': 'off',
            },
            'listeners': [
                {
                    'kind': 'tcp',
                    'host': '127.0.0.1',
                    'port': 8443,
                    'http_versions': ['2'],
                    'protocols': ['http2'],
                    'websocket': False,
                    'alpn_protocols': ['h2'],
                    'ssl_require_client_cert': True,
                }
            ],
        },
    ),
    'static-origin': _profile(
        profile_id='static-origin',
        extends='strict-h1-origin',
        description='Static origin posture with explicit mounted delivery, index handling, validators, range support, and no proxy trust by default.',
        claim_ids=['TC-PROFILE-STATIC-ORIGIN'],
        rfc_targets=['RFC 9112', 'RFC 7232', 'RFC 7233', 'RFC 9110 Section 8'],
        required_overrides=['static.mount'],
        explicit_posture={
            'protocol_family': 'http1-static-origin',
            'proxy_trust': 'disabled',
            'connect': 'deny',
            'trusted_proxy_behavior': 'deny_untrusted_forwarded_headers',
            'static_serving': 'enabled_when_mount_present',
            'early_data': 'not_applicable',
            'http3_quic': 'disabled',
        },
        config={
            'app': {'profile': 'static-origin'},
            'static': {
                'route': '/',
                'dir_to_file': True,
                'index_file': 'index.html',
                'expires': 3600,
            },
            'http': {
                'content_coding_policy': 'allowlist',
                'content_codings': ['br', 'gzip', 'deflate'],
            },
        },
    ),
}


def list_blessed_profiles() -> tuple[str, ...]:
    return tuple(_PROFILE_REGISTRY)


def get_profile_spec(profile: str) -> dict[str, Any]:
    try:
        return deepcopy(_PROFILE_REGISTRY[profile])
    except KeyError as exc:
        raise ValueError(f'unknown blessed profile: {profile!r}') from exc


def resolve_profile_spec(profile: str) -> dict[str, Any]:
    spec = get_profile_spec(profile)
    parent = spec.get('extends')
    if not parent:
        return spec
    parent_spec = resolve_profile_spec(parent)
    return {
        'profile_id': spec['profile_id'],
        'extends': spec['extends'],
        'description': spec['description'],
        'claim_ids': [*parent_spec['claim_ids'], *[item for item in spec['claim_ids'] if item not in parent_spec['claim_ids']]],
        'rfc_targets': [*parent_spec['rfc_targets'], *[item for item in spec['rfc_targets'] if item not in parent_spec['rfc_targets']]],
        'required_overrides': [
            *parent_spec['required_overrides'],
            *[item for item in spec['required_overrides'] if item not in parent_spec['required_overrides']],
        ],
        'explicit_posture': merge_config_dicts(parent_spec['explicit_posture'], spec['explicit_posture']),
        'config': merge_config_dicts(parent_spec['config'], spec['config']),
    }


def resolve_profile_config(profile: str) -> dict[str, Any]:
    return deepcopy(resolve_profile_spec(profile)['config'])


def resolve_effective_profile_mapping(profile: str) -> dict[str, Any]:
    defaults_dict = _dataclass_to_dict(default_config())
    profile_dict = resolve_profile_config(profile)
    merged = merge_config_dicts(defaults_dict, profile_dict)
    merged.setdefault('app', {})
    merged['app']['profile'] = profile
    return merged


def resolve_requested_profile(
    *sources: Mapping[str, Any] | None,
    explicit_profile: str | None = None,
) -> str:
    if explicit_profile:
        return explicit_profile.strip().lower()
    selected: str | None = None
    for source in sources:
        if not source:
            continue
        app_block = source.get('app')
        if isinstance(app_block, Mapping):
            candidate = app_block.get('profile')
            if isinstance(candidate, str) and candidate.strip():
                selected = candidate.strip().lower()
    return selected or 'default'
