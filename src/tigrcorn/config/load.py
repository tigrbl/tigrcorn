from __future__ import annotations

import dataclasses
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

from tigrcorn.constants import DEFAULT_ENV_PREFIX, DEFAULT_HOST, DEFAULT_PORT

from .defaults import default_config
from .env import load_env_config, load_env_file
from .files import load_config_source
from .merge import merge_config_dicts
from .model import ListenerConfig, ServerConfig
from .normalize import normalize_config
from .profiles import resolve_effective_profile_mapping, resolve_requested_profile
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
        if isinstance(current, list) and key == 'listeners' and isinstance(value, list):
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
    profile_name = resolve_requested_profile(data)
    effective_mapping = merge_config_dicts(resolve_effective_profile_mapping(profile_name), data)
    config = default_config()
    _apply_mapping(config, effective_mapping)
    normalize_config(config)
    validate_config(config)
    return config


def config_from_source(source: str | Path | Mapping[str, Any] | Any | None) -> ServerConfig:
    return config_from_mapping(load_config_source(source))


def _parse_bind(value: str, *, kind: str) -> dict[str, Any]:
    if value.startswith('fd://'):
        return {'kind': kind, 'fd': int(value.removeprefix('fd://'))}
    if value.startswith('unix:'):
        return {'kind': 'unix', 'path': value.split(':', 1)[1]}
    if value.startswith('udp://'):
        kind = 'udp'
        value = value.removeprefix('udp://')
    elif value.startswith('tcp://'):
        kind = 'tcp'
        value = value.removeprefix('tcp://')
    elif value.startswith('quic://'):
        kind = 'udp'
        value = value.removeprefix('quic://')
    if value.startswith('[') and ']:' in value:
        host, port = value.rsplit(':', 1)
        host = host[1:-1]
    elif ':' in value:
        host, port = value.rsplit(':', 1)
    else:
        host, port = DEFAULT_HOST, value
    return {'kind': kind, 'host': host, 'port': int(port)}


def _listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[Any] = []
        for item in value:
            if isinstance(item, str) and ',' in item:
                result.extend(part.strip() for part in item.split(',') if part.strip())
            else:
                result.append(item)
        return result
    if isinstance(value, str):
        return [part.strip() for part in value.split(',') if part.strip()]
    return [value]


