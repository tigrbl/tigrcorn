from __future__ import annotations


class CongestionControlError(RuntimeError):
    """Base error for the QUIC congestion-controller extension surface."""


class ProviderDiscoveryError(CongestionControlError):
    """Raised when a selected provider cannot be resolved unambiguously."""


class ProviderCompatibilityError(CongestionControlError):
    """Raised when provider metadata is incompatible with this API major."""


class ProviderConfigurationError(CongestionControlError):
    """Raised when provider options are invalid."""


class InvalidControllerOutput(CongestionControlError):
    """Raised when a provider returns unsafe or malformed send limits."""
