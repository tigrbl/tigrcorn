from __future__ import annotations

from argparse import Namespace
from typing import Any

from .helpers import listify
from .listeners import listener_overrides_from_namespace


def namespace_to_overrides(ns: Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    blocks = {
        "app": {},
        "process": {},
        "tls": {},
        "proxy": {},
        "http": {},
        "websocket": {},
        "static": {},
        "quic": {},
        "webtransport": {},
        "logging": {},
        "metrics": {},
        "scheduler": {},
    }

    _populate_app_block(ns, blocks["app"])
    logging_explicit_fields = _populate_mapped_blocks(ns, blocks)
    _populate_special_blocks(ns, blocks, logging_explicit_fields)

    listeners = listener_overrides_from_namespace(ns)
    if listeners:
        overrides["listeners"] = listeners
    if logging_explicit_fields:
        blocks["logging"]["explicit_fields"] = sorted(set(logging_explicit_fields))

    for name, block in blocks.items():
        if block:
            overrides[name] = block
    return overrides


def _populate_app_block(ns: Namespace, app_block: dict[str, Any]) -> None:
    if ns.app is not None:
        app_block["target"] = ns.app
    for key, dest in (
        ("factory", "factory"),
        ("app_interface", "interface"),
        ("app_dir", "app_dir"),
        ("lifespan", "lifespan"),
        ("reload", "reload"),
        ("config", "config_file"),
        ("env_prefix", "env_prefix"),
        ("env_file", "env_file"),
    ):
        value = getattr(ns, key, None)
        if value is not None:
            app_block[dest] = value
    if ns.reload_dir:
        app_block["reload_dirs"] = list(ns.reload_dir)
    if ns.reload_include:
        app_block["reload_include"] = list(ns.reload_include)
    if ns.reload_exclude:
        app_block["reload_exclude"] = list(ns.reload_exclude)


def _populate_mapped_blocks(ns: Namespace, blocks: dict[str, dict[str, Any]]) -> list[str]:
    logging_explicit_fields: list[str] = []
    for key, (block_name, dest) in _NAMESPACE_MAPPING.items():
        value = getattr(ns, key, None)
        if value is not None:
            block = blocks[block_name]
            block[dest] = value
            if block_name == "logging" and dest in _LOGGING_EXPLICIT_DESTS:
                logging_explicit_fields.append(dest)
    return logging_explicit_fields


def _populate_special_blocks(
    ns: Namespace,
    blocks: dict[str, dict[str, Any]],
    logging_explicit_fields: list[str],
) -> None:
    if ns.ssl_alpn:
        blocks["tls"]["alpn_protocols"] = listify(ns.ssl_alpn)
    if ns.log_config is not None:
        logging_explicit_fields.append("log_config")
    if getattr(ns, "ssl_revocation_fetch", None) is not None:
        value = ns.ssl_revocation_fetch
        blocks["tls"]["revocation_fetch"] = value == "on" if isinstance(value, str) else bool(value)
    if ns.forwarded_allow_ips:
        blocks["proxy"]["forwarded_allow_ips"] = listify(ns.forwarded_allow_ips)
    if ns.server_header is not None:
        blocks["proxy"]["server_header"] = ns.server_header
        blocks["proxy"]["include_server_header"] = True
    if ns.no_server_header:
        blocks["proxy"]["include_server_header"] = False
        blocks["proxy"]["server_header"] = ""
    if ns.date_header is not None:
        blocks["proxy"]["include_date_header"] = ns.date_header
    if ns.headers:
        blocks["proxy"]["default_headers"] = list(ns.headers)
    if ns.server_name:
        blocks["proxy"]["server_names"] = listify(ns.server_name)
    if ns.http_versions:
        blocks["http"]["http_versions"] = list(ns.http_versions)
    if getattr(ns, "alt_svc", None):
        blocks["http"]["alt_svc_headers"] = listify(ns.alt_svc)
    if ns.content_codings:
        blocks["http"]["content_codings"] = listify(ns.content_codings)
    if getattr(ns, "connect_allow", None):
        blocks["http"]["connect_allow"] = listify(ns.connect_allow)
    if ns.disable_h2c is not None:
        blocks["http"]["enable_h2c"] = not ns.disable_h2c
    if ns.disable_websocket is not None:
        blocks["websocket"]["enabled"] = not ns.disable_websocket
    if ns.quic_secret is not None:
        blocks["quic"]["quic_secret"] = ns.quic_secret.encode("utf-8") if isinstance(ns.quic_secret, str) else ns.quic_secret
    if getattr(ns, "webtransport_origin", None):
        blocks["webtransport"]["origins"] = listify(ns.webtransport_origin)


_LOGGING_EXPLICIT_DESTS = {
    "level",
    "access_log",
    "access_log_file",
    "access_log_format",
    "error_log_file",
    "structured",
    "use_colors",
    "log_config",
}

_NAMESPACE_MAPPING: dict[str, tuple[str, str]] = {
    "workers": ("process", "workers"),
    "worker_class": ("process", "worker_class"),
    "runtime": ("process", "runtime"),
    "pid": ("process", "pid_file"),
    "worker_healthcheck_timeout": ("process", "worker_healthcheck_timeout"),
    "limit_max_requests": ("process", "limit_max_requests"),
    "max_requests_jitter": ("process", "max_requests_jitter"),
    "ssl_certfile": ("tls", "certfile"),
    "ssl_keyfile": ("tls", "keyfile"),
    "ssl_keyfile_password": ("tls", "keyfile_password"),
    "ssl_ca_certs": ("tls", "ca_certs"),
    "ssl_require_client_cert": ("tls", "require_client_cert"),
    "ssl_ciphers": ("tls", "ciphers"),
    "ssl_ocsp_mode": ("tls", "ocsp_mode"),
    "ssl_ocsp_soft_fail": ("tls", "ocsp_soft_fail"),
    "ssl_ocsp_cache_size": ("tls", "ocsp_cache_size"),
    "ssl_ocsp_max_age": ("tls", "ocsp_max_age"),
    "ssl_crl_mode": ("tls", "crl_mode"),
    "ssl_crl": ("tls", "crl"),
    "proxy_headers": ("proxy", "proxy_headers"),
    "root_path": ("proxy", "root_path"),
    "timeout_keep_alive": ("http", "keep_alive_timeout"),
    "read_timeout": ("http", "read_timeout"),
    "write_timeout": ("http", "write_timeout"),
    "timeout_graceful_shutdown": ("http", "shutdown_timeout"),
    "idle_timeout": ("http", "idle_timeout"),
    "max_body_size": ("http", "max_body_size"),
    "max_header_size": ("http", "max_header_size"),
    "http1_max_incomplete_event_size": ("http", "http1_max_incomplete_event_size"),
    "http1_buffer_size": ("http", "http1_buffer_size"),
    "http1_header_read_timeout": ("http", "http1_header_read_timeout"),
    "http1_keep_alive": ("http", "http1_keep_alive"),
    "http2_max_concurrent_streams": ("http", "http2_max_concurrent_streams"),
    "http2_max_headers_size": ("http", "http2_max_headers_size"),
    "http2_max_frame_size": ("http", "http2_max_frame_size"),
    "http2_adaptive_window": ("http", "http2_adaptive_window"),
    "http2_initial_connection_window_size": ("http", "http2_initial_connection_window_size"),
    "http2_initial_stream_window_size": ("http", "http2_initial_stream_window_size"),
    "http2_keep_alive_interval": ("http", "http2_keep_alive_interval"),
    "http2_keep_alive_timeout": ("http", "http2_keep_alive_timeout"),
    "connect_policy": ("http", "connect_policy"),
    "trailer_policy": ("http", "trailer_policy"),
    "content_coding_policy": ("http", "content_coding_policy"),
    "alt_svc_auto": ("http", "alt_svc_auto"),
    "alt_svc_ma": ("http", "alt_svc_max_age"),
    "alt_svc_persist": ("http", "alt_svc_persist"),
    "websocket_max_message_size": ("websocket", "max_message_size"),
    "websocket_max_queue": ("websocket", "max_queue"),
    "websocket_ping_interval": ("websocket", "ping_interval"),
    "websocket_ping_timeout": ("websocket", "ping_timeout"),
    "websocket_compression": ("websocket", "compression"),
    "static_path_route": ("static", "route"),
    "static_path_mount": ("static", "mount"),
    "static_path_dir_to_file": ("static", "dir_to_file"),
    "static_path_index_file": ("static", "index_file"),
    "static_path_expires": ("static", "expires"),
    "quic_require_retry": ("quic", "require_retry"),
    "quic_max_datagram_size": ("quic", "max_datagram_size"),
    "quic_idle_timeout": ("quic", "idle_timeout"),
    "quic_early_data_policy": ("quic", "early_data_policy"),
    "webtransport_max_sessions": ("webtransport", "max_sessions"),
    "webtransport_max_streams": ("webtransport", "max_streams"),
    "webtransport_max_datagram_size": ("webtransport", "max_datagram_size"),
    "webtransport_path": ("webtransport", "path"),
    "webtransport_profiles": ("webtransport", "profiles"),
    "webtransport_preferred_profile": ("webtransport", "preferred_profile"),
    "log_level": ("logging", "level"),
    "access_log": ("logging", "access_log"),
    "access_log_file": ("logging", "access_log_file"),
    "access_log_format": ("logging", "access_log_format"),
    "error_log_file": ("logging", "error_log_file"),
    "log_config": ("logging", "log_config"),
    "structured_log": ("logging", "structured"),
    "use_colors": ("logging", "use_colors"),
    "metrics": ("metrics", "enabled"),
    "metrics_bind": ("metrics", "bind"),
    "statsd_host": ("metrics", "statsd_host"),
    "otel_endpoint": ("metrics", "otel_endpoint"),
    "limit_concurrency": ("scheduler", "limit_concurrency"),
    "max_connections": ("scheduler", "max_connections"),
    "max_tasks": ("scheduler", "max_tasks"),
    "max_streams": ("scheduler", "max_streams"),
}
