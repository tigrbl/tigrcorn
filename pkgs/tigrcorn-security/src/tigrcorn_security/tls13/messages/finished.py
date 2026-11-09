from __future__ import annotations

from .imports import *
from .types import *
from .vectors import *
from .base import *

@dataclass(slots=True)
class Finished(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.FINISHED
    verify_data: bytes

    def encode_body(self, **kwargs) -> bytes:
        return self.verify_data

    @classmethod
    def decode_body(cls, body: bytes) -> 'Finished':
        return cls(verify_data=body)


@dataclass(slots=True)
class NewSessionTicket(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.NEW_SESSION_TICKET
    ticket_lifetime: int
    ticket_age_add: int
    ticket_nonce: bytes
    ticket: bytes
    extensions: tuple[TlsExtension, ...] = ()

    def encode_body(self, **kwargs) -> bytes:
        return (
            self.ticket_lifetime.to_bytes(4, 'big')
            + self.ticket_age_add.to_bytes(4, 'big')
            + _u8_vector(self.ticket_nonce)
            + _u16_vector(self.ticket)
            + encode_extensions(self.extensions, message_context='new_session_ticket')
        )

    @classmethod
    def decode_body(cls, body: bytes) -> 'NewSessionTicket':
        ticket_lifetime, offset = _read_u32(body, 0)
        ticket_age_add, offset = _read_u32(body, offset)
        ticket_nonce, offset = _read_u8_vector(body, offset)
        ticket, offset = _read_u16_vector(body, offset)
        extensions = decode_extensions(body[offset:], message_context='new_session_ticket')
        return cls(
            ticket_lifetime=ticket_lifetime,
            ticket_age_add=ticket_age_add,
            ticket_nonce=ticket_nonce,
            ticket=ticket,
            extensions=extensions,
        )


@dataclass(slots=True)
class KeyUpdate(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.KEY_UPDATE
    request_update: int

    def encode_body(self, **kwargs) -> bytes:
        return bytes([self.request_update])

    @classmethod
    def decode_body(cls, body: bytes) -> 'KeyUpdate':
        if len(body) != 1:
            raise ProtocolError('invalid KeyUpdate message')
        return cls(request_update=body[0])


@dataclass(slots=True)
class SyntheticMessageHash(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.MESSAGE_HASH
    digest: bytes

    def encode_body(self, **kwargs) -> bytes:
        return self.digest


@dataclass(slots=True)
class UnknownHandshake(HandshakeMessage):
    handshake_type: int
    body: bytes

    def encode_body(self, **kwargs) -> bytes:
        return self.body

__all__ = [name for name in globals() if not name.startswith('__')]
