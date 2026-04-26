from __future__ import annotations

__all__ = [
    "run",
    "serve",
    "serve_import_string",
]


def __getattr__(name: str):
    if name in __all__:
        from .api import run, serve, serve_import_string

        mapping = {
            "run": run,
            "serve": serve,
            "serve_import_string": serve_import_string,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
