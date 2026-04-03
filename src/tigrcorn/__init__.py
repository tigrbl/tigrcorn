from .version import __version__

__all__ = ["__version__", "run", "serve", "serve_import_string", "StaticFilesApp", "EmbeddedServer"]


def __getattr__(name: str):
    if name in {"run", "serve", "serve_import_string"}:
        from .api import run, serve, serve_import_string

        mapping = {
            "run": run,
            "serve": serve,
            "serve_import_string": serve_import_string,
        }
        return mapping[name]
    if name == "EmbeddedServer":
        from .embedded import EmbeddedServer

        return EmbeddedServer
    if name == "StaticFilesApp":
        from .static import StaticFilesApp

        return StaticFilesApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
