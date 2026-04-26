from __future__ import annotations

from typing import Any

from tigrcorn.constants import ASGI_VERSION, WEBSOCKET_SPEC_VERSION
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.types import Scope
from tigrcorn.utils.headers import get_header
from tigrcorn.utils.proxy import resolve_proxy_view, strip_root_path


def build_websocket_scope(
    request: ParsedRequest,
    *,
    client: tuple[str, int] | None,
    server: tuple[str, int] | tuple[str, None] | None,
    scheme: str = "ws",
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
    subprotocol_header = get_header(request.headers, b"sec-websocket-protocol")
    subprotocols = []
    if subprotocol_header:
        subprotocols = [part.strip().decode("ascii", "ignore") for part in subprotocol_header.split(b",") if part.strip()]
    scope_extensions = {"websocket.http.response": {}}
    if extensions:
        scope_extensions.update(extensions)
    scope: Scope = {
        "type": "websocket",
        "asgi": {"version": ASGI_VERSION, "spec_version": WEBSOCKET_SPEC_VERSION},
        "http_version": request.http_version,
        "scheme": scheme,
        "path": path,
        "raw_path": raw_path,
        "query_string": request.query_string,
        "root_path": root_path,
        "headers": request.headers,
        "client": client,
        "server": server,
        "subprotocols": subprotocols,
        "extensions": scope_extensions,
    }
    return scope
