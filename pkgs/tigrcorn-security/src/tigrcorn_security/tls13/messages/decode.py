from __future__ import annotations

from .imports import *
from .types import *
from .vectors import *
from .base import *
from .hello import *
from .certificates import *
from .finished import *

_HANDSHAKE_DECODERS: dict[int, type[HandshakeMessage]] = {
    HandshakeType.CLIENT_HELLO: ClientHello,
    HandshakeType.SERVER_HELLO: ServerHello,
    HandshakeType.NEW_SESSION_TICKET: NewSessionTicket,
    HandshakeType.ENCRYPTED_EXTENSIONS: EncryptedExtensions,
    HandshakeType.CERTIFICATE_REQUEST: CertificateRequest,
    HandshakeType.CERTIFICATE: Certificate,
    HandshakeType.CERTIFICATE_VERIFY: CertificateVerify,
    HandshakeType.FINISHED: Finished,
    HandshakeType.KEY_UPDATE: KeyUpdate,
}

def decode_handshake_message(data: bytes, offset: int = 0) -> tuple[HandshakeMessage, int]:
    handshake_type_raw, next_offset = _read_u8(data, offset)
    body_length, next_offset = _read_u24(data, next_offset)
    body, next_offset = _read_exact(data, next_offset, body_length)
    decoder = _HANDSHAKE_DECODERS.get(handshake_type_raw)
    if decoder is None:
        message: HandshakeMessage = UnknownHandshake(handshake_type=handshake_type_raw, body=body)
    else:
        message = decoder.decode_body(body)  # type: ignore[attr-defined]
    return message, next_offset



def decode_handshake_messages(data: bytes) -> tuple[HandshakeMessage, ...]:
    messages: list[HandshakeMessage] = []
    offset = 0
    while offset < len(data):
        message, offset = decode_handshake_message(data, offset)
        messages.append(message)
    return tuple(messages)

__all__ = [name for name in globals() if not name.startswith('__')]
