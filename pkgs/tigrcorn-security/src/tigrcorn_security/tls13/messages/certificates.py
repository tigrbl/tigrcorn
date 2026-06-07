from __future__ import annotations

from .imports import *
from .types import *
from .vectors import *
from .base import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
