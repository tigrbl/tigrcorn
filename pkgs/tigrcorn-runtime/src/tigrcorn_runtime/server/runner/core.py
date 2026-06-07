from __future__ import annotations

from .base import _TigrCornServerBase
from .diagnostics import _TigrCornServerDiagnosticsMixin
from .lifecycle import _TigrCornServerLifecycleMixin
from .listeners import _TigrCornServerListenerMixin
from .client_handlers import _TigrCornServerClientHandlerMixin
from .http11 import _TigrCornServerHTTP11Mixin
from .http11_send import _TigrCornServerHTTP11SendMixin
from .http11_serve import _TigrCornServerHTTP11ServeMixin
from .metrics import _TigrCornServerMetricsMixin


class TigrCornServer(
    _TigrCornServerMetricsMixin,
    _TigrCornServerHTTP11ServeMixin,
    _TigrCornServerHTTP11SendMixin,
    _TigrCornServerHTTP11Mixin,
    _TigrCornServerClientHandlerMixin,
    _TigrCornServerListenerMixin,
    _TigrCornServerLifecycleMixin,
    _TigrCornServerDiagnosticsMixin,
    _TigrCornServerBase,
):
    pass


__all__ = ['TigrCornServer']
