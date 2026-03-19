from __future__ import annotations

from tigrcorn.errors import AppLoadError
from tigrcorn.types import ASGIApp
from tigrcorn.utils.imports import import_from_string


def load_app(target: str, *, factory: bool = False) -> ASGIApp:
    try:
        loaded = import_from_string(target)
    except Exception as exc:  # pragma: no cover
        raise AppLoadError(f"failed to load ASGI app {target!r}: {exc}") from exc
    if factory:
        loaded = loaded()
    if not callable(loaded):
        raise AppLoadError(f"loaded object is not callable: {target!r}")
    return loaded  # type: ignore[return-value]
