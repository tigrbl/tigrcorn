from __future__ import annotations

import sys
from contextlib import contextmanager

from tigrcorn.errors import AppLoadError
from tigrcorn.types import ASGIApp
from tigrcorn.utils.imports import import_from_string


@contextmanager
def _temporary_app_dir(app_dir: str | None):
    if not app_dir:
        yield
        return
    inserted = False
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(app_dir)
            except ValueError:  # pragma: no cover
                pass


def load_app(target: str, *, factory: bool = False, app_dir: str | None = None) -> ASGIApp:
    try:
        with _temporary_app_dir(app_dir):
            loaded = import_from_string(target)
    except Exception as exc:  # pragma: no cover
        raise AppLoadError(f"failed to load ASGI app {target!r}: {exc}") from exc
    if factory:
        loaded = loaded()
    if not callable(loaded):
        raise AppLoadError(f"loaded object is not callable: {target!r}")
    return loaded  # type: ignore[return-value]
