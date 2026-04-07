from __future__ import annotations

import argparse
import dataclasses
import re
from typing import Any

from .defaults import default_config
from .load import build_config, config_to_dict
from .model import ServerConfig
from .profiles import get_profile_spec, list_blessed_profiles


_RUNTIME_RANDOMIZED = '<runtime-randomized>'
_RUNTIME_RANDOMIZED_PATTERNS = (
    re.compile(r'^listeners\[\d+\]\.quic_secret$'),
)


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, bytes):
        return value.decode('latin1')
    return value


def _sanitize_runtime_audit_values(value: Any, *, prefix: str = '') -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_runtime_audit_values(item, prefix=f'{prefix}.{key}' if prefix else str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _sanitize_runtime_audit_values(item, prefix=f'{prefix}[{index}]')
            for index, item in enumerate(value)
        ]
    if any(pattern.match(prefix) for pattern in _RUNTIME_RANDOMIZED_PATTERNS) and value is not None:
        return _RUNTIME_RANDOMIZED
    return value


def _flatten(value: Any, *, prefix: str = '') -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            child_prefix = f'{prefix}.{key}' if prefix else str(key)
            result.update(_flatten(item, prefix=child_prefix))
        return result
    if isinstance(value, list):
        for index, item in enumerate(value):
            child_prefix = f'{prefix}[{index}]'
            result.update(_flatten(item, prefix=child_prefix))
        if not value and prefix:
            result[prefix] = []
        return result
    result[prefix] = value
    return result


def _diff(before: Any, after: Any) -> Any:
    if isinstance(before, dict) and isinstance(after, dict):
        diff: dict[str, Any] = {}
        for key in sorted(set(before) | set(after)):
            if key not in before:
                diff[key] = {'from': None, 'to': after[key]}
                continue
            if key not in after:
                diff[key] = {'from': before[key], 'to': None}
                continue
            child = _diff(before[key], after[key])
            if child not in ({}, None):
                diff[key] = child
        return diff
    if before != after:
        return {'from': before, 'to': after}
    return {}


def parser_public_defaults() -> list[dict[str, Any]]:
    from tigrcorn.cli import build_parser

    parser = build_parser()
    rows: list[dict[str, Any]] = []
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if action.help == argparse.SUPPRESS:
            continue
        for flag in action.option_strings:
            rows.append(
                {
                    'flag': flag,
                    'dest': action.dest,
                    'parser_default': _jsonable(action.default),
                    'help': action.help,
                    'choices': list(action.choices) if action.choices is not None else None,
                    'required': bool(action.required),
                }
            )
    return rows


def resolve_effective_defaults(profile: str = 'default') -> dict[str, Any]:
    raw_dataclass = _jsonable(dataclasses.asdict(ServerConfig()))
    normalized = _jsonable(config_to_dict(default_config()))
    profile_kwargs: dict[str, Any] = {}
    for item in get_profile_spec(profile).get('required_overrides', []):
        if item == 'tls.certfile':
            profile_kwargs['ssl_certfile'] = 'cert.pem'
        elif item == 'tls.keyfile':
            profile_kwargs['ssl_keyfile'] = 'key.pem'
        elif item == 'tls.ca_certs':
            profile_kwargs['ssl_ca_certs'] = 'ca.pem'
        elif item == 'static.mount':
            profile_kwargs['static_path_mount'] = '/srv/static'
    effective = _sanitize_runtime_audit_values(_jsonable(config_to_dict(build_config(profile=profile, **profile_kwargs))))
    parser_rows = parser_public_defaults()
    base_profile_kwargs: dict[str, Any] = {}
    for item in get_profile_spec('default').get('required_overrides', []):
        if item == 'static.mount':
            base_profile_kwargs['static_path_mount'] = '/srv/static'
    base_effective = _sanitize_runtime_audit_values(_jsonable(config_to_dict(build_config(profile='default', **base_profile_kwargs))))
    return {
        'profile': profile,
        'blessed_profiles': list(list_blessed_profiles()),
        'dataclass_model_defaults': raw_dataclass,
        'dataclass_model_defaults_flat': _flatten(raw_dataclass),
        'cli_parser_defaults': parser_rows,
        'cli_parser_defaults_by_flag': {row['flag']: row['parser_default'] for row in parser_rows},
        'normalization_backfills': _diff(raw_dataclass, normalized),
        'normalization_backfills_flat': _flatten(_diff(raw_dataclass, normalized)),
        'profile_overlays': _diff(base_effective, effective),
        'profile_overlays_flat': _flatten(_diff(base_effective, effective)),
        'effective_defaults': effective,
        'effective_defaults_flat': _flatten(effective),
    }
