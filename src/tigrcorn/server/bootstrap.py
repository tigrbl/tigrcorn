from __future__ import annotations

"""Compatibility shim for runtime bootstrap.

Optional uvloop errors are owned by tigrcorn_runtime.server.bootstrap and must
continue to mention tigrcorn[runtime-uvloop].
"""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module('tigrcorn_runtime.server.bootstrap')
_sys.modules[__name__] = _module
