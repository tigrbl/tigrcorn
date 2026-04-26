from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar, Sequence

from tigrcorn.errors import ProtocolError
from tigrcorn.security.tls13.extensions import (
    ExtensionType,
    TlsExtension,
    TLS_LEGACY_VERSION,
    encode_extensions,
    decode_extensions,
)

HELLO_RETRY_REQUEST_RANDOM = bytes.fromhex(
    'CF21AD74E59A6111BE1D8C021E65B891'
    'C2A211167ABB8C5E079E09E2C8A8339C'
)


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



def _u8_vector(payload: bytes) -> bytes:
    if len(payload) > 255:
        raise ValueError('u8 vector too large')
    return bytes([len(payload)]) + payload



def _u16_vector(payload: bytes) -> bytes:
    if len(payload) > 0xFFFF:
        raise ValueError('u16 vector too large')
    return len(payload).to_bytes(2, 'big') + payload



def _u24_vector(payload: bytes) -> bytes:
    if len(payload) > 0xFFFFFF:
        raise ValueError('u24 vector too large')
    return len(payload).to_bytes(3, 'big') + payload



def _read_exact(data: bytes, offset: int, length: int) -> tuple[bytes, int]:
    end = offset + length
    if end > len(data):
        raise NeedMoreData('incomplete TLS handshake payload')
    return data[offset:end], end



def _read_u8(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 1)
    return raw[0], offset



def _read_u16(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 2)
    return int.from_bytes(raw, 'big'), offset



def _read_u24(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 3)
    return int.from_bytes(raw, 'big'), offset



def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 4)
    return int.from_bytes(raw, 'big'), offset



def _read_u8_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u8(data, offset)
    return _read_exact(data, offset, length)



def _read_u16_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u16(data, offset)
    return _read_exact(data, offset, length)



def _read_u24_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u24(data, offset)
    return _read_exact(data, offset, length)


@dataclass(slots=True)
class HandshakeMessage:
    handshake_type: ClassVar[int]

    def encode_body(self, **kwargs) -> bytes:
        raise NotImplementedError

    def encode(self, **kwargs) -> bytes:
        body = self.encode_body(**kwargs)
        return bytes([self.handshake_type]) + len(body).to_bytes(3, 'big') + body


