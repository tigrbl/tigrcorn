from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Mapping

from tigrcorn_config.defaults import default_config
from tigrcorn_config.files import load_config_source
from tigrcorn_config.merge import merge_config_dicts
from tigrcorn_config.model import CongestionControlConfig, ListenerConfig, ServerConfig
from tigrcorn_config.normalize import normalize_config
from tigrcorn_config.profiles import resolve_effective_profile_mapping, resolve_requested_profile
from tigrcorn_config.validate import validate_config


def _dataclass_to_dict(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: _dataclass_to_dict(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, list):
        return [_dataclass_to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [_dataclass_to_dict(item) for item in value]
    return value


def config_to_dict(config: ServerConfig) -> dict[str, Any]:
    return _dataclass_to_dict(config)


def _apply_mapping(target: Any, data: Mapping[str, Any]) -> None:
    for key, value in data.items():
        if not hasattr(target, key):
            continue
        current = getattr(target, key)
        if isinstance(current, list) and key == "listeners" and isinstance(value, list):
            listeners: list[ListenerConfig] = []
            for entry in value:
                if isinstance(entry, Mapping):
                    listener = ListenerConfig()
                    _apply_mapping(listener, entry)
                    listeners.append(listener)
            setattr(target, key, listeners)
        elif key == "congestion_control" and isinstance(value, Mapping):
            congestion_control = CongestionControlConfig()
            _apply_mapping(congestion_control, value)
            setattr(target, key, congestion_control)
        elif dataclasses.is_dataclass(current) and isinstance(value, Mapping):
            _apply_mapping(current, value)
        else:
            setattr(target, key, value)


def config_from_mapping(data: Mapping[str, Any]) -> ServerConfig:
    profile_name = resolve_requested_profile(data)
    effective_mapping = merge_config_dicts(resolve_effective_profile_mapping(profile_name), data)
    config = default_config()
    _apply_mapping(config, effective_mapping)
    normalize_config(config)
    validate_config(config)
    return config


def config_from_source(source: str | Path | Mapping[str, Any] | Any | None) -> ServerConfig:
    return config_from_mapping(load_config_source(source))
