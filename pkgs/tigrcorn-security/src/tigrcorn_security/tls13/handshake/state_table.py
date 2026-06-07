from __future__ import annotations

from .imports import *

def tls13_handshake_state_table() -> tuple[dict[str, object], ...]:
    return tuple(dict(entry) for entry in TLS13_HANDSHAKE_STATE_TABLE)

__all__ = [name for name in globals() if not name.startswith('__')]
