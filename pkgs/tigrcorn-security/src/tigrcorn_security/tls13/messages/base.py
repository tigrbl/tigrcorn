from __future__ import annotations

from .imports import *
from .types import *

@dataclass(slots=True)
class HandshakeMessage:
    handshake_type: ClassVar[int]

    def encode_body(self, **kwargs) -> bytes:
        raise NotImplementedError

    def encode(self, **kwargs) -> bytes:
        body = self.encode_body(**kwargs)
        return bytes([self.handshake_type]) + len(body).to_bytes(3, 'big') + body

__all__ = [name for name in globals() if not name.startswith('__')]
