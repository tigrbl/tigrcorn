from __future__ import annotations

from tigrcorn.constants import ASGI_SPEC_VERSION, ASGI_VERSION, WEBSOCKET_SPEC_VERSION
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.types import Scope
from tigrcorn.utils.headers import get_header


def build_websocket_scope(
    request: ParsedRequest,
    *,
    client: tuple[str, int] | None,
    server: tuple[str, int] | tuple[str, None] | None,
    scheme: str = "ws",
    extensions: dict | None = None,
) -> Scope:
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
        "path": request.path,
        "raw_path": request.raw_path,
        "query_string": request.query_string,
        "root_path": "",
        "headers": request.headers,
        "client": client,
        "server": server,
        "subprotocols": subprotocols,
        "extensions": scope_extensions,
    }
    return scope
