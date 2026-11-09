from __future__ import annotations

from __future__ import annotations

from importlib import import_module as _import_module

_module = _import_module("tigrcorn_compat")
__all__ = list(getattr(_module, "__all__", ()))


def __getattr__(name: str):
    return getattr(_module, name)
