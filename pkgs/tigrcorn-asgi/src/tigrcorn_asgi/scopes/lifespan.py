from __future__ import annotations

from tigrcorn.constants import ASGI_SPEC_VERSION, ASGI_VERSION
from tigrcorn.types import Scope


def build_lifespan_scope() -> Scope:
    return {
        "type": "lifespan",
        "asgi": {"version": ASGI_VERSION, "spec_version": ASGI_SPEC_VERSION},
        "state": {},
    }
