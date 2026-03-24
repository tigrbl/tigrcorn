from __future__ import annotations

from typing import Any

from tigrcorn.constants import ASGI_SPEC_VERSION, ASGI_VERSION
from tigrcorn.protocols.http1.parser import ParsedRequest, ParsedRequestHead
from tigrcorn.types import Scope
from tigrcorn.utils.proxy import resolve_proxy_view, strip_root_path


def build_http_scope(
    request: ParsedRequest | ParsedRequestHead,
    *,
    client: tuple[str, int] | None,
    server: tuple[str, int] | tuple[str, None] | None,
    scheme: str = "http",
    extensions: dict | None = None,
    root_path: str = "",
    proxy: Any | None = None,
) -> Scope:
    if proxy is not None:
        proxy_view = resolve_proxy_view(
            request.headers,
            client=client,
            server=server,
            scheme=scheme,
            root_path=root_path,
            enabled=bool(getattr(proxy, 'proxy_headers', False)),
            forwarded_allow_ips=tuple(getattr(proxy, 'forwarded_allow_ips', []) or ()),
        )
        client = proxy_view.client
        server = proxy_view.server
        scheme = proxy_view.scheme
        root_path = proxy_view.root_path
    path, raw_path = strip_root_path(request.path, request.raw_path, root_path)
    scope: Scope = {
        "type": "http",
        "asgi": {"version": ASGI_VERSION, "spec_version": ASGI_SPEC_VERSION},
        "http_version": request.http_version,
        "method": request.method,
        "scheme": scheme,
        "path": path,
        "raw_path": raw_path,
        "query_string": request.query_string,
        "root_path": root_path,
        "headers": request.headers,
        "client": client,
        "server": server,
        "extensions": extensions or {},
    }
    return scope
