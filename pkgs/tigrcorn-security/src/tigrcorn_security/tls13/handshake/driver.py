from __future__ import annotations

from .base import _QuicTlsHandshakeBase
from .server import _QuicTlsServerHandshakeMixin
from .client import _QuicTlsClientHandshakeMixin
from .io import _QuicTlsMessageIoMixin


class QuicTlsHandshakeDriver(
    _QuicTlsMessageIoMixin,
    _QuicTlsClientHandshakeMixin,
    _QuicTlsServerHandshakeMixin,
    _QuicTlsHandshakeBase,
):
    pass


__all__ = ['QuicTlsHandshakeDriver']
