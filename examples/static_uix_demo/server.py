from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from tigrcorn.static import StaticFilesApp
from tigrcorn_core.utils.proxy import strip_root_path


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
STATIC_ROUTE = "/assets"

JSON_HEADERS = [
    (b"content-type", b"application/json; charset=utf-8"),
    (b"access-control-allow-origin", b"*"),
    (b"access-control-allow-methods", b"GET, HEAD, OPTIONS"),
    (b"access-control-allow-headers", b"range, if-none-match, if-modified-since, accept-encoding"),
    (
        b"access-control-expose-headers",
        b"etag, last-modified, content-length, content-range, accept-ranges, cache-control, content-encoding, vary",
    ),
    (b"cache-control", b"no-store"),
]

STATIC_HEADERS = [
    (b"access-control-allow-origin", b"*"),
    (
        b"access-control-expose-headers",
        b"etag, last-modified, content-length, content-range, accept-ranges, cache-control, content-encoding, vary",
    ),
]

static_app = StaticFilesApp(
    PUBLIC,
    index_file="index.html",
    dir_to_file=True,
    expires=120,
    default_headers=STATIC_HEADERS,
    apply_content_coding=True,
    content_coding_policy="allowlist",
    content_codings=("br", "gzip", "deflate"),
    use_precompressed_sidecars=True,
    precompressed_codings=("br", "gzip"),
)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


async def _send_json(send, payload: dict[str, Any], status: int = 200) -> None:
    body = _json_bytes(payload)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": JSON_HEADERS + [(b"content-length", str(len(body)).encode("ascii"))],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def _send_empty(send, status: int = 204) -> None:
    await send({"type": "http.response.start", "status": status, "headers": JSON_HEADERS})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


async def _handle_lifespan(receive, send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _mount_static(scope: dict[str, Any], receive, send) -> None:
    path = str(scope.get("path") or "/")
    raw_path = bytes(scope.get("raw_path") or path.encode("latin1"))
    mounted_path, mounted_raw_path = strip_root_path(path, raw_path, STATIC_ROUTE)
    mounted_scope = dict(scope)
    mounted_scope["path"] = mounted_path
    mounted_scope["raw_path"] = mounted_raw_path
    mounted_scope["root_path"] = STATIC_ROUTE
    await static_app(mounted_scope, receive, send)


async def app(scope: dict[str, Any], receive, send) -> None:
    if scope["type"] == "lifespan":
        await _handle_lifespan(receive, send)
        return

    if scope["type"] != "http":
        raise RuntimeError("static UIX demo only accepts ASGI HTTP scopes")

    method = str(scope.get("method", "GET")).upper()
    path = str(scope.get("path") or "/")

    if method == "OPTIONS":
        await _send_empty(send)
        return

    if path == "/" or path == "/api":
        await _send_json(
            send,
            {
                "name": "tigrcorn static ASGI3 demo",
                "static_route": STATIC_ROUTE,
                "static_directory": str(PUBLIC),
                "try": [
                    "/assets/",
                    "/assets/site.css",
                    "/assets/data/config.json",
                    "/assets/docs/readme.txt",
                ],
                "features": [
                    "directory index to index.html",
                    "ETag and Last-Modified validators",
                    "Range and HEAD handling",
                    "Cache-Control and Expires headers",
                    "precompressed sidecar negotiation when available",
                    "tigrcorn file-response extension when the server exposes it",
                ],
            },
        )
        return

    if path == "/api/list":
        entries = []
        for item in sorted(PUBLIC.rglob("*")):
            if item.is_file() and not item.name.endswith((".br", ".gz")):
                entries.append(
                    {
                        "path": f"{STATIC_ROUTE}/{item.relative_to(PUBLIC).as_posix()}",
                        "bytes": item.stat().st_size,
                    }
                )
        await _send_json(send, {"entries": entries})
        return

    if path == "/api/resolve":
        query = parse_qs(scope.get("query_string", b"").decode("utf-8", "replace"))
        requested = query.get("path", [f"{STATIC_ROUTE}/"])[0]
        await _send_json(
            send,
            {
                "requested": requested,
                "normalized_static_route": STATIC_ROUTE,
                "will_mount": requested == STATIC_ROUTE or requested.startswith(STATIC_ROUTE + "/"),
            },
        )
        return

    if path == STATIC_ROUTE or path.startswith(STATIC_ROUTE + "/"):
        if method not in {"GET", "HEAD"}:
            await _send_json(send, {"error": "static assets only allow GET and HEAD"}, status=405)
            return
        await _mount_static(scope, receive, send)
        return

    await _send_json(send, {"error": "not found", "path": path}, status=404)