def _listener_overrides_from_namespace(ns: Namespace) -> list[dict[str, Any]] | None:
    listeners: list[dict[str, Any]] = []
    bind_entries = list(ns.bind or [])
    quic_bind_entries = list(ns.quic_bind or [])
    insecure_bind_entries = list(ns.insecure_bind or [])
    fd_entries = list(ns.fd or [])
    endpoint_entries = list(ns.endpoint or [])

    for item in bind_entries:
        listeners.append(_parse_bind(item, kind='tcp'))
    for item in quic_bind_entries:
        listener = _parse_bind(item, kind='udp')
        listener['quic_bind'] = item
        listeners.append(listener)
    for item in insecure_bind_entries:
        listener = _parse_bind(item, kind='tcp')
        listener['insecure_bind'] = item
        listeners.append(listener)
    for item in fd_entries:
        listeners.append({'kind': ns.transport or 'tcp', 'fd': int(item)})
    for item in endpoint_entries:
        listeners.append({'kind': ns.transport or 'tcp', 'endpoint': item})

    if not listeners:
        if ns.uds:
            kind = 'pipe' if ns.transport == 'pipe' else 'unix'
            listeners.append({'kind': kind, 'path': ns.uds})
        else:
            listeners.append({'kind': ns.transport or 'tcp', 'host': ns.host or DEFAULT_HOST, 'port': ns.port or DEFAULT_PORT})

    for listener in listeners:
        if ns.backlog is not None:
            listener['backlog'] = ns.backlog
        if ns.reuse_port is not None:
            listener['reuse_port'] = ns.reuse_port
        if ns.reuse_address is not None:
            listener['reuse_address'] = ns.reuse_address
        if ns.pipe_mode is not None and listener.get('kind') == 'pipe':
            listener['pipe_mode'] = ns.pipe_mode
        if ns.user is not None and listener.get('kind') == 'unix':
            listener['user'] = ns.user
        if ns.group is not None and listener.get('kind') == 'unix':
            listener['group'] = ns.group
        if ns.umask is not None and listener.get('kind') == 'unix':
            listener['umask'] = ns.umask
        if ns.http_versions:
            listener['http_versions'] = list(ns.http_versions)
        if ns.protocols:
            listener['protocols'] = list(ns.protocols)
        if ns.disable_websocket is not None:
            listener['websocket'] = not ns.disable_websocket
        if ns.ssl_certfile is not None and not listener.get('insecure_bind'):
            listener['ssl_certfile'] = ns.ssl_certfile
        if ns.ssl_keyfile is not None and not listener.get('insecure_bind'):
            listener['ssl_keyfile'] = ns.ssl_keyfile
        if getattr(ns, 'ssl_keyfile_password', None) is not None and not listener.get('insecure_bind'):
            listener['ssl_keyfile_password'] = ns.ssl_keyfile_password
        if ns.ssl_ca_certs is not None and not listener.get('insecure_bind'):
            listener['ssl_ca_certs'] = ns.ssl_ca_certs
        if ns.ssl_require_client_cert is not None and not listener.get('insecure_bind'):
            listener['ssl_require_client_cert'] = ns.ssl_require_client_cert
        if ns.ssl_alpn:
            listener['alpn_protocols'] = _listify(ns.ssl_alpn)
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
        if getattr(ns, 'ssl_crl', None) is not None:
            listener['ssl_crl'] = ns.ssl_crl
        if getattr(ns, 'ssl_revocation_fetch', None) is not None:
            listener['revocation_fetch'] = ns.ssl_revocation_fetch == 'on' if isinstance(ns.ssl_revocation_fetch, str) else bool(ns.ssl_revocation_fetch)
        if ns.quic_require_retry is not None and listener.get('kind') == 'udp':
            listener['quic_require_retry'] = ns.quic_require_retry
        if ns.quic_max_datagram_size is not None and listener.get('kind') == 'udp':
            listener['max_datagram_size'] = ns.quic_max_datagram_size
        if ns.quic_secret is not None and listener.get('kind') == 'udp':
            listener['quic_secret'] = ns.quic_secret.encode('utf-8') if isinstance(ns.quic_secret, str) else ns.quic_secret
    return listeners


