from __future__ import annotations

from pathlib import Path


def peer_parts(peername) -> tuple[str | None, int | None]:
    if isinstance(peername, tuple) and len(peername) >= 2:
        host = peername[0]
        port = peername[1]
        if isinstance(host, str) and isinstance(port, int):
            return host, port
    return None, None


def format_bind(host: str, port: int) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
