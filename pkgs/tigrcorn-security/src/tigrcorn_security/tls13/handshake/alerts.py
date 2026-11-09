from __future__ import annotations

from .imports import *

class AlertDescription:
    UNEXPECTED_MESSAGE = 10
    HANDSHAKE_FAILURE = 40
    BAD_CERTIFICATE = 42
    UNSUPPORTED_CERTIFICATE = 43
    CERTIFICATE_EXPIRED = 45
    CERTIFICATE_UNKNOWN = 46
    ILLEGAL_PARAMETER = 47
    UNKNOWN_CA = 48
    DECODE_ERROR = 50
    DECRYPT_ERROR = 51
    PROTOCOL_VERSION = 70
    INTERNAL_ERROR = 80
    MISSING_EXTENSION = 109
    CERTIFICATE_REQUIRED = 116


class TlsAlertError(ProtocolError):
    def __init__(self, description: int, message: str) -> None:
        super().__init__(message)
        self.description = description
        self.quic_error_code = _QUIC_TLS_ALERT_BASE + description


class QuicTransportError(ProtocolError):
    def __init__(self, error_code: int, message: str) -> None:
        super().__init__(message)
        self.quic_error_code = error_code

__all__ = [name for name in globals() if not name.startswith('__')]
