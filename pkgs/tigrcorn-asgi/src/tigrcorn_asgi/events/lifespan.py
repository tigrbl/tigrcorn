from __future__ import annotations


def lifespan_startup() -> dict:
    return {"type": "lifespan.startup"}


def lifespan_shutdown() -> dict:
    return {"type": "lifespan.shutdown"}
