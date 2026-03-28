from __future__ import annotations

import dataclasses
import importlib
import json
import runpy
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

try:  # pragma: no cover
    import yaml  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


class ConfigFileError(RuntimeError):
    pass


def _object_to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if callable(value):
        return _object_to_mapping(value())
    if hasattr(value, '__dict__'):
        return {key: item for key, item in vars(value).items() if not key.startswith('_')}
    raise ConfigFileError(f'config object did not resolve to a mapping: {value!r}')


def _extract_python_payload(payload: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    for key in ('CONFIG', 'config', 'TIGRCORN_CONFIG'):
        if key in payload:
            return _object_to_mapping(payload[key])
    raise ConfigFileError(f'{label} did not expose CONFIG/config/TIGRCORN_CONFIG')


def load_config_file(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigFileError(f'config file does not exist: {config_path}')
    suffix = config_path.suffix.lower()
    if suffix == '.json':
        return json.loads(config_path.read_text(encoding='utf-8'))
    if suffix in {'.yaml', '.yml'}:
        if yaml is None:
            raise ConfigFileError(
                'YAML loading is unavailable on this Python runtime; '
                'install tigrcorn[config-yaml] to enable .yaml/.yml config files'
            )
        loaded = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        return _object_to_mapping(loaded or {})
    if suffix == '.toml':
        if tomllib is None:
            raise ConfigFileError('TOML loading is unavailable on this Python runtime')
        return tomllib.loads(config_path.read_text(encoding='utf-8'))
    if suffix == '.py':
        payload = runpy.run_path(str(config_path))
        return _extract_python_payload(payload, label=f'python config {config_path}')
    raise ConfigFileError(f'unsupported config file type: {config_path.suffix!r}')


def load_config_module(module_name: str) -> dict[str, Any]:
    module = importlib.import_module(module_name)
    return _extract_python_payload(vars(module), label=f'config module {module_name}')


def load_config_object(spec: str) -> dict[str, Any]:
    if ':' not in spec:
        raise ConfigFileError('object config references must use module:object syntax')
    module_name, object_name = spec.split(':', 1)
    module = importlib.import_module(module_name)
    if not hasattr(module, object_name):
        raise ConfigFileError(f'config object {spec!r} was not found')
    value = getattr(module, object_name)
    return _object_to_mapping(value)


def load_config_source(source: str | Path | Mapping[str, Any] | Any | None) -> dict[str, Any]:
    if source is None:
        return {}
    if isinstance(source, Mapping):
        return dict(source)
    if dataclasses.is_dataclass(source):
        return dataclasses.asdict(source)
    if isinstance(source, Path):
        return load_config_file(source)
    if isinstance(source, str):
        candidate = Path(source)
        if candidate.exists():
            return load_config_file(candidate)
        if source.startswith('module:'):
            return load_config_module(source.split(':', 1)[1])
        if source.startswith('object:'):
            return load_config_object(source.split(':', 1)[1])
        raise ConfigFileError(
            'config source must be a file path or module:/object: reference '
            f'(got {source!r})'
        )
    return _object_to_mapping(source)
