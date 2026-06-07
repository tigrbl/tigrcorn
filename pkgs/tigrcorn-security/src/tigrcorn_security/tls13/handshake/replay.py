from __future__ import annotations

from .imports import *
from .models import *

def _purge_replay_cache(now_ms: int) -> None:
    expired = [key for key, expiry in _REPLAY_CACHE.items() if expiry <= now_ms]
    for key in expired:
        _REPLAY_CACHE.pop(key, None)



def _claim_ticket_for_0rtt(ticket_identity: bytes, *, now_ms: int, ticket_lifetime: int) -> bool:
    _purge_replay_cache(now_ms)
    token = hashlib.sha256(ticket_identity).digest()
    expiry = now_ms + (ticket_lifetime * 1000)
    if token in _REPLAY_CACHE:
        return False
    _REPLAY_CACHE[token] = expiry
    return True

__all__ = [name for name in globals() if not name.startswith('__')]
