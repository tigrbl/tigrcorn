from __future__ import annotations

from tigrcorn.constants import ASGI_SPEC_VERSION, ASGI_VERSION


def build_custom_scope(scope_type: str, **fields) -> dict:
    scope = {
        "type": scope_type,
        "asgi": {"version": ASGI_VERSION, "spec_version": ASGI_SPEC_VERSION},
    }
    scope.update(fields)
    return scope
