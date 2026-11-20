from __future__ import annotations


class TigrCornError(Exception):
    """Base exception for the package."""


class ConfigError(TigrCornError):
    """Raised for invalid configuration."""


class AppLoadError(TigrCornError):
    """Raised when an ASGI application cannot be imported."""


class ProtocolError(TigrCornError):
    """Raised when the wire protocol is malformed or unsupported."""


class RequestBodyTooLarge(ProtocolError):
    """Raised when request content exceeds the configured body limit."""


class UnsupportedFeature(TigrCornError):
    """Raised when a requested feature or protocol is not implemented."""


class ServerError(TigrCornError):
    """Raised for server lifecycle errors."""


__all__ = [
    "AppLoadError",
    "ConfigError",
    "ProtocolError",
    "RequestBodyTooLarge",
    "ServerError",
    "TigrCornError",
    "UnsupportedFeature",
]
