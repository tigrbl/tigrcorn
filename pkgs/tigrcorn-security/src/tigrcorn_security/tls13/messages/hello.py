from __future__ import annotations

from .imports import *
from .types import *
from .vectors import *
from .base import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
