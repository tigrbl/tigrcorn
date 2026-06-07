from __future__ import annotations

from importlib import import_module as _import_module

__all__ = ["governance"]


def __getattr__(name: str):
    if name == "governance":
        return _import_module(".governance", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
