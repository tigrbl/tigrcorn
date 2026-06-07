from __future__ import annotations

from typing import Any, Mapping

from tigrcorn_core.constants import DEFAULT_HOST, DEFAULT_PORT


def apply_profile_sensitive_overrides(
    overrides: dict[str, Any],
    *,
    config: Mapping[str, Any] | None,
    profile_selected: bool,
    requested_http_versions: list[str] | None,
    direct_runtime_customized: bool,
    websocket: bool | None,
    effective_websocket_enabled: bool,
    websocket_max_queue: int | None,
    quic_require_retry: bool | None,
    ssl_require_client_cert: bool | None,
    alt_svc_auto: bool | None,
    max_header_size: int | None,
    http2_max_headers_size: int | None,
    http2_max_concurrent_streams: int | None,
) -> None:
    if (
        isinstance(config, Mapping)
        and isinstance(config.get("scheduler"), Mapping)
        and config["scheduler"].get("max_streams") is not None  # type: ignore[index]
        and not (isinstance(config.get("http"), Mapping) and "http2_max_concurrent_streams" in config["http"])  # type: ignore[index]
        and http2_max_concurrent_streams is None
    ):
        overrides["http"]["http2_max_concurrent_streams"] = None
    if (
        max_header_size is not None
        and http2_max_headers_size is None
        and not (isinstance(config, Mapping) and isinstance(config.get("http"), Mapping) and "http2_max_headers_size" in config["http"])  # type: ignore[index]
    ):
        overrides["http"]["http2_max_headers_size"] = None
    if alt_svc_auto is not None or not profile_selected:
        overrides["http"]["alt_svc_auto"] = False if alt_svc_auto is None else alt_svc_auto
    if requested_http_versions is not None:
        overrides["http"]["http_versions"] = requested_http_versions
    if websocket is not None or (not profile_selected and direct_runtime_customized):
        overrides["websocket"] = {"enabled": effective_websocket_enabled, "max_queue": websocket_max_queue}
    elif websocket_max_queue is not None:
        overrides["websocket"] = {"max_queue": websocket_max_queue}
    if quic_require_retry is not None or not profile_selected:
        overrides["quic"] = {"require_retry": False if quic_require_retry is None else quic_require_retry}
    if ssl_require_client_cert is not None or not profile_selected:
        overrides["tls"]["require_client_cert"] = False if ssl_require_client_cert is None else ssl_require_client_cert


def apply_webtransport_overrides(
    overrides: dict[str, Any],
    *,
    webtransport_max_sessions: int | None,
    webtransport_max_streams: int | None,
    webtransport_max_datagram_size: int | None,
    webtransport_origins: list[str] | None,
    webtransport_path: str | None,
) -> None:
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
        overrides["webtransport"] = {
            "max_sessions": webtransport_max_sessions,
            "max_streams": webtransport_max_streams,
            "max_datagram_size": webtransport_max_datagram_size,
            "origins": webtransport_origins or [],
            "path": webtransport_path,
        }


def apply_listener_override_if_needed(overrides: dict[str, Any], **values: Any) -> None:
    listener_customized = (
        (not values["profile_selected"] and values["direct_runtime_customized"])
        or values["uds"] is not None
        or values["transport"] != "tcp"
        or values["host"] != DEFAULT_HOST
        or values["port"] != DEFAULT_PORT
        or values["requested_http_versions"] is not None
        or values["protocols"] is not None
        or values["quic_secret"] is not None
        or values["pipe_mode"] != "rawframed"
        or values["websocket"] is not None
        or values["quic_require_retry"] is not None
        or values["webtransport_max_sessions"] is not None
        or values["webtransport_max_streams"] is not None
        or values["webtransport_max_datagram_size"] is not None
        or values["webtransport_origins"] is not None
        or values["webtransport_path"] is not None
    )
    if not listener_customized:
        return
    overrides["listeners"] = [
        {
            "kind": "unix" if values["uds"] and values["transport"] == "tcp" else values["transport"].lower(),
            "host": values["host"],
            "port": values["port"],
            "path": values["uds"],
            "ssl_certfile": values["ssl_certfile"],
            "ssl_keyfile": values["ssl_keyfile"],
            "ssl_keyfile_password": values["ssl_keyfile_password"],
            "ssl_ca_certs": values["ssl_ca_certs"],
            "ssl_require_client_cert": False if values["ssl_require_client_cert"] is None else values["ssl_require_client_cert"],
            "ssl_ciphers": values["ssl_ciphers"],
            "ssl_crl": values["ssl_crl"],
            "http_versions": values["requested_http_versions"],
            "websocket": values["effective_websocket_enabled"],
            "protocols": list(values["protocols"]) if values["protocols"] is not None else None,
            "quic_secret": values["quic_secret"],
            "quic_require_retry": False if values["quic_require_retry"] is None else values["quic_require_retry"],
            "pipe_mode": values["pipe_mode"],
        }
    ]


def apply_optional_http_overrides(overrides: dict[str, Any], **values: Any) -> None:
    http_keys = (
        "max_body_size",
        "max_header_size",
        "http1_max_incomplete_event_size",
        "http1_buffer_size",
        "http1_header_read_timeout",
        "http2_adaptive_window",
        "http2_max_concurrent_streams",
        "http2_max_headers_size",
        "http2_max_frame_size",
        "http2_initial_connection_window_size",
        "http2_initial_stream_window_size",
        "http2_keep_alive_interval",
        "http2_keep_alive_timeout",
        "alt_svc_max_age",
    )
    for key in http_keys:
        if values[key] is not None:
            overrides.setdefault("http", {})[key] = values[key]
    if values["quic_secret"] is not None:
        overrides.setdefault("quic", {})["quic_secret"] = values["quic_secret"]
    if values["worker_healthcheck_timeout"] is not None:
        overrides.setdefault("process", {})["worker_healthcheck_timeout"] = values["worker_healthcheck_timeout"]
