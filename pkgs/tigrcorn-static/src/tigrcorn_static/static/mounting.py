from __future__ import annotations

from pathlib import Path
from typing import Iterable

from tigrcorn_core.types import ASGIApp
from tigrcorn_core.utils.proxy import strip_root_path

from .app import StaticFilesApp


async def _not_found_app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1000})
        return
    if scope["type"] != "http":
        raise RuntimeError(f"unsupported scope type for static fallback: {scope['type']!r}")
    if scope.get("method", "GET").upper() not in {"GET", "HEAD"}:
        await send(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [(b"allow", b"GET, HEAD"), (b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": b"method not allowed"})
        return
    await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
    await send({"type": "http.response.body", "body": b"not found"})


def normalize_static_route(route: str | None) -> str:
    if not route:
        return "/"
    return ("/" + str(route).lstrip("/")).rstrip("/") or "/"


def _route_matches(route: str, path: str) -> bool:
    if route == "/":
        return True
    return path == route or path.startswith(route + "/")


def mount_static_app(
    app: ASGIApp | None,
    *,
    route: str,
    directory: str | Path,
    dir_to_file: bool = True,
    index_file: str | None = "index.html",
    expires: int | None = None,
    apply_content_coding: bool = True,
    content_coding_policy: str = "allowlist",
    content_codings: Iterable[str] = ("br", "gzip", "deflate"),
    use_precompressed_sidecars: bool = True,
    precompressed_codings: Iterable[str] = ("br", "gzip"),
) -> ASGIApp:
    static_app = StaticFilesApp(
        directory,
        index_file=index_file,
        dir_to_file=dir_to_file,
        expires=expires,
        apply_content_coding=apply_content_coding,
        content_coding_policy=content_coding_policy,
        content_codings=content_codings,
        use_precompressed_sidecars=use_precompressed_sidecars,
        precompressed_codings=precompressed_codings,
    )
    fallback = app or _not_found_app
    normalized_route = normalize_static_route(route)

    async def wrapped(scope, receive, send) -> None:
        if scope["type"] != "http":
            await fallback(scope, receive, send)
            return
        path = str(scope.get("path") or "/")
        if not _route_matches(normalized_route, path):
            await fallback(scope, receive, send)
            return
        raw_path = bytes(scope.get("raw_path") or path.encode("latin1"))
        mounted_path, mounted_raw_path = strip_root_path(path, raw_path, normalized_route)
        mounted_scope = dict(scope)
        mounted_scope["path"] = mounted_path
        mounted_scope["raw_path"] = mounted_raw_path
        if normalized_route != "/":
            existing_root = str(scope.get("root_path") or "")
            combined_root = (existing_root.rstrip("/") + normalized_route).rstrip("/") or "/"
            mounted_scope["root_path"] = combined_root
        await static_app(mounted_scope, receive, send)

    return wrapped
