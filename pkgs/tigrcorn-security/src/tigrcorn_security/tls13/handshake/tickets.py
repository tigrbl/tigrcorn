from __future__ import annotations

from .imports import *
from .models import *
from .utils import *

def _ticket_protection_key(private_key_pem: bytes | None, certificate_pem: bytes | None) -> bytes:
    material = private_key_pem or certificate_pem or b'tigrcorn-quic-tls13-ticket-key'
    return hashlib.sha256(b'tigrcorn-ticket-v1' + material).digest()



def _seal_ticket(ticket_key: bytes, payload: dict[str, object]) -> bytes:
    serialized = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    mac = hmac.new(ticket_key, serialized, hashlib.sha256).digest()
    return b'TGT1' + mac + serialized



def _normalize_ticket_payload(payload: dict[str, object]) -> dict[str, object]:
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



def _open_ticket(ticket_key: bytes, ticket: bytes) -> dict[str, object]:
    if not ticket.startswith(b'TGT1') or len(ticket) < 4 + 32:
        _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'invalid session ticket format')
    mac = ticket[4:36]
    serialized = ticket[36:]
    expected = hmac.new(ticket_key, serialized, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'session ticket integrity verification failed')
    return _normalize_ticket_payload(json.loads(serialized.decode('utf-8')))



def _session_ticket_from_payload(payload: dict[str, object], *, opaque_ticket: bytes) -> QuicSessionTicket:
    payload = _normalize_ticket_payload(payload)
    return QuicSessionTicket(
        ticket=opaque_ticket,
        resumption_secret=_unb64(str(payload['resumption_secret'])),
        server_name=str(payload['server_name']),
        alpn=str(payload['alpn']),
        transport_parameters=TransportParameters.from_bytes(_unb64(str(payload['transport_parameters']))),
        ticket_age_add=int(payload['ticket_age_add']),
        ticket_nonce=_unb64(str(payload['ticket_nonce'])),
        ticket_lifetime=int(payload['ticket_lifetime']),
        issued_at=int(payload['issued_at']),
        cipher_suite=int(payload.get('cipher_suite', CIPHER_TLS_AES_128_GCM_SHA256)),
        max_early_data_size=int(payload.get('max_early_data_size', 0)),
    )




def _client_hello_without_binders(full_client_hello: bytes, binders: Sequence[bytes]) -> bytes:
    binders_length = 2 + sum(1 + len(binder) for binder in binders)
    if binders_length <= 2 or binders_length > len(full_client_hello):
        raise ProtocolError('invalid ClientHello pre_shared_key binder vector')
    return full_client_hello[:-binders_length]

__all__ = [name for name in globals() if not name.startswith('__')]
