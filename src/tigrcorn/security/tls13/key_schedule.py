from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from tigrcorn.security.tls13.transcript import HandshakeTranscript
from tigrcorn.transports.quic.crypto import hkdf_expand_label, hkdf_extract


@dataclass(slots=True)
class TrafficSecrets:
    client_handshake_traffic_secret: bytes
    server_handshake_traffic_secret: bytes
    client_application_traffic_secret: bytes
    server_application_traffic_secret: bytes
    client_early_traffic_secret: bytes | None = None
    exporter_master_secret: bytes | None = None
    resumption_master_secret: bytes | None = None


class Tls13KeySchedule:
    def __init__(self, *, hash_name: str = 'sha256') -> None:
        self.hash_name = hash_name
        self.hash_length = hashlib.new(hash_name).digest_size

    def hash_empty(self) -> bytes:
        return hashlib.new(self.hash_name).digest()

    def transcript_hash(self, transcript: HandshakeTranscript | bytes) -> bytes:
        if isinstance(transcript, HandshakeTranscript):
            return transcript.digest()
        return hashlib.new(self.hash_name, transcript).digest()

    def extract(self, salt: bytes, ikm: bytes) -> bytes:
        return hkdf_extract(salt, ikm, hash_name=self.hash_name)

    def expand_label(self, secret: bytes, label: bytes | str, context: bytes = b'', length: int | None = None) -> bytes:
        return hkdf_expand_label(
            secret,
            label,
            context,
            self.hash_length if length is None else length,
            hash_name=self.hash_name,
        )

    def derive_secret(self, secret: bytes, label: bytes | str, transcript: HandshakeTranscript | bytes | None = None) -> bytes:
        if transcript is None:
            context = self.hash_empty()
        else:
            context = self.transcript_hash(transcript)
        return self.expand_label(secret, label, context, self.hash_length)

    def zero_secret(self) -> bytes:
        return b'\x00' * self.hash_length

    def make_early_secret(self, psk: bytes | None) -> bytes:
        ikm = self.zero_secret() if psk is None else psk
        return self.extract(self.zero_secret(), ikm)

    def make_binder_key(self, early_secret: bytes, *, external: bool = False) -> bytes:
        label = 'ext binder' if external else 'res binder'
        return self.derive_secret(early_secret, label)

    def client_early_traffic_secret(self, early_secret: bytes, transcript: HandshakeTranscript | bytes) -> bytes:
        return self.derive_secret(early_secret, 'c e traffic', transcript)

    def handshake_secret(self, early_secret: bytes, shared_secret: bytes) -> bytes:
        derived = self.derive_secret(early_secret, 'derived')
        return self.extract(derived, shared_secret)

    def handshake_traffic_secrets(self, handshake_secret: bytes, transcript: HandshakeTranscript | bytes) -> tuple[bytes, bytes]:
        return (
            self.derive_secret(handshake_secret, 'c hs traffic', transcript),
            self.derive_secret(handshake_secret, 's hs traffic', transcript),
        )

    def finished_key(self, base_key: bytes) -> bytes:
        return self.expand_label(base_key, 'finished', b'', self.hash_length)

    def finished_verify_data(self, base_key: bytes, transcript: HandshakeTranscript | bytes) -> bytes:
        return hmac.new(self.finished_key(base_key), self.transcript_hash(transcript), getattr(hashlib, self.hash_name)).digest()

    def verify_finished(self, verify_data: bytes, *, base_key: bytes, transcript: HandshakeTranscript | bytes) -> bool:
        expected = self.finished_verify_data(base_key, transcript)
        return hmac.compare_digest(expected, verify_data)

    def master_secret(self, handshake_secret: bytes) -> bytes:
        derived = self.derive_secret(handshake_secret, 'derived')
        return self.extract(derived, self.zero_secret())

    def application_traffic_secrets(self, master_secret: bytes, transcript: HandshakeTranscript | bytes) -> tuple[bytes, bytes]:
        return (
            self.derive_secret(master_secret, 'c ap traffic', transcript),
            self.derive_secret(master_secret, 's ap traffic', transcript),
        )

    def exporter_master_secret(self, master_secret: bytes, transcript: HandshakeTranscript | bytes) -> bytes:
        return self.derive_secret(master_secret, 'exp master', transcript)

    def resumption_master_secret(self, master_secret: bytes, transcript: HandshakeTranscript | bytes) -> bytes:
        return self.derive_secret(master_secret, 'res master', transcript)

    def resumption_psk(self, resumption_master_secret: bytes, ticket_nonce: bytes) -> bytes:
        return self.expand_label(resumption_master_secret, 'resumption', ticket_nonce, self.hash_length)

    def update_application_traffic_secret(self, traffic_secret: bytes) -> bytes:
        return self.expand_label(traffic_secret, 'traffic upd', b'', self.hash_length)
