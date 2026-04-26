from __future__ import annotations

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module('tigrcorn_asgi.extensions.websocket_denial')
_sys.modules[__name__] = _module