@dataclass(slots=True)
class ClientHello(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.CLIENT_HELLO
    random: bytes = field(default_factory=lambda: os.urandom(32))
    legacy_session_id: bytes = field(default_factory=lambda: os.urandom(32))
    cipher_suites: tuple[int, ...] = ()
    compression_methods: bytes = b'\x00'
    extensions: tuple[TlsExtension, ...] = ()
    legacy_version: int = TLS_LEGACY_VERSION

    def encode_body(self, *, message_context: str = 'client_hello', **kwargs) -> bytes:
        if len(self.random) != 32:
            raise ValueError('ClientHello.random must be 32 bytes')
        if len(self.legacy_session_id) > 32:
            raise ValueError('legacy_session_id must be <= 32 bytes')
        cipher_payload = b''.join(cipher_suite.to_bytes(2, 'big') for cipher_suite in self.cipher_suites)
        if len(cipher_payload) < 2:
            raise ValueError('at least one cipher suite is required')
        return (
            self.legacy_version.to_bytes(2, 'big')
            + self.random
            + _u8_vector(self.legacy_session_id)
            + _u16_vector(cipher_payload)
            + _u8_vector(self.compression_methods)
            + encode_extensions(self.extensions, message_context=message_context)
        )

    @classmethod
    def decode_body(cls, body: bytes) -> 'ClientHello':
        legacy_version, offset = _read_u16(body, 0)
        random, offset = _read_exact(body, offset, 32)
        legacy_session_id, offset = _read_u8_vector(body, offset)
        cipher_suites_raw, offset = _read_u16_vector(body, offset)
        compression_methods, offset = _read_u8_vector(body, offset)
        extensions = decode_extensions(body[offset:], message_context='client_hello')
        if len(cipher_suites_raw) % 2:
            raise ProtocolError('invalid cipher_suites vector in ClientHello')
        cipher_suites = tuple(int.from_bytes(cipher_suites_raw[index:index + 2], 'big') for index in range(0, len(cipher_suites_raw), 2))
        return cls(
            random=random,
            legacy_session_id=legacy_session_id,
            cipher_suites=cipher_suites,
            compression_methods=compression_methods,
            extensions=extensions,
            legacy_version=legacy_version,
        )

    def with_extensions(self, extensions: Sequence[TlsExtension]) -> 'ClientHello':
        return ClientHello(
            random=self.random,
            legacy_session_id=self.legacy_session_id,
            cipher_suites=self.cipher_suites,
            compression_methods=self.compression_methods,
            extensions=tuple(extensions),
            legacy_version=self.legacy_version,
        )


@dataclass(slots=True)
class ServerHello(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.SERVER_HELLO
    random: bytes
    legacy_session_id_echo: bytes
    cipher_suite: int
    extensions: tuple[TlsExtension, ...]
    legacy_version: int = TLS_LEGACY_VERSION
    legacy_compression_method: int = 0

    def encode_body(self, *, message_context: str = 'server_hello', **kwargs) -> bytes:
        if len(self.random) != 32:
            raise ValueError('ServerHello.random must be 32 bytes')
        return (
            self.legacy_version.to_bytes(2, 'big')
            + self.random
            + _u8_vector(self.legacy_session_id_echo)
            + self.cipher_suite.to_bytes(2, 'big')
            + bytes([self.legacy_compression_method])
            + encode_extensions(self.extensions, message_context=message_context)
        )

    @property
    def is_hello_retry_request(self) -> bool:
        return self.random == HELLO_RETRY_REQUEST_RANDOM

    @classmethod
    def decode_body(cls, body: bytes) -> 'ServerHello':
        legacy_version, offset = _read_u16(body, 0)
        random, offset = _read_exact(body, offset, 32)
        legacy_session_id_echo, offset = _read_u8_vector(body, offset)
        cipher_suite, offset = _read_u16(body, offset)
        legacy_compression_method, offset = _read_u8(body, offset)
        context = 'hello_retry_request' if random == HELLO_RETRY_REQUEST_RANDOM else 'server_hello'
        extensions = decode_extensions(body[offset:], message_context=context)
        return cls(
            random=random,
            legacy_session_id_echo=legacy_session_id_echo,
            cipher_suite=cipher_suite,
            extensions=extensions,
            legacy_version=legacy_version,
            legacy_compression_method=legacy_compression_method,
        )


@dataclass(slots=True)
class EncryptedExtensions(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.ENCRYPTED_EXTENSIONS
    extensions: tuple[TlsExtension, ...]

    def encode_body(self, *, message_context: str = 'encrypted_extensions', **kwargs) -> bytes:
        return encode_extensions(self.extensions, message_context=message_context)

    @classmethod
    def decode_body(cls, body: bytes) -> 'EncryptedExtensions':
        return cls(extensions=decode_extensions(body, message_context='encrypted_extensions'))


@dataclass(slots=True)
class CertificateRequest(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.CERTIFICATE_REQUEST
    request_context: bytes = b''
    extensions: tuple[TlsExtension, ...] = ()

    def encode_body(self, *, message_context: str = 'certificate_request', **kwargs) -> bytes:
        return _u8_vector(self.request_context) + encode_extensions(self.extensions, message_context=message_context)

    @classmethod
    def decode_body(cls, body: bytes) -> 'CertificateRequest':
        request_context, offset = _read_u8_vector(body, 0)
        return cls(request_context=request_context, extensions=decode_extensions(body[offset:], message_context='certificate_request'))


@dataclass(slots=True)
class CertificateEntry:
    cert_data: bytes
    extensions: tuple[TlsExtension, ...] = ()

    def encode(self) -> bytes:
        return _u24_vector(self.cert_data) + encode_extensions(self.extensions, message_context='certificate_entry')

    @classmethod
    def decode(cls, data: bytes, offset: int) -> tuple['CertificateEntry', int]:
        cert_data, offset = _read_u24_vector(data, offset)
        extensions_raw, offset = _read_u16_vector(data, offset)
        extensions = decode_extensions(len(extensions_raw).to_bytes(2, 'big') + extensions_raw, message_context='certificate_entry')
        return cls(cert_data=cert_data, extensions=extensions), offset


@dataclass(slots=True)
class Certificate(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.CERTIFICATE
    request_context: bytes = b''
    certificate_list: tuple[CertificateEntry, ...] = ()

    def encode_body(self, **kwargs) -> bytes:
        payload = bytearray()
        for entry in self.certificate_list:
            payload.extend(entry.encode())
        return _u8_vector(self.request_context) + _u24_vector(bytes(payload))

    @classmethod
    def decode_body(cls, body: bytes) -> 'Certificate':
        request_context, offset = _read_u8_vector(body, 0)
        certificate_list_raw, offset = _read_u24_vector(body, offset)
        if offset != len(body):
            raise ProtocolError('invalid Certificate message length')
        inner = 0
        entries: list[CertificateEntry] = []
        while inner < len(certificate_list_raw):
            entry, inner = CertificateEntry.decode(certificate_list_raw, inner)
            entries.append(entry)
        return cls(request_context=request_context, certificate_list=tuple(entries))


@dataclass(slots=True)
class CertificateVerify(HandshakeMessage):
    handshake_type: ClassVar[int] = HandshakeType.CERTIFICATE_VERIFY
    algorithm: int
    signature: bytes

    def encode_body(self, **kwargs) -> bytes:
        return self.algorithm.to_bytes(2, 'big') + _u16_vector(self.signature)

    @classmethod
    def decode_body(cls, body: bytes) -> 'CertificateVerify':
        algorithm, offset = _read_u16(body, 0)
        signature, offset = _read_u16_vector(body, offset)
        if offset != len(body):
            raise ProtocolError('invalid CertificateVerify message')
        return cls(algorithm=algorithm, signature=signature)


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
