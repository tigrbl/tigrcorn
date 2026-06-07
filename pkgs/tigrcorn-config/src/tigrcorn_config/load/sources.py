from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

from tigrcorn_core.constants import DEFAULT_ENV_PREFIX
from tigrcorn_config.env import load_env_config, load_env_file
from tigrcorn_config.files import load_config_source
from tigrcorn_config.merge import merge_config_dicts
from tigrcorn_config.model import ServerConfig
from tigrcorn_config.profiles import resolve_effective_profile_mapping, resolve_requested_profile

from .helpers import mapping_get
from .mapping import config_from_mapping
from .namespace import namespace_to_overrides


def build_config_from_sources(
    *,
    cli_overrides: Mapping[str, Any] | None = None,
    config_source: str | Path | Mapping[str, Any] | Any | None = None,
    config_path: str | Path | None = None,
    env_prefix: str | None = None,
    env_file: str | Path | None = None,
    profile: str | None = None,
) -> ServerConfig:
    source = config_source if config_source is not None else config_path
    file_dict = load_config_source(source)
    prefix = env_prefix or mapping_get(file_dict, "app", "env_prefix") or DEFAULT_ENV_PREFIX
    resolved_env_file = env_file or mapping_get(file_dict, "app", "env_file")
    env_file_vars = load_env_file(resolved_env_file)
    env_file_dict = load_env_config(prefix, environ=env_file_vars) if env_file_vars else {}
    env_dict = load_env_config(prefix)
    profile_name = resolve_requested_profile(file_dict, env_file_dict, env_dict, cli_overrides, explicit_profile=profile)
    merged = merge_config_dicts(resolve_effective_profile_mapping(profile_name), file_dict, env_file_dict, env_dict, cli_overrides)
    merged.setdefault("app", {})
    merged["app"]["profile"] = profile_name
    return config_from_mapping(merged)


def build_config_from_namespace(ns: Namespace) -> ServerConfig:
    cli_overrides = namespace_to_overrides(ns)
    config_source = getattr(ns, "config", None)
    env_prefix = getattr(ns, "env_prefix", None)
    env_file = getattr(ns, "env_file", None)
    return build_config_from_sources(cli_overrides=cli_overrides, config_source=config_source, env_prefix=env_prefix, env_file=env_file)
