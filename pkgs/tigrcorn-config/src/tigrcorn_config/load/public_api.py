from __future__ import annotations

from typing import Any, Mapping

from tigrcorn_core.constants import DEFAULT_HOST, DEFAULT_PORT
from tigrcorn_config.model import ServerConfig

from .public_helpers import (
    apply_listener_override_if_needed as _apply_listener_override_if_needed,
    apply_optional_http_overrides as _apply_optional_http_overrides,
    apply_profile_sensitive_overrides as _apply_profile_sensitive_overrides,
    apply_webtransport_overrides as _apply_webtransport_overrides,
)
from .sources import build_config_from_sources


def build_config(
    *,
    profile: str | None = None,
    app: str | None = None,
    app_interface: str = "auto",
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    uds: str | None = None,
    transport: str = "tcp",
    lifespan: str = "auto",
    log_level: str = "info",
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
    static_path_index_file: str | None = "index.html",
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
    webtransport_stream_receive_coalesce_bytes: int | None = None,
    webtransport_stream_receive_max_delay_ms: int | None = None,
    webtransport_origins: list[str] | None = None,
    webtransport_path: str | None = None,
    webtransport_profiles: list[str] | None = None,
    webtransport_preferred_profile: str | None = None,
    pipe_mode: str = "rawframed",
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
    runtime: str = "auto",
    worker_healthcheck_timeout: float | None = None,
    use_colors: bool | None = None,
) -> ServerConfig:
    profile_selected = profile is not None
    requested_http_versions = list(http_versions) if http_versions is not None else None
    direct_runtime_customized = _direct_runtime_customized(
        app=app,
        app_interface=app_interface,
        host=host,
        port=port,
        uds=uds,
        transport=transport,
        lifespan=lifespan,
        http_versions=http_versions,
        protocols=protocols,
        quic_secret=quic_secret,
        pipe_mode=pipe_mode,
        websocket=websocket,
        websocket_max_queue=websocket_max_queue,
        webtransport_max_sessions=webtransport_max_sessions,
        webtransport_max_streams=webtransport_max_streams,
        webtransport_max_datagram_size=webtransport_max_datagram_size,
        webtransport_stream_receive_coalesce_bytes=webtransport_stream_receive_coalesce_bytes,
        webtransport_stream_receive_max_delay_ms=webtransport_stream_receive_max_delay_ms,
        webtransport_origins=webtransport_origins,
        webtransport_path=webtransport_path,
        webtransport_profiles=webtransport_profiles,
        webtransport_preferred_profile=webtransport_preferred_profile,
    )
    effective_websocket_enabled = True if websocket is None and direct_runtime_customized else bool(websocket)
    effective_h2c_enabled = _effective_h2c_enabled(enable_h2c, requested_http_versions)
    overrides = _base_public_overrides(
        app=app,
        app_interface=app_interface,
        lifespan=lifespan,
        env_file=env_file,
        profile=profile,
        log_level=log_level,
        access_log=access_log,
        use_colors=use_colors,
        effective_h2c_enabled=effective_h2c_enabled,
        alt_svc=alt_svc,
        alt_svc_persist=alt_svc_persist,
        http1_keep_alive=http1_keep_alive,
        static_path_route=static_path_route,
        static_path_mount=static_path_mount,
        static_path_dir_to_file=static_path_dir_to_file,
        static_path_index_file=static_path_index_file,
        static_path_expires=static_path_expires,
        runtime=runtime,
        include_date_header=include_date_header,
        include_server_header=include_server_header,
        server_header=server_header,
        default_headers=default_headers,
        server_names=server_names,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_keyfile_password=ssl_keyfile_password,
        ssl_ca_certs=ssl_ca_certs,
        ssl_ciphers=ssl_ciphers,
        ssl_crl=ssl_crl,
    )
    _apply_profile_sensitive_overrides(
        overrides,
        config=config,
        profile_selected=profile_selected,
        requested_http_versions=requested_http_versions,
        direct_runtime_customized=direct_runtime_customized,
        websocket=websocket,
        effective_websocket_enabled=effective_websocket_enabled,
        websocket_max_queue=websocket_max_queue,
        quic_require_retry=quic_require_retry,
        ssl_require_client_cert=ssl_require_client_cert,
        alt_svc_auto=alt_svc_auto,
        max_header_size=max_header_size,
        http2_max_headers_size=http2_max_headers_size,
        http2_max_concurrent_streams=http2_max_concurrent_streams,
    )
    _apply_webtransport_overrides(
        overrides,
        webtransport_max_sessions=webtransport_max_sessions,
        webtransport_max_streams=webtransport_max_streams,
        webtransport_max_datagram_size=webtransport_max_datagram_size,
        webtransport_stream_receive_coalesce_bytes=webtransport_stream_receive_coalesce_bytes,
        webtransport_stream_receive_max_delay_ms=webtransport_stream_receive_max_delay_ms,
        webtransport_origins=webtransport_origins,
        webtransport_path=webtransport_path,
        webtransport_profiles=webtransport_profiles,
        webtransport_preferred_profile=webtransport_preferred_profile,
    )
    _apply_listener_override_if_needed(
        overrides,
        profile_selected=profile_selected,
        direct_runtime_customized=direct_runtime_customized,
        uds=uds,
        transport=transport,
        host=host,
        port=port,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_keyfile_password=ssl_keyfile_password,
        ssl_ca_certs=ssl_ca_certs,
        ssl_require_client_cert=ssl_require_client_cert,
        ssl_ciphers=ssl_ciphers,
        ssl_crl=ssl_crl,
        requested_http_versions=requested_http_versions,
        effective_websocket_enabled=effective_websocket_enabled,
        protocols=protocols,
        quic_secret=quic_secret,
        quic_require_retry=quic_require_retry,
        pipe_mode=pipe_mode,
        websocket=websocket,
        webtransport_max_sessions=webtransport_max_sessions,
        webtransport_max_streams=webtransport_max_streams,
        webtransport_max_datagram_size=webtransport_max_datagram_size,
        webtransport_stream_receive_coalesce_bytes=webtransport_stream_receive_coalesce_bytes,
        webtransport_stream_receive_max_delay_ms=webtransport_stream_receive_max_delay_ms,
        webtransport_origins=webtransport_origins,
        webtransport_path=webtransport_path,
        webtransport_profiles=webtransport_profiles,
        webtransport_preferred_profile=webtransport_preferred_profile,
    )
    _apply_optional_http_overrides(
        overrides,
        max_body_size=max_body_size,
        max_header_size=max_header_size,
        http1_max_incomplete_event_size=http1_max_incomplete_event_size,
        http1_buffer_size=http1_buffer_size,
        http1_header_read_timeout=http1_header_read_timeout,
        http2_adaptive_window=http2_adaptive_window,
        http2_max_concurrent_streams=http2_max_concurrent_streams,
        http2_max_headers_size=http2_max_headers_size,
        http2_max_frame_size=http2_max_frame_size,
        http2_initial_connection_window_size=http2_initial_connection_window_size,
        http2_initial_stream_window_size=http2_initial_stream_window_size,
        http2_keep_alive_interval=http2_keep_alive_interval,
        http2_keep_alive_timeout=http2_keep_alive_timeout,
        alt_svc_max_age=alt_svc_max_age,
        quic_secret=quic_secret,
        worker_healthcheck_timeout=worker_healthcheck_timeout,
    )
    return build_config_from_sources(cli_overrides=overrides, config_source=config, profile=profile)


