from __future__ import annotations


class TigrCornError(Exception):
    """Base exception for the package."""


class ConfigError(TigrCornError):
    """Raised for invalid configuration."""


class AppLoadError(TigrCornError):
    """Raised when an ASGI application cannot be imported."""


class ProtocolError(TigrCornError):
    """Raised when the wire protocol is malformed or unsupported."""


class UnsupportedFeature(TigrCornError):
    """Raised when a requested feature or protocol is not implemented."""


class ServerError(TigrCornError):
    """Raised for server lifecycle errors."""


__all__ = [
    "AppLoadError",
    "ConfigError",
    "ProtocolError",
    "ServerError",
    "TigrCornError",
    "UnsupportedFeature",
]
