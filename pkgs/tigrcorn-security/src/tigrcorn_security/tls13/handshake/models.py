from __future__ import annotations

from .imports import *

def _ticket_b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _ticket_unb64(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _normalize_serialized_ticket_payload(payload: dict[str, object]) -> dict[str, object]:
    if 'version' in payload:
        return payload
    if 'v' in payload:
        return {
            'version': int(payload.get('v', 1)),
            'issued_at': int(payload['i']),
            'ticket_lifetime': int(payload['l']),
            'ticket_age_add': int(payload['a']),
            'ticket_nonce': str(payload['n']),
            'server_name': str(payload['s']),
            'alpn': str(payload['h']),
            'transport_parameters': str(payload['p']),
            'cipher_suite': int(payload.get('c', CIPHER_TLS_AES_128_GCM_SHA256)),
            'resumption_secret': str(payload['r']),
            'max_early_data_size': int(payload.get('e', 0)),
        }
    return payload


@dataclass(slots=True)
class HandshakeFlight:
    packet_space: str
    data: bytes


@dataclass(slots=True)
class QuicTrafficSecrets:
    client_handshake_secret: bytes
    server_handshake_secret: bytes
    client_application_secret: bytes
    server_application_secret: bytes
    client_early_secret: bytes | None = None
    exporter_master_secret: bytes | None = None
    resumption_master_secret: bytes | None = None


@dataclass(slots=True)
class QuicSessionTicket:
    ticket: bytes
    resumption_secret: bytes
    server_name: str
    alpn: str
    transport_parameters: TransportParameters
    ticket_age_add: int
    ticket_nonce: bytes
    ticket_lifetime: int
    issued_at: int
    cipher_suite: int = CIPHER_TLS_AES_128_GCM_SHA256
    max_early_data_size: int = 0

    def serialize(self) -> bytes:
        payload = {
            'ticket': _ticket_b64(self.ticket),
            'resumption_secret': _ticket_b64(self.resumption_secret),
            'server_name': self.server_name,
            'alpn': self.alpn,
            'transport_parameters': _ticket_b64(self.transport_parameters.to_bytes()),
            'ticket_age_add': self.ticket_age_add,
            'ticket_nonce': _ticket_b64(self.ticket_nonce),
            'ticket_lifetime': self.ticket_lifetime,
            'issued_at': self.issued_at,
            'cipher_suite': self.cipher_suite,
            'max_early_data_size': self.max_early_data_size,
        }
        return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')

    @classmethod
    def deserialize(cls, data: bytes) -> 'QuicSessionTicket':
        payload = json.loads(data.decode('utf-8'))
        payload = _normalize_serialized_ticket_payload(payload)
        return cls(
            ticket=_ticket_unb64(str(payload['ticket'])),
            resumption_secret=_ticket_unb64(str(payload['resumption_secret'])),
            server_name=str(payload['server_name']),
            alpn=str(payload['alpn']),
            transport_parameters=TransportParameters.from_bytes(_ticket_unb64(str(payload['transport_parameters']))),
            ticket_age_add=int(payload['ticket_age_add']),
            ticket_nonce=_ticket_unb64(str(payload['ticket_nonce'])),
            ticket_lifetime=int(payload['ticket_lifetime']),
            issued_at=int(payload['issued_at']),
            cipher_suite=int(payload.get('cipher_suite', CIPHER_TLS_AES_128_GCM_SHA256)),
            max_early_data_size=int(payload.get('max_early_data_size', 0)),
        )


_REPLAY_CACHE: dict[bytes, int] = {}

__all__ = [name for name in globals() if not name.startswith('__')]
