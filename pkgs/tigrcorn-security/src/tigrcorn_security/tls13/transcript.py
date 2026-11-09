from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from tigrcorn_security.tls13.messages import SyntheticMessageHash


@dataclass(slots=True)
class HandshakeTranscript:
    hash_name: str = 'sha256'
    _messages: bytearray = field(default_factory=bytearray)

    @property
    def hash_length(self) -> int:
        return hashlib.new(self.hash_name).digest_size

    def copy(self) -> 'HandshakeTranscript':
        transcript = HandshakeTranscript(hash_name=self.hash_name)
        transcript._messages.extend(self._messages)
        return transcript

    def clear(self) -> None:
        self._messages.clear()

    def append(self, encoded_handshake_message: bytes) -> None:
        self._messages.extend(encoded_handshake_message)

    def extend(self, encoded_handshake_messages: bytes) -> None:
        self._messages.extend(encoded_handshake_messages)

    def digest(self) -> bytes:
        hasher = hashlib.new(self.hash_name)
        hasher.update(self._messages)
        return hasher.digest()

    def digest_with(self, *encoded_handshake_messages: bytes) -> bytes:
        hasher = hashlib.new(self.hash_name)
        hasher.update(self._messages)
        for message in encoded_handshake_messages:
            hasher.update(message)
        return hasher.digest()

    def as_bytes(self) -> bytes:
        return bytes(self._messages)

    def reset_with_message_hash(self, encoded_client_hello: bytes) -> None:
        digest = hashlib.new(self.hash_name, encoded_client_hello).digest()
        synthetic = SyntheticMessageHash(digest=digest).encode()
        self._messages.clear()
        self._messages.extend(synthetic)
