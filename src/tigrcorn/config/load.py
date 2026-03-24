from __future__ import annotations

import dataclasses
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

from tigrcorn.constants import DEFAULT_ENV_PREFIX, DEFAULT_HOST, DEFAULT_PORT

from .defaults import default_config
from .env import load_env_config
from .files import load_config_file
from .merge import merge_config_dicts
from .model import ListenerConfig, ServerConfig
from .normalize import normalize_config
from .validate import validate_config


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
        elif dataclasses.is_dataclass(current) and isinstance(value, Mapping):
            _apply_mapping(current, value)
        else:
            setattr(target, key, value)


def config_from_mapping(data: Mapping[str, Any]) -> ServerConfig:
    config = default_config()
    _apply_mapping(config, data)
    normalize_config(config)
    validate_config(config)
    return config


def _parse_bind(value: str, *, kind: str) -> dict[str, Any]:
    if value.startswith("fd://"):
        return {"kind": kind, "fd": int(value.removeprefix("fd://"))}
    if value.startswith("unix:"):
        return {"kind": "unix", "path": value.split(":", 1)[1]}
    if value.startswith("udp://"):
        kind = "udp"
        value = value.removeprefix("udp://")
    elif value.startswith("tcp://"):
        kind = "tcp"
        value = value.removeprefix("tcp://")
    elif value.startswith("quic://"):
        kind = "udp"
        value = value.removeprefix("quic://")
    if value.startswith("[") and "]:" in value:
        host, port = value.rsplit(":", 1)
        host = host[1:-1]
    elif ":" in value:
        host, port = value.rsplit(":", 1)
    else:
        host, port = DEFAULT_HOST, value
    return {"kind": kind, "host": host, "port": int(port)}


def _listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[Any] = []
        for item in value:
            if isinstance(item, str) and "," in item:
                result.extend(part.strip() for part in item.split(",") if part.strip())
            else:
                result.append(item)
        return result
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _listener_overrides_from_namespace(ns: Namespace) -> list[dict[str, Any]] | None:
    listeners: list[dict[str, Any]] = []
    bind_entries = list(ns.bind or [])
    quic_bind_entries = list(ns.quic_bind or [])
    insecure_bind_entries = list(ns.insecure_bind or [])
    fd_entries = list(ns.fd or [])
    endpoint_entries = list(ns.endpoint or [])

    for item in bind_entries:
        listeners.append(_parse_bind(item, kind="tcp"))
    for item in quic_bind_entries:
        listener = _parse_bind(item, kind="udp")
        listener["quic_bind"] = item
        listeners.append(listener)
    for item in insecure_bind_entries:
        listener = _parse_bind(item, kind="tcp")
        listener["insecure_bind"] = item
        listeners.append(listener)
    for item in fd_entries:
        listeners.append({"kind": ns.transport or "tcp", "fd": int(item)})
    for item in endpoint_entries:
        listeners.append({"kind": ns.transport or "tcp", "endpoint": item})

    if not listeners:
        if ns.uds:
            kind = "pipe" if ns.transport == "pipe" else "unix"
            listeners.append({"kind": kind, "path": ns.uds})
        else:
            listeners.append({"kind": ns.transport or "tcp", "host": ns.host or DEFAULT_HOST, "port": ns.port or DEFAULT_PORT})

    for listener in listeners:
        if ns.backlog is not None:
            listener["backlog"] = ns.backlog
        if ns.reuse_port is not None:
            listener["reuse_port"] = ns.reuse_port
        if ns.reuse_address is not None:
            listener["reuse_address"] = ns.reuse_address
        if ns.pipe_mode is not None and listener.get("kind") == "pipe":
            listener["pipe_mode"] = ns.pipe_mode
        if ns.http_versions:
            listener["http_versions"] = list(ns.http_versions)
        if ns.protocols:
            listener["protocols"] = list(ns.protocols)
        if ns.disable_websocket is not None:
            listener["websocket"] = not ns.disable_websocket
        if ns.ssl_certfile is not None and not listener.get("insecure_bind"):
            listener["ssl_certfile"] = ns.ssl_certfile
        if ns.ssl_keyfile is not None and not listener.get("insecure_bind"):
            listener["ssl_keyfile"] = ns.ssl_keyfile
        if ns.ssl_ca_certs is not None and not listener.get("insecure_bind"):
            listener["ssl_ca_certs"] = ns.ssl_ca_certs
        if ns.ssl_require_client_cert is not None and not listener.get("insecure_bind"):
            listener["ssl_require_client_cert"] = ns.ssl_require_client_cert
        if ns.ssl_alpn:
            listener["alpn_protocols"] = _listify(ns.ssl_alpn)
        if getattr(ns, 'ssl_ocsp_mode', None) is not None:
            listener['ocsp_mode'] = ns.ssl_ocsp_mode
        if getattr(ns, 'ssl_ocsp_soft_fail', None) is not None:
            listener['ocsp_soft_fail'] = ns.ssl_ocsp_soft_fail
        if getattr(ns, 'ssl_ocsp_cache_size', None) is not None:
            listener['ocsp_cache_size'] = ns.ssl_ocsp_cache_size
        if getattr(ns, 'ssl_ocsp_max_age', None) is not None:
            listener['ocsp_max_age'] = ns.ssl_ocsp_max_age
        if getattr(ns, 'ssl_crl_mode', None) is not None:
            listener['crl_mode'] = ns.ssl_crl_mode
        if getattr(ns, 'ssl_revocation_fetch', None) is not None:
            listener['revocation_fetch'] = ns.ssl_revocation_fetch == 'on' if isinstance(ns.ssl_revocation_fetch, str) else bool(ns.ssl_revocation_fetch)
        if ns.quic_require_retry is not None and listener.get("kind") == "udp":
            listener["quic_require_retry"] = ns.quic_require_retry
        if ns.quic_max_datagram_size is not None and listener.get("kind") == "udp":
            listener["max_datagram_size"] = ns.quic_max_datagram_size
        if ns.quic_secret is not None and listener.get("kind") == "udp":
            listener["quic_secret"] = ns.quic_secret.encode("utf-8") if isinstance(ns.quic_secret, str) else ns.quic_secret
    return listeners


