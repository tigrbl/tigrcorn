from __future__ import annotations

from tigrcorn.constants import ASGI_SPEC_VERSION, ASGI_VERSION
from tigrcorn.protocols.http1.parser import ParsedRequest, ParsedRequestHead
from tigrcorn.types import Scope


def build_http_scope(
    request: ParsedRequest | ParsedRequestHead,
    *,
    client: tuple[str, int] | None,
    server: tuple[str, int] | tuple[str, None] | None,
    scheme: str = "http",
    extensions: dict | None = None,
) -> Scope:
    scope: Scope = {
        "type": "http",
        "asgi": {"version": ASGI_VERSION, "spec_version": ASGI_SPEC_VERSION},
        "http_version": request.http_version,
        "method": request.method,
        "scheme": scheme,
        "path": request.path,
        "raw_path": request.raw_path,
        "query_string": request.query_string,
        "root_path": "",
        "headers": request.headers,
        "client": client,
        "server": server,
        "extensions": extensions or {},
    }
    return scope
