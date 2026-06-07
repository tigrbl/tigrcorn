from __future__ import annotations

from .imports import *
from .models import *
from .vectors import *

def encode_early_data(message_context: str, max_early_data_size: int = QUIC_EARLY_DATA_SENTINEL) -> bytes:
    if message_context in {'client_hello', 'encrypted_extensions'}:
        return b''
    if message_context == 'new_session_ticket':
        return max_early_data_size.to_bytes(4, 'big')
    raise ValueError(f'unsupported early_data context: {message_context}')



def decode_early_data(data: bytes, message_context: str) -> object:
    if message_context in {'client_hello', 'encrypted_extensions'}:
        if data:
            raise ProtocolError('early_data extension must be empty in this context')
        return True
    if message_context == 'new_session_ticket':
        if len(data) != 4:
            raise ProtocolError('invalid early_data NewSessionTicket extension')
        return int.from_bytes(data, 'big')
    return data



def encode_pre_shared_key_client(identities: Sequence[PskIdentity], binders: Sequence[bytes]) -> bytes:
    if len(identities) != len(binders):
        raise ValueError('PSK identities and binders must have matching counts')
    identities_payload = bytearray()
    binders_payload = bytearray()
    for identity, binder in zip(identities, binders):
        identities_payload.extend(_u16_vector(identity.identity))
        identities_payload.extend(identity.obfuscated_ticket_age.to_bytes(4, 'big'))
        binders_payload.extend(_u8_vector(binder))
    return _u16_vector(bytes(identities_payload)) + _u16_vector(bytes(binders_payload))



def encode_pre_shared_key_client_without_binders(identities: Sequence[PskIdentity]) -> bytes:
    identities_payload = bytearray()
    for identity in identities:
        identities_payload.extend(_u16_vector(identity.identity))
        identities_payload.extend(identity.obfuscated_ticket_age.to_bytes(4, 'big'))
    return _u16_vector(bytes(identities_payload))



def decode_pre_shared_key_client(data: bytes) -> OfferedPsks:
    identities_raw, offset = _read_u16_vector(data, 0)
    binders_raw, offset = _read_u16_vector(data, offset)
    if offset != len(data):
        raise ProtocolError('invalid pre_shared_key extension')
    identities: list[PskIdentity] = []
    inner = 0
    while inner < len(identities_raw):
        identity, inner = _read_u16_vector(identities_raw, inner)
        obfuscated_ticket_age, inner = _read_u32(identities_raw, inner)
        identities.append(PskIdentity(identity=identity, obfuscated_ticket_age=obfuscated_ticket_age))
    binders: list[bytes] = []
    inner = 0
    while inner < len(binders_raw):
        binder, inner = _read_u8_vector(binders_raw, inner)
        binders.append(binder)
    if len(identities) != len(binders):
        raise ProtocolError('mismatched PSK identities and binders')
    return OfferedPsks(identities=tuple(identities), binders=tuple(binders))



def encode_pre_shared_key_server(selected_identity: int) -> bytes:
    return selected_identity.to_bytes(2, 'big')



def decode_pre_shared_key_server(data: bytes) -> int:
    if len(data) != 2:
        raise ProtocolError('invalid server pre_shared_key extension')
    return int.from_bytes(data, 'big')

__all__ = [name for name in globals() if not name.startswith('__')]