def namespace_to_overrides(ns: Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    app_block: dict[str, Any] = {}
    process_block: dict[str, Any] = {}
    tls_block: dict[str, Any] = {}
    proxy_block: dict[str, Any] = {}
    http_block: dict[str, Any] = {}
    websocket_block: dict[str, Any] = {}
    quic_block: dict[str, Any] = {}
    logging_block: dict[str, Any] = {}
    metrics_block: dict[str, Any] = {}
    scheduler_block: dict[str, Any] = {}

    if ns.app is not None:
        app_block["target"] = ns.app
    for key, dest in (("factory", "factory"), ("app_dir", "app_dir"), ("lifespan", "lifespan"), ("reload", "reload"), ("config", "config_file"), ("env_prefix", "env_prefix")):
        value = getattr(ns, key, None)
        if value is not None:
            app_block[dest] = value
    if ns.reload_dir:
        app_block["reload_dirs"] = list(ns.reload_dir)
    if ns.reload_include:
        app_block["reload_include"] = list(ns.reload_include)
    if ns.reload_exclude:
        app_block["reload_exclude"] = list(ns.reload_exclude)

    logging_explicit_fields: list[str] = []

    mapping = {
        "workers": (process_block, "workers"),
        "worker_class": (process_block, "worker_class"),
        "pid": (process_block, "pid_file"),
        "limit_max_requests": (process_block, "limit_max_requests"),
        "max_requests_jitter": (process_block, "max_requests_jitter"),
        "ssl_certfile": (tls_block, "certfile"),
        "ssl_keyfile": (tls_block, "keyfile"),
        "ssl_ca_certs": (tls_block, "ca_certs"),
        "ssl_require_client_cert": (tls_block, "require_client_cert"),
        "ssl_ciphers": (tls_block, "ciphers"),
        "ssl_ocsp_mode": (tls_block, "ocsp_mode"),
        "ssl_ocsp_soft_fail": (tls_block, "ocsp_soft_fail"),
        "ssl_ocsp_cache_size": (tls_block, "ocsp_cache_size"),
        "ssl_ocsp_max_age": (tls_block, "ocsp_max_age"),
        "ssl_crl_mode": (tls_block, "crl_mode"),
        "proxy_headers": (proxy_block, "proxy_headers"),
        "root_path": (proxy_block, "root_path"),
        "timeout_keep_alive": (http_block, "keep_alive_timeout"),
        "read_timeout": (http_block, "read_timeout"),
        "write_timeout": (http_block, "write_timeout"),
        "timeout_graceful_shutdown": (http_block, "shutdown_timeout"),
        "idle_timeout": (http_block, "idle_timeout"),
        "max_body_size": (http_block, "max_body_size"),
        "max_header_size": (http_block, "max_header_size"),
        "connect_policy": (http_block, "connect_policy"),
        "trailer_policy": (http_block, "trailer_policy"),
        "content_coding_policy": (http_block, "content_coding_policy"),
        "websocket_max_message_size": (websocket_block, "max_message_size"),
        "websocket_ping_interval": (websocket_block, "ping_interval"),
        "websocket_ping_timeout": (websocket_block, "ping_timeout"),
        "websocket_compression": (websocket_block, "compression"),
        "quic_require_retry": (quic_block, "require_retry"),
        "quic_max_datagram_size": (quic_block, "max_datagram_size"),
        "quic_idle_timeout": (quic_block, "idle_timeout"),
        "quic_early_data_policy": (quic_block, "early_data_policy"),
        "log_level": (logging_block, "level"),
        "access_log": (logging_block, "access_log"),
        "access_log_file": (logging_block, "access_log_file"),
        "access_log_format": (logging_block, "access_log_format"),
        "error_log_file": (logging_block, "error_log_file"),
        "log_config": (logging_block, "log_config"),
        "structured_log": (logging_block, "structured"),
        "metrics": (metrics_block, "enabled"),
        "metrics_bind": (metrics_block, "bind"),
        "statsd_host": (metrics_block, "statsd_host"),
        "otel_endpoint": (metrics_block, "otel_endpoint"),
        "limit_concurrency": (scheduler_block, "limit_concurrency"),
        "max_connections": (scheduler_block, "max_connections"),
        "max_tasks": (scheduler_block, "max_tasks"),
        "max_streams": (scheduler_block, "max_streams"),
    }
    for key, (block, dest) in mapping.items():
        value = getattr(ns, key, None)
        if value is not None:
            block[dest] = value
            if block is logging_block and dest in {"level", "access_log", "access_log_file", "access_log_format", "error_log_file", "structured", "log_config"}:
                logging_explicit_fields.append(dest)

    if ns.ssl_alpn:
        tls_block["alpn_protocols"] = _listify(ns.ssl_alpn)
    if ns.log_config is not None:
        logging_explicit_fields.append("log_config")
    if getattr(ns, 'ssl_revocation_fetch', None) is not None:
        tls_block['revocation_fetch'] = ns.ssl_revocation_fetch == 'on' if isinstance(ns.ssl_revocation_fetch, str) else bool(ns.ssl_revocation_fetch)
    if ns.forwarded_allow_ips:
        proxy_block["forwarded_allow_ips"] = _listify(ns.forwarded_allow_ips)
    if ns.server_header is not None:
        proxy_block["server_header"] = ns.server_header
        proxy_block["include_server_header"] = True
    if ns.no_server_header:
        proxy_block["include_server_header"] = False
        proxy_block["server_header"] = ""
    if ns.http_versions:
        http_block["http_versions"] = list(ns.http_versions)
    if ns.content_codings:
        http_block["content_codings"] = _listify(ns.content_codings)
    if getattr(ns, 'connect_allow', None):
        http_block['connect_allow'] = _listify(ns.connect_allow)
    if ns.disable_h2c is not None:
        http_block["enable_h2c"] = not ns.disable_h2c
    if ns.disable_websocket is not None:
        websocket_block["enabled"] = not ns.disable_websocket
    if ns.quic_secret is not None:
        quic_block["quic_secret"] = ns.quic_secret.encode("utf-8") if isinstance(ns.quic_secret, str) else ns.quic_secret

    listeners = _listener_overrides_from_namespace(ns)
    if listeners:
        overrides["listeners"] = listeners
    if logging_explicit_fields:
        logging_block["explicit_fields"] = sorted(set(logging_explicit_fields))

    for name, block in (
        ("app", app_block),
        ("process", process_block),
        ("tls", tls_block),
        ("proxy", proxy_block),
        ("http", http_block),
        ("websocket", websocket_block),
        ("quic", quic_block),
        ("logging", logging_block),
        ("metrics", metrics_block),
        ("scheduler", scheduler_block),
    ):
        if block:
            overrides[name] = block
    return overrides


def build_config_from_sources(*, cli_overrides: Mapping[str, Any] | None = None, config_path: str | Path | None = None, env_prefix: str | None = None) -> ServerConfig:
    defaults_dict = config_to_dict(default_config())
    file_dict = load_config_file(config_path)
    prefix = env_prefix or DEFAULT_ENV_PREFIX
    env_dict = load_env_config(prefix)
    merged = merge_config_dicts(defaults_dict, file_dict, env_dict, cli_overrides)
    return config_from_mapping(merged)


def build_config_from_namespace(ns: Namespace) -> ServerConfig:
    cli_overrides = namespace_to_overrides(ns)
    config_path = getattr(ns, "config", None)
    env_prefix = getattr(ns, "env_prefix", None) or DEFAULT_ENV_PREFIX
    return build_config_from_sources(cli_overrides=cli_overrides, config_path=config_path, env_prefix=env_prefix)


def build_config(
    *,
    app: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    uds: str | None = None,
    transport: str = "tcp",
    lifespan: str = "auto",
    log_level: str = "info",
    access_log: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ssl_ca_certs: str | None = None,
    ssl_require_client_cert: bool = False,
    ssl_ciphers: str | None = None,
    http_versions: list[str] | None = None,
    websocket: bool = True,
    enable_h2c: bool = True,
    max_body_size: int | None = None,
    protocols: list[str] | None = None,
    quic_secret: bytes | None = None,
    quic_require_retry: bool = False,
    pipe_mode: str = "rawframed",
    config: Mapping[str, Any] | None = None,
) -> ServerConfig:
    overrides: dict[str, Any] = {
        "app": {"target": app, "lifespan": lifespan},
        "logging": {"level": log_level, "access_log": access_log},
        "http": {"enable_h2c": enable_h2c},
        "websocket": {"enabled": websocket},
        "quic": {"require_retry": quic_require_retry},
        "tls": {
            "certfile": ssl_certfile,
            "keyfile": ssl_keyfile,
            "ca_certs": ssl_ca_certs,
            "require_client_cert": ssl_require_client_cert,
            "ciphers": ssl_ciphers,
        },
        "listeners": [
            {
                "kind": "unix" if uds and transport == "tcp" else transport.lower(),
                "host": host,
                "port": port,
                "path": uds,
                "ssl_certfile": ssl_certfile,
                "ssl_keyfile": ssl_keyfile,
                "ssl_ca_certs": ssl_ca_certs,
                "ssl_require_client_cert": ssl_require_client_cert,
                "ssl_ciphers": ssl_ciphers,
                "http_versions": list(http_versions) if http_versions is not None else None,
                "websocket": websocket,
                "protocols": list(protocols) if protocols is not None else None,
                "quic_secret": quic_secret,
                "quic_require_retry": quic_require_retry,
                "pipe_mode": pipe_mode,
            }
        ],
    }
    if max_body_size is not None:
        overrides.setdefault("http", {})["max_body_size"] = max_body_size
    if quic_secret is not None:
        overrides.setdefault("quic", {})["quic_secret"] = quic_secret
    merged = merge_config_dicts(config or {}, overrides)
    return config_from_mapping(merged)
