from __future__ import annotations

from tigrcorn.config.model import ServerConfig


def normalize_config(config: ServerConfig) -> None:
    config.log_level = config.log_level.lower()
    for listener in config.listeners:
        listener.kind = listener.kind.lower()  # type: ignore[assignment]
        listener.http_versions = [str(v).replace("http/", "") for v in listener.http_versions]
        listener.protocols = [str(v).lower() for v in listener.protocols]
        if listener.kind in {"tcp", "unix"} and not listener.alpn_protocols:
            listener.alpn_protocols = ["h2", "http/1.1"]
        if listener.kind == "udp" and "http3" in listener.protocols and "quic" not in listener.protocols:
            listener.protocols.insert(0, "quic")
        if listener.kind == "udp" and not listener.scheme:
            listener.scheme = "https" if "http3" in listener.enabled_protocols else "quic"
        elif listener.kind == "pipe" and not listener.scheme:
            listener.scheme = "tigrcorn+pipe"
        elif listener.kind == "unix" and not listener.scheme:
            listener.scheme = "http"
        elif listener.kind == "inproc" and not listener.scheme:
            listener.scheme = "tigrcorn+inproc"
        elif listener.kind == "tcp" and not listener.scheme:
            listener.scheme = "https" if listener.ssl_enabled else "http"
