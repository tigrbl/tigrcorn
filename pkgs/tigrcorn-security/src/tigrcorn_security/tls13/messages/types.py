from __future__ import annotations

from .imports import *

class HandshakeType(IntEnum):
    CLIENT_HELLO = 1
    SERVER_HELLO = 2
    NEW_SESSION_TICKET = 4
    END_OF_EARLY_DATA = 5
    ENCRYPTED_EXTENSIONS = 8
    CERTIFICATE = 11
    CERTIFICATE_REQUEST = 13
    CERTIFICATE_VERIFY = 15
    FINISHED = 20
    KEY_UPDATE = 24
    MESSAGE_HASH = 254


class NeedMoreData(ProtocolError):
    pass

__all__ = [name for name in globals() if not name.startswith('__')]
