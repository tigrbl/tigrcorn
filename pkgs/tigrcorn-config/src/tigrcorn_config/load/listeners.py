from __future__ import annotations

from argparse import Namespace
from typing import Any

from tigrcorn_core.constants import DEFAULT_HOST, DEFAULT_PORT

from .helpers import listify


def parse_bind(value: str, *, kind: str) -> dict[str, Any]:
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


def listener_overrides_from_namespace(ns: Namespace) -> list[dict[str, Any]] | None:
    listeners: list[dict[str, Any]] = []
    for item in list(ns.bind or []):
        listeners.append(parse_bind(item, kind="tcp"))
    for item in list(ns.quic_bind or []):
        listener = parse_bind(item, kind="udp")
        listener["quic_bind"] = item
        listeners.append(listener)
    for item in list(ns.insecure_bind or []):
        listener = parse_bind(item, kind="tcp")
        listener["insecure_bind"] = item
        listeners.append(listener)
    for item in list(ns.fd or []):
        listeners.append({"kind": ns.transport or "tcp", "fd": int(item)})
    for item in list(ns.endpoint or []):
        listeners.append({"kind": ns.transport or "tcp", "endpoint": item})

    if not listeners:
        if ns.uds:
            kind = "pipe" if ns.transport == "pipe" else "unix"
            listeners.append({"kind": kind, "path": ns.uds})
        else:
            listeners.append({"kind": ns.transport or "tcp", "host": ns.host or DEFAULT_HOST, "port": ns.port or DEFAULT_PORT})

    for listener in listeners:
        _apply_common_listener_fields(ns, listener)
    return listeners


def _apply_common_listener_fields(ns: Namespace, listener: dict[str, Any]) -> None:
    for attr in ("backlog", "reuse_port", "reuse_address"):
        value = getattr(ns, attr, None)
        if value is not None:
            listener[attr] = value
    if ns.pipe_mode is not None and listener.get("kind") == "pipe":
        listener["pipe_mode"] = ns.pipe_mode
    if ns.user is not None and listener.get("kind") == "unix":
        listener["user"] = ns.user
    if ns.group is not None and listener.get("kind") == "unix":
        listener["group"] = ns.group
    if ns.umask is not None and listener.get("kind") == "unix":
        listener["umask"] = ns.umask
    if ns.http_versions:
        listener["http_versions"] = list(ns.http_versions)
    if ns.protocols:
        listener["protocols"] = list(ns.protocols)
    if ns.disable_websocket is not None:
        listener["websocket"] = not ns.disable_websocket
    _apply_listener_tls_fields(ns, listener)
    _apply_listener_quic_fields(ns, listener)


def _apply_listener_tls_fields(ns: Namespace, listener: dict[str, Any]) -> None:
    if listener.get("insecure_bind"):
        return
    mapping = {
        "ssl_certfile": "ssl_certfile",
        "ssl_keyfile": "ssl_keyfile",
        "ssl_keyfile_password": "ssl_keyfile_password",
        "ssl_ca_certs": "ssl_ca_certs",
        "ssl_require_client_cert": "ssl_require_client_cert",
        "ssl_ocsp_mode": "ocsp_mode",
        "ssl_ocsp_soft_fail": "ocsp_soft_fail",
        "ssl_ocsp_cache_size": "ocsp_cache_size",
        "ssl_ocsp_max_age": "ocsp_max_age",
        "ssl_crl_mode": "crl_mode",
        "ssl_crl": "ssl_crl",
    }
    for source, dest in mapping.items():
        value = getattr(ns, source, None)
        if value is not None:
            listener[dest] = value
    if ns.ssl_alpn:
        listener["alpn_protocols"] = listify(ns.ssl_alpn)
    if getattr(ns, "ssl_revocation_fetch", None) is not None:
        value = ns.ssl_revocation_fetch
        listener["revocation_fetch"] = value == "on" if isinstance(value, str) else bool(value)


def _apply_listener_quic_fields(ns: Namespace, listener: dict[str, Any]) -> None:
    if listener.get("kind") != "udp":
        return
    if ns.quic_require_retry is not None:
        listener["quic_require_retry"] = ns.quic_require_retry
    if ns.quic_max_datagram_size is not None:
        listener["max_datagram_size"] = ns.quic_max_datagram_size
    if ns.quic_secret is not None:
        listener["quic_secret"] = ns.quic_secret.encode("utf-8") if isinstance(ns.quic_secret, str) else ns.quic_secret