def _direct_runtime_customized(**values: Any) -> bool:
    return (
        values["app"] is not None
        or values["app_interface"] != "auto"
        or values["host"] != DEFAULT_HOST
        or values["port"] != DEFAULT_PORT
        or values["uds"] is not None
        or values["transport"] != "tcp"
        or values["lifespan"] != "auto"
        or values["http_versions"] is not None
        or values["protocols"] is not None
        or values["quic_secret"] is not None
        or values["pipe_mode"] != "rawframed"
        or values["websocket"] is not None
        or values["websocket_max_queue"] is not None
        or values["webtransport_max_sessions"] is not None
        or values["webtransport_max_streams"] is not None
        or values["webtransport_max_datagram_size"] is not None
        or values["webtransport_stream_receive_coalesce_bytes"] is not None
        or values["webtransport_stream_receive_max_delay_ms"] is not None
        or values["webtransport_origins"] is not None
        or values["webtransport_path"] is not None
        or values["webtransport_profiles"] is not None
        or values["webtransport_preferred_profile"] is not None
    )


def _effective_h2c_enabled(enable_h2c: bool | None, requested_http_versions: list[str] | None) -> bool:
    if enable_h2c is not None:
        return bool(enable_h2c)
    return bool(requested_http_versions and "2" in {str(version).replace("http/", "") for version in requested_http_versions})


def _base_public_overrides(**values: Any) -> dict[str, Any]:
    return {
        "app": {
            "target": values["app"],
            "interface": values["app_interface"],
            "lifespan": values["lifespan"],
            "env_file": values["env_file"],
            "profile": values["profile"],
        },
        "logging": {"level": values["log_level"], "access_log": values["access_log"], "use_colors": values["use_colors"]},
        "http": {
            "enable_h2c": values["effective_h2c_enabled"],
            "alt_svc_headers": values["alt_svc"] or [],
            "alt_svc_persist": values["alt_svc_persist"],
            "http1_keep_alive": values["http1_keep_alive"],
        },
        "static": {
            "route": values["static_path_route"],
            "mount": values["static_path_mount"],
            "dir_to_file": values["static_path_dir_to_file"],
            "index_file": values["static_path_index_file"],
            "expires": values["static_path_expires"],
        },
        "process": {"runtime": values["runtime"]},
        "proxy": {
            "include_date_header": values["include_date_header"],
            "include_server_header": values["include_server_header"],
            "server_header": values["server_header"],
            "default_headers": values["default_headers"] or [],
            "server_names": values["server_names"] or [],
        },
        "tls": {
            "certfile": values["ssl_certfile"],
            "keyfile": values["ssl_keyfile"],
            "keyfile_password": values["ssl_keyfile_password"],
            "ca_certs": values["ssl_ca_certs"],
            "ciphers": values["ssl_ciphers"],
            "crl": values["ssl_crl"],
        },
    }
