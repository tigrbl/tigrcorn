from __future__ import annotations

from tigrcorn_core.constants import ASGI_SPEC_VERSION, ASGI_VERSION
from tigrcorn_core.types import Scope


def build_lifespan_scope() -> Scope:
    return {
        "type": "lifespan",
        "asgi": {"version": ASGI_VERSION, "spec_version": ASGI_SPEC_VERSION},
        "state": {},
    }
