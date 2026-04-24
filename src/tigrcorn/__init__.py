from .version import __version__

__all__ = [
    "__version__",
    "run",
    "serve",
    "serve_import_string",
    "StaticFilesApp",
    "EmbeddedServer",
    "NativeContractApp",
    "native_contract_app",
    "mark_native_contract_app",
]


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
    if name in {"NativeContractApp", "native_contract_app", "mark_native_contract_app"}:
        from .app_interfaces import NativeContractApp, mark_native_contract_app, native_contract_app

        mapping = {
            "NativeContractApp": NativeContractApp,
            "native_contract_app": native_contract_app,
            "mark_native_contract_app": mark_native_contract_app,
        }
        return mapping[name]
    if name == "StaticFilesApp":
        from .static import StaticFilesApp

        return StaticFilesApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
