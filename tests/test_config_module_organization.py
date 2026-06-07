from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ROOT / "pkgs" / "tigrcorn-config" / "src" / "tigrcorn_config"


def test_tigrcorn_config_python_files_stay_under_400_lines() -> None:
    oversized = []
    for path in CONFIG_ROOT.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 400:
            oversized.append((len(lines), path.relative_to(ROOT).as_posix()))
    assert oversized == []


def test_config_load_public_imports_remain_compatible() -> None:
    from tigrcorn_config.load import (
        build_config,
        build_config_from_namespace,
        build_config_from_sources,
        config_from_mapping,
        config_from_source,
        config_to_dict,
    )
    from tigrcorn.config.load import build_config as root_build_config

    assert root_build_config is build_config
    assert callable(build_config_from_namespace)
    assert callable(build_config_from_sources)
    assert callable(config_from_mapping)
    assert callable(config_from_source)
    assert callable(config_to_dict)


def test_config_model_public_imports_remain_compatible() -> None:
    from tigrcorn_config.model import HTTPConfig, ListenerConfig, ServerConfig, TLSConfig
    from tigrcorn.config.model import ServerConfig as RootServerConfig

    assert RootServerConfig is ServerConfig
    assert ListenerConfig().label == "127.0.0.1:8000"
    assert HTTPConfig().http_versions == ["1.1", "2"]
    assert TLSConfig().alpn_protocols == ["h2", "http/1.1"]


def test_config_responsibility_modules_are_isolated() -> None:
    assert hasattr(importlib.import_module("tigrcorn_config.load.namespace"), "namespace_to_overrides")
    assert hasattr(importlib.import_module("tigrcorn_config.load.listeners"), "listener_overrides_from_namespace")
    assert hasattr(importlib.import_module("tigrcorn_config.model.transports"), "ListenerConfig")
    assert hasattr(importlib.import_module("tigrcorn_config.model.server"), "ServerConfig")


def test_tigrcorn_config_does_not_import_runtime_server_or_transport_packages() -> None:
    banned_prefixes = ("tigrcorn_runtime.server", "tigrcorn_transports")
    offenders: list[tuple[str, str]] = []
    for path in CONFIG_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes):
                        offenders.append((path.relative_to(ROOT).as_posix(), alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(banned_prefixes):
                    offenders.append((path.relative_to(ROOT).as_posix(), node.module))
    assert offenders == []
