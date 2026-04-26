__all__ = ["TigrCornServer"]


def __getattr__(name: str):
    if name == "TigrCornServer":
        from .runner import TigrCornServer

        return TigrCornServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