def namespace_to_overrides(ns: Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    app_block: dict[str, Any] = {}
    process_block: dict[str, Any] = {}
    tls_block: dict[str, Any] = {}
    proxy_block: dict[str, Any] = {}
    http_block: dict[str, Any] = {}
    websocket_block: dict[str, Any] = {}
    static_block: dict[str, Any] = {}
    quic_block: dict[str, Any] = {}
    webtransport_block: dict[str, Any] = {}
    logging_block: dict[str, Any] = {}
    metrics_block: dict[str, Any] = {}
    scheduler_block: dict[str, Any] = {}

    if ns.app is not None:
        app_block['target'] = ns.app
    for key, dest in (
        ('factory', 'factory'),
        ('app_interface', 'interface'),
        ('app_dir', 'app_dir'),
        ('lifespan', 'lifespan'),
        ('reload', 'reload'),
        ('config', 'config_file'),
        ('env_prefix', 'env_prefix'),
        ('env_file', 'env_file'),
    ):
        value = getattr(ns, key, None)
        if value is not None:
            app_block[dest] = value
    if ns.reload_dir:
        app_block['reload_dirs'] = list(ns.reload_dir)
    if ns.reload_include:
        app_block['reload_include'] = list(ns.reload_include)
    if ns.reload_exclude:
        app_block['reload_exclude'] = list(ns.reload_exclude)

    logging_explicit_fields: list[str] = []

    mapping = {
        'workers': (process_block, 'workers'),
        'worker_class': (process_block, 'worker_class'),
        'runtime': (process_block, 'runtime'),
        'pid': (process_block, 'pid_file'),
        'worker_healthcheck_timeout': (process_block, 'worker_healthcheck_timeout'),
        'limit_max_requests': (process_block, 'limit_max_requests'),
        'max_requests_jitter': (process_block, 'max_requests_jitter'),
        'ssl_certfile': (tls_block, 'certfile'),
        'ssl_keyfile': (tls_block, 'keyfile'),
        'ssl_keyfile_password': (tls_block, 'keyfile_password'),
        'ssl_ca_certs': (tls_block, 'ca_certs'),
        'ssl_require_client_cert': (tls_block, 'require_client_cert'),
        'ssl_ciphers': (tls_block, 'ciphers'),
        'ssl_ocsp_mode': (tls_block, 'ocsp_mode'),
        'ssl_ocsp_soft_fail': (tls_block, 'ocsp_soft_fail'),
        'ssl_ocsp_cache_size': (tls_block, 'ocsp_cache_size'),
        'ssl_ocsp_max_age': (tls_block, 'ocsp_max_age'),
        'ssl_crl_mode': (tls_block, 'crl_mode'),
        'ssl_crl': (tls_block, 'crl'),
        'proxy_headers': (proxy_block, 'proxy_headers'),
        'root_path': (proxy_block, 'root_path'),
        'timeout_keep_alive': (http_block, 'keep_alive_timeout'),
        'read_timeout': (http_block, 'read_timeout'),
        'write_timeout': (http_block, 'write_timeout'),
        'timeout_graceful_shutdown': (http_block, 'shutdown_timeout'),
        'idle_timeout': (http_block, 'idle_timeout'),
        'max_body_size': (http_block, 'max_body_size'),
        'max_header_size': (http_block, 'max_header_size'),
        'http1_max_incomplete_event_size': (http_block, 'http1_max_incomplete_event_size'),
        'http1_buffer_size': (http_block, 'http1_buffer_size'),
        'http1_header_read_timeout': (http_block, 'http1_header_read_timeout'),
        'http1_keep_alive': (http_block, 'http1_keep_alive'),
        'http2_max_concurrent_streams': (http_block, 'http2_max_concurrent_streams'),
        'http2_max_headers_size': (http_block, 'http2_max_headers_size'),
        'http2_max_frame_size': (http_block, 'http2_max_frame_size'),
        'http2_adaptive_window': (http_block, 'http2_adaptive_window'),
        'http2_initial_connection_window_size': (http_block, 'http2_initial_connection_window_size'),
        'http2_initial_stream_window_size': (http_block, 'http2_initial_stream_window_size'),
        'http2_keep_alive_interval': (http_block, 'http2_keep_alive_interval'),
        'http2_keep_alive_timeout': (http_block, 'http2_keep_alive_timeout'),
        'connect_policy': (http_block, 'connect_policy'),
        'trailer_policy': (http_block, 'trailer_policy'),
        'content_coding_policy': (http_block, 'content_coding_policy'),
        'alt_svc_auto': (http_block, 'alt_svc_auto'),
        'alt_svc_ma': (http_block, 'alt_svc_max_age'),
        'alt_svc_persist': (http_block, 'alt_svc_persist'),
        'websocket_max_message_size': (websocket_block, 'max_message_size'),
        'websocket_max_queue': (websocket_block, 'max_queue'),
        'websocket_ping_interval': (websocket_block, 'ping_interval'),
        'websocket_ping_timeout': (websocket_block, 'ping_timeout'),
        'websocket_compression': (websocket_block, 'compression'),
        'static_path_route': (static_block, 'route'),
        'static_path_mount': (static_block, 'mount'),
        'static_path_dir_to_file': (static_block, 'dir_to_file'),
        'static_path_index_file': (static_block, 'index_file'),
        'static_path_expires': (static_block, 'expires'),
        'quic_require_retry': (quic_block, 'require_retry'),
        'quic_max_datagram_size': (quic_block, 'max_datagram_size'),
        'quic_idle_timeout': (quic_block, 'idle_timeout'),
        'quic_early_data_policy': (quic_block, 'early_data_policy'),
        'webtransport_max_sessions': (webtransport_block, 'max_sessions'),
        'webtransport_max_streams': (webtransport_block, 'max_streams'),
        'webtransport_max_datagram_size': (webtransport_block, 'max_datagram_size'),
        'webtransport_path': (webtransport_block, 'path'),
        'log_level': (logging_block, 'level'),
        'access_log': (logging_block, 'access_log'),
        'access_log_file': (logging_block, 'access_log_file'),
        'access_log_format': (logging_block, 'access_log_format'),
        'error_log_file': (logging_block, 'error_log_file'),
        'log_config': (logging_block, 'log_config'),
        'structured_log': (logging_block, 'structured'),
        'use_colors': (logging_block, 'use_colors'),
        'metrics': (metrics_block, 'enabled'),
        'metrics_bind': (metrics_block, 'bind'),
        'statsd_host': (metrics_block, 'statsd_host'),
        'otel_endpoint': (metrics_block, 'otel_endpoint'),
        'limit_concurrency': (scheduler_block, 'limit_concurrency'),
        'max_connections': (scheduler_block, 'max_connections'),
        'max_tasks': (scheduler_block, 'max_tasks'),
        'max_streams': (scheduler_block, 'max_streams'),
    }
    for key, (block, dest) in mapping.items():
        value = getattr(ns, key, None)
        if value is not None:
            block[dest] = value
            if block is logging_block and dest in {'level', 'access_log', 'access_log_file', 'access_log_format', 'error_log_file', 'structured', 'use_colors', 'log_config'}:
                logging_explicit_fields.append(dest)

    if ns.ssl_alpn:
        tls_block['alpn_protocols'] = _listify(ns.ssl_alpn)
    if ns.log_config is not None:
        logging_explicit_fields.append('log_config')
    if getattr(ns, 'ssl_revocation_fetch', None) is not None:
        tls_block['revocation_fetch'] = ns.ssl_revocation_fetch == 'on' if isinstance(ns.ssl_revocation_fetch, str) else bool(ns.ssl_revocation_fetch)
    if ns.forwarded_allow_ips:
        proxy_block['forwarded_allow_ips'] = _listify(ns.forwarded_allow_ips)
    if ns.server_header is not None:
        proxy_block['server_header'] = ns.server_header
        proxy_block['include_server_header'] = True
    if ns.no_server_header:
        proxy_block['include_server_header'] = False
        proxy_block['server_header'] = ''
    if ns.date_header is not None:
        proxy_block['include_date_header'] = ns.date_header
    if ns.headers:
        proxy_block['default_headers'] = list(ns.headers)
    if ns.server_name:
        proxy_block['server_names'] = _listify(ns.server_name)
    if ns.http_versions:
        http_block['http_versions'] = list(ns.http_versions)
    if getattr(ns, 'alt_svc', None):
        http_block['alt_svc_headers'] = _listify(ns.alt_svc)
    if ns.content_codings:
        http_block['content_codings'] = _listify(ns.content_codings)
    if getattr(ns, 'connect_allow', None):
        http_block['connect_allow'] = _listify(ns.connect_allow)
    if ns.disable_h2c is not None:
        http_block['enable_h2c'] = not ns.disable_h2c
    if ns.disable_websocket is not None:
        websocket_block['enabled'] = not ns.disable_websocket
    if ns.quic_secret is not None:
        quic_block['quic_secret'] = ns.quic_secret.encode('utf-8') if isinstance(ns.quic_secret, str) else ns.quic_secret
    if getattr(ns, 'webtransport_origin', None):
        webtransport_block['origins'] = _listify(ns.webtransport_origin)

    listeners = _listener_overrides_from_namespace(ns)
    if listeners:
        overrides['listeners'] = listeners
    if logging_explicit_fields:
        logging_block['explicit_fields'] = sorted(set(logging_explicit_fields))

    for name, block in (
        ('app', app_block),
        ('process', process_block),
        ('tls', tls_block),
        ('proxy', proxy_block),
        ('http', http_block),
        ('websocket', websocket_block),
        ('static', static_block),
        ('quic', quic_block),
        ('webtransport', webtransport_block),
        ('logging', logging_block),
        ('metrics', metrics_block),
        ('scheduler', scheduler_block),
    ):
        if block:
            overrides[name] = block
    return overrides


def _mapping_get(source: Mapping[str, Any], *path: str) -> Any:
    cursor: Any = source
    for segment in path:
        if not isinstance(cursor, Mapping):
            return None
        cursor = cursor.get(segment)
    return cursor


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
    prefix = env_prefix or _mapping_get(file_dict, 'app', 'env_prefix') or DEFAULT_ENV_PREFIX
    resolved_env_file = env_file or _mapping_get(file_dict, 'app', 'env_file')
    env_file_vars = load_env_file(resolved_env_file)
    env_file_dict = load_env_config(prefix, environ=env_file_vars) if env_file_vars else {}
    env_dict = load_env_config(prefix)
    profile_name = resolve_requested_profile(file_dict, env_file_dict, env_dict, cli_overrides, explicit_profile=profile)
    merged = merge_config_dicts(resolve_effective_profile_mapping(profile_name), file_dict, env_file_dict, env_dict, cli_overrides)
    merged.setdefault('app', {})
    merged['app']['profile'] = profile_name
    return config_from_mapping(merged)


def build_config_from_namespace(ns: Namespace) -> ServerConfig:
    cli_overrides = namespace_to_overrides(ns)
    config_source = getattr(ns, 'config', None)
    env_prefix = getattr(ns, 'env_prefix', None)
    env_file = getattr(ns, 'env_file', None)
    return build_config_from_sources(cli_overrides=cli_overrides, config_source=config_source, env_prefix=env_prefix, env_file=env_file)


def build_config(
    *,
    profile: str | None = None,
    app: str | None = None,
    app_interface: str = 'auto',
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    uds: str | None = None,
    transport: str = 'tcp',
    lifespan: str = 'auto',
    log_level: str = 'info',
    access_log: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ssl_keyfile_password: str | bytes | None = None,
    ssl_ca_certs: str | None = None,
    ssl_require_client_cert: bool | None = None,
    ssl_ciphers: str | None = None,
    ssl_crl: str | None = None,
    http_versions: list[str] | None = None,
    websocket: bool | None = None,
    static_path_route: str | None = None,
    static_path_mount: str | None = None,
    static_path_dir_to_file: bool = True,
    static_path_index_file: str | None = 'index.html',
    static_path_expires: int | None = None,
    enable_h2c: bool | None = None,
    max_body_size: int | None = None,
    max_header_size: int | None = None,
    http1_max_incomplete_event_size: int | None = None,
    http1_buffer_size: int | None = None,
    http1_header_read_timeout: float | None = None,
    http1_keep_alive: bool | None = None,
    http2_max_concurrent_streams: int | None = None,
    http2_max_headers_size: int | None = None,
    http2_max_frame_size: int | None = None,
    http2_adaptive_window: bool | None = None,
    http2_initial_connection_window_size: int | None = None,
    http2_initial_stream_window_size: int | None = None,
    http2_keep_alive_interval: float | None = None,
    http2_keep_alive_timeout: float | None = None,
    websocket_max_queue: int | None = None,
    protocols: list[str] | None = None,
    quic_secret: bytes | None = None,
    quic_require_retry: bool | None = None,
    webtransport_max_sessions: int | None = None,
    webtransport_max_streams: int | None = None,
    webtransport_max_datagram_size: int | None = None,
    webtransport_origins: list[str] | None = None,
    webtransport_path: str | None = None,
    pipe_mode: str = 'rawframed',
    config: Mapping[str, Any] | None = None,
    default_headers: list[str] | list[tuple[str, str]] | None = None,
    include_date_header: bool = True,
    include_server_header: bool = False,
    server_header: str | bytes | None = None,
    env_file: str | None = None,
    server_names: list[str] | None = None,
    alt_svc: list[str] | list[tuple[str, str]] | None = None,
    alt_svc_auto: bool | None = None,
    alt_svc_max_age: int | None = None,
    alt_svc_persist: bool = False,
    runtime: str = 'auto',
    worker_healthcheck_timeout: float | None = None,
    use_colors: bool | None = None,
) -> ServerConfig:
    profile_selected = profile is not None
    requested_http_versions = list(http_versions) if http_versions is not None else None
    direct_runtime_customized = (
        app is not None
        or app_interface != 'auto'
        or host != DEFAULT_HOST
        or port != DEFAULT_PORT
        or uds is not None
        or transport != 'tcp'
        or lifespan != 'auto'
        or http_versions is not None
        or protocols is not None
        or quic_secret is not None
        or pipe_mode != 'rawframed'
        or websocket is not None
        or websocket_max_queue is not None
        or webtransport_max_sessions is not None
        or webtransport_max_streams is not None
        or webtransport_max_datagram_size is not None
        or webtransport_origins is not None
        or webtransport_path is not None
    )
    effective_websocket_enabled = True if websocket is None and direct_runtime_customized else bool(websocket)
    effective_h2c_enabled = (
        bool(enable_h2c)
        if enable_h2c is not None
        else bool(requested_http_versions and "2" in {str(version).replace("http/", "") for version in requested_http_versions})
    )
    overrides: dict[str, Any] = {
        'app': {'target': app, 'interface': app_interface, 'lifespan': lifespan, 'env_file': env_file, 'profile': profile},
        'logging': {'level': log_level, 'access_log': access_log, 'use_colors': use_colors},
        'http': {
            'enable_h2c': effective_h2c_enabled,
            'alt_svc_headers': alt_svc or [],
            'alt_svc_persist': alt_svc_persist,
            'http1_keep_alive': http1_keep_alive,
        },
        'static': {
            'route': static_path_route,
            'mount': static_path_mount,
            'dir_to_file': static_path_dir_to_file,
            'index_file': static_path_index_file,
            'expires': static_path_expires,
        },
        'process': {'runtime': runtime},
        'proxy': {
            'include_date_header': include_date_header,
            'include_server_header': include_server_header,
            'server_header': server_header,
            'default_headers': default_headers or [],
            'server_names': server_names or [],
        },
        'tls': {
            'certfile': ssl_certfile,
            'keyfile': ssl_keyfile,
            'keyfile_password': ssl_keyfile_password,
            'ca_certs': ssl_ca_certs,
            'ciphers': ssl_ciphers,
            'crl': ssl_crl,
        },
    }
    if (
        isinstance(config, Mapping)
        and isinstance(config.get('scheduler'), Mapping)
        and config['scheduler'].get('max_streams') is not None  # type: ignore[index]
        and not (isinstance(config.get('http'), Mapping) and 'http2_max_concurrent_streams' in config['http'])  # type: ignore[index]
        and http2_max_concurrent_streams is None
    ):
        overrides['http']['http2_max_concurrent_streams'] = None
    if (
        max_header_size is not None
        and http2_max_headers_size is None
        and not (isinstance(config, Mapping) and isinstance(config.get('http'), Mapping) and 'http2_max_headers_size' in config['http'])  # type: ignore[index]
    ):
        overrides['http']['http2_max_headers_size'] = None
    if alt_svc_auto is not None or not profile_selected:
        overrides['http']['alt_svc_auto'] = False if alt_svc_auto is None else alt_svc_auto
    if requested_http_versions is not None:
        overrides['http']['http_versions'] = requested_http_versions
    if websocket is not None or (not profile_selected and direct_runtime_customized):
        overrides['websocket'] = {'enabled': effective_websocket_enabled, 'max_queue': websocket_max_queue}
    elif websocket_max_queue is not None:
        overrides['websocket'] = {'max_queue': websocket_max_queue}
    if quic_require_retry is not None or not profile_selected:
        overrides['quic'] = {'require_retry': False if quic_require_retry is None else quic_require_retry}
    if any(
        value is not None
        for value in (
            webtransport_max_sessions,
            webtransport_max_streams,
            webtransport_max_datagram_size,
            webtransport_origins,
            webtransport_path,
        )
    ):
        overrides['webtransport'] = {
            'max_sessions': webtransport_max_sessions,
            'max_streams': webtransport_max_streams,
            'max_datagram_size': webtransport_max_datagram_size,
            'origins': webtransport_origins or [],
            'path': webtransport_path,
        }
    if ssl_require_client_cert is not None or not profile_selected:
        overrides['tls']['require_client_cert'] = False if ssl_require_client_cert is None else ssl_require_client_cert

    listener_customized = (
        (not profile_selected and direct_runtime_customized)
        or uds is not None
        or transport != 'tcp'
        or host != DEFAULT_HOST
        or port != DEFAULT_PORT
        or http_versions is not None
        or protocols is not None
        or quic_secret is not None
        or pipe_mode != 'rawframed'
        or websocket is not None
        or quic_require_retry is not None
        or webtransport_max_sessions is not None
        or webtransport_max_streams is not None
        or webtransport_max_datagram_size is not None
        or webtransport_origins is not None
        or webtransport_path is not None
    )
    if listener_customized:
        overrides['listeners'] = [
            {
                'kind': 'unix' if uds and transport == 'tcp' else transport.lower(),
                'host': host,
                'port': port,
                'path': uds,
                'ssl_certfile': ssl_certfile,
                'ssl_keyfile': ssl_keyfile,
                'ssl_keyfile_password': ssl_keyfile_password,
                'ssl_ca_certs': ssl_ca_certs,
                'ssl_require_client_cert': False if ssl_require_client_cert is None else ssl_require_client_cert,
                'ssl_ciphers': ssl_ciphers,
                'ssl_crl': ssl_crl,
                'http_versions': requested_http_versions,
                'websocket': effective_websocket_enabled,
                'protocols': list(protocols) if protocols is not None else None,
                'quic_secret': quic_secret,
                'quic_require_retry': False if quic_require_retry is None else quic_require_retry,
                'pipe_mode': pipe_mode,
            }
        ]
    if max_body_size is not None:
        overrides.setdefault('http', {})['max_body_size'] = max_body_size
    if max_header_size is not None:
        overrides.setdefault('http', {})['max_header_size'] = max_header_size
    if http1_max_incomplete_event_size is not None:
        overrides.setdefault('http', {})['http1_max_incomplete_event_size'] = http1_max_incomplete_event_size
    if http1_buffer_size is not None:
        overrides.setdefault('http', {})['http1_buffer_size'] = http1_buffer_size
    if http1_header_read_timeout is not None:
        overrides.setdefault('http', {})['http1_header_read_timeout'] = http1_header_read_timeout
    if http2_adaptive_window is not None:
        overrides.setdefault('http', {})['http2_adaptive_window'] = http2_adaptive_window
    if http2_max_concurrent_streams is not None:
        overrides.setdefault('http', {})['http2_max_concurrent_streams'] = http2_max_concurrent_streams
    if http2_max_headers_size is not None:
        overrides.setdefault('http', {})['http2_max_headers_size'] = http2_max_headers_size
    if http2_max_frame_size is not None:
        overrides.setdefault('http', {})['http2_max_frame_size'] = http2_max_frame_size
    if http2_initial_connection_window_size is not None:
        overrides.setdefault('http', {})['http2_initial_connection_window_size'] = http2_initial_connection_window_size
    if http2_initial_stream_window_size is not None:
        overrides.setdefault('http', {})['http2_initial_stream_window_size'] = http2_initial_stream_window_size
    if http2_keep_alive_interval is not None:
        overrides.setdefault('http', {})['http2_keep_alive_interval'] = http2_keep_alive_interval
    if http2_keep_alive_timeout is not None:
        overrides.setdefault('http', {})['http2_keep_alive_timeout'] = http2_keep_alive_timeout
    if alt_svc_max_age is not None:
        overrides.setdefault('http', {})['alt_svc_max_age'] = alt_svc_max_age
    if quic_secret is not None:
        overrides.setdefault('quic', {})['quic_secret'] = quic_secret
    if worker_healthcheck_timeout is not None:
        overrides.setdefault('process', {})['worker_healthcheck_timeout'] = worker_healthcheck_timeout
    return build_config_from_sources(cli_overrides=overrides, config_source=config, profile=profile)
