from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable, Sequence

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint

TLS_VERSION_1_3 = 0x0304
TLS_LEGACY_VERSION = 0x0303

CIPHER_TLS_AES_128_GCM_SHA256 = 0x1301
CIPHER_TLS_AES_256_GCM_SHA384 = 0x1302

GROUP_SECP256R1 = 0x0017
GROUP_X25519 = 0x001D

SIG_RSA_PKCS1_SHA256 = 0x0401
SIG_ECDSA_SECP256R1_SHA256 = 0x0403
SIG_RSA_PSS_RSAE_SHA256 = 0x0804
SIG_ED25519 = 0x0807
SIG_RSA_PSS_PSS_SHA256 = 0x0809

PSK_MODE_KE = 0
PSK_MODE_DHE_KE = 1

QUIC_EARLY_DATA_SENTINEL = 0xFFFFFFFF


class ExtensionType(IntEnum):
    SERVER_NAME = 0
    SUPPORTED_GROUPS = 10
    SIGNATURE_ALGORITHMS = 13
    ALPN = 16
    SIGNATURE_ALGORITHMS_CERT = 50
    PRE_SHARED_KEY = 41
    EARLY_DATA = 42
    SUPPORTED_VERSIONS = 43
    COOKIE = 44
    PSK_KEY_EXCHANGE_MODES = 45
    KEY_SHARE = 51
    QUIC_TRANSPORT_PARAMETERS = 57


@dataclass(slots=True)
class TlsExtension:
    extension_type: int
    value: object
    raw_data: bytes | None = None


@dataclass(slots=True)
class PskIdentity:
    identity: bytes
    obfuscated_ticket_age: int


@dataclass(slots=True)
class OfferedPsks:
    identities: tuple[PskIdentity, ...]
    binders: tuple[bytes, ...]


@dataclass(frozen=True, slots=True)
class CipherSuiteParameters:
    hash_name: str
    key_length: int
    hp_length: int
    iv_length: int = 12


_TP_ORIGINAL_DESTINATION_CONNECTION_ID = 0x00
_TP_MAX_IDLE_TIMEOUT = 0x01
_TP_STATELESS_RESET_TOKEN = 0x02
_TP_MAX_UDP_PAYLOAD_SIZE = 0x03
_TP_INITIAL_MAX_DATA = 0x04
_TP_INITIAL_MAX_STREAM_DATA_BIDI_LOCAL = 0x05
_TP_INITIAL_MAX_STREAM_DATA_BIDI_REMOTE = 0x06
_TP_INITIAL_MAX_STREAM_DATA_UNI = 0x07
_TP_INITIAL_MAX_STREAMS_BIDI = 0x08
_TP_INITIAL_MAX_STREAMS_UNI = 0x09
_TP_ACK_DELAY_EXPONENT = 0x0A
_TP_MAX_ACK_DELAY = 0x0B
_TP_DISABLE_ACTIVE_MIGRATION = 0x0C
_TP_PREFERRED_ADDRESS = 0x0D
_TP_ACTIVE_CONNECTION_ID_LIMIT = 0x0E
_TP_INITIAL_SOURCE_CONNECTION_ID = 0x0F
_TP_RETRY_SOURCE_CONNECTION_ID = 0x10


@dataclass(slots=True)
class TransportParameters:
    max_data: int = 65536
    max_stream_data_bidi_local: int = 65536
    max_stream_data_bidi_remote: int = 65536
    max_stream_data_uni: int = 65536
    max_streams_bidi: int = 128
    max_streams_uni: int = 128
    idle_timeout: int = 30000
    active_connection_id_limit: int = 4
    max_udp_payload_size: int = 1200
    ack_delay_exponent: int = 3
    max_ack_delay: int = 25
    disable_active_migration: bool = False
    original_destination_connection_id: bytes | None = None
    stateless_reset_token: bytes | None = None
    preferred_address: bytes | None = None
    initial_source_connection_id: bytes | None = None
    retry_source_connection_id: bytes | None = None
    unknown_parameters: dict[int, bytes] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.active_connection_id_limit < 2:
            raise ValueError('active_connection_id_limit must be at least 2')
        if self.ack_delay_exponent < 0:
            raise ValueError('ack_delay_exponent must be non-negative')
        if self.max_ack_delay < 0:
            raise ValueError('max_ack_delay must be non-negative')
        if self.max_udp_payload_size < 1200:
            raise ValueError('max_udp_payload_size must be at least 1200')
        if self.stateless_reset_token is not None and len(self.stateless_reset_token) != 16:
            raise ValueError('stateless_reset_token must be exactly 16 bytes')

    def to_bytes(self) -> bytes:
        payload = bytearray()

        def add_int(parameter_id: int, value: int | None) -> None:
            if value is None:
                return
            encoded = encode_quic_varint(value)
            payload.extend(encode_quic_varint(parameter_id))
            payload.extend(encode_quic_varint(len(encoded)))
            payload.extend(encoded)

        def add_bytes(parameter_id: int, value: bytes | None) -> None:
            if value is None:
                return
            payload.extend(encode_quic_varint(parameter_id))
            payload.extend(encode_quic_varint(len(value)))
            payload.extend(value)

        add_bytes(_TP_ORIGINAL_DESTINATION_CONNECTION_ID, self.original_destination_connection_id)
        add_int(_TP_MAX_IDLE_TIMEOUT, self.idle_timeout)
        add_bytes(_TP_STATELESS_RESET_TOKEN, self.stateless_reset_token)
        add_int(_TP_MAX_UDP_PAYLOAD_SIZE, self.max_udp_payload_size)
        add_int(_TP_INITIAL_MAX_DATA, self.max_data)
        add_int(_TP_INITIAL_MAX_STREAM_DATA_BIDI_LOCAL, self.max_stream_data_bidi_local)
        add_int(_TP_INITIAL_MAX_STREAM_DATA_BIDI_REMOTE, self.max_stream_data_bidi_remote)
        add_int(_TP_INITIAL_MAX_STREAM_DATA_UNI, self.max_stream_data_uni)
        add_int(_TP_INITIAL_MAX_STREAMS_BIDI, self.max_streams_bidi)
        add_int(_TP_INITIAL_MAX_STREAMS_UNI, self.max_streams_uni)
        add_int(_TP_ACK_DELAY_EXPONENT, self.ack_delay_exponent)
        add_int(_TP_MAX_ACK_DELAY, self.max_ack_delay)
        if self.disable_active_migration:
            payload.extend(encode_quic_varint(_TP_DISABLE_ACTIVE_MIGRATION))
            payload.extend(encode_quic_varint(0))
        add_bytes(_TP_PREFERRED_ADDRESS, self.preferred_address)
        add_int(_TP_ACTIVE_CONNECTION_ID_LIMIT, self.active_connection_id_limit)
        add_bytes(_TP_INITIAL_SOURCE_CONNECTION_ID, self.initial_source_connection_id)
        add_bytes(_TP_RETRY_SOURCE_CONNECTION_ID, self.retry_source_connection_id)
        for parameter_id, value in sorted(self.unknown_parameters.items()):
            payload.extend(encode_quic_varint(parameter_id))
            payload.extend(encode_quic_varint(len(value)))
            payload.extend(value)
        return bytes(payload)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'TransportParameters':
        values: dict[str, object] = {'unknown_parameters': {}}
        seen: set[int] = set()
        offset = 0
        while offset < len(data):
            parameter_id, offset = decode_quic_varint(data, offset)
            if parameter_id in seen:
                raise ProtocolError('duplicate QUIC transport parameter')
            seen.add(parameter_id)
            parameter_length, offset = decode_quic_varint(data, offset)
            end = offset + parameter_length
            if end > len(data):
                raise ProtocolError('truncated QUIC transport parameter')
            raw = data[offset:end]
            offset = end

            def decode_int(value: bytes) -> int:
                decoded, inner_offset = decode_quic_varint(value, 0)
                if inner_offset != len(value):
                    raise ProtocolError('invalid QUIC transport parameter encoding')
                return decoded

            if parameter_id == _TP_ORIGINAL_DESTINATION_CONNECTION_ID:
                values['original_destination_connection_id'] = raw
            elif parameter_id == _TP_MAX_IDLE_TIMEOUT:
                values['idle_timeout'] = decode_int(raw)
            elif parameter_id == _TP_STATELESS_RESET_TOKEN:
                if len(raw) != 16:
                    raise ProtocolError('stateless_reset_token transport parameter must be 16 bytes')
                values['stateless_reset_token'] = raw
            elif parameter_id == _TP_MAX_UDP_PAYLOAD_SIZE:
                values['max_udp_payload_size'] = decode_int(raw)
            elif parameter_id == _TP_INITIAL_MAX_DATA:
                values['max_data'] = decode_int(raw)
            elif parameter_id == _TP_INITIAL_MAX_STREAM_DATA_BIDI_LOCAL:
                values['max_stream_data_bidi_local'] = decode_int(raw)
            elif parameter_id == _TP_INITIAL_MAX_STREAM_DATA_BIDI_REMOTE:
                values['max_stream_data_bidi_remote'] = decode_int(raw)
            elif parameter_id == _TP_INITIAL_MAX_STREAM_DATA_UNI:
                values['max_stream_data_uni'] = decode_int(raw)
            elif parameter_id == _TP_INITIAL_MAX_STREAMS_BIDI:
                values['max_streams_bidi'] = decode_int(raw)
            elif parameter_id == _TP_INITIAL_MAX_STREAMS_UNI:
                values['max_streams_uni'] = decode_int(raw)
            elif parameter_id == _TP_ACK_DELAY_EXPONENT:
                values['ack_delay_exponent'] = decode_int(raw)
            elif parameter_id == _TP_MAX_ACK_DELAY:
                values['max_ack_delay'] = decode_int(raw)
            elif parameter_id == _TP_DISABLE_ACTIVE_MIGRATION:
                if raw:
                    raise ProtocolError('disable_active_migration transport parameter must be empty')
                values['disable_active_migration'] = True
            elif parameter_id == _TP_PREFERRED_ADDRESS:
                values['preferred_address'] = raw
            elif parameter_id == _TP_ACTIVE_CONNECTION_ID_LIMIT:
                values['active_connection_id_limit'] = decode_int(raw)
            elif parameter_id == _TP_INITIAL_SOURCE_CONNECTION_ID:
                values['initial_source_connection_id'] = raw
            elif parameter_id == _TP_RETRY_SOURCE_CONNECTION_ID:
                values['retry_source_connection_id'] = raw
            else:
                values['unknown_parameters'][parameter_id] = raw
        return cls(**values)

    def is_0rtt_compatible_with(self, current: 'TransportParameters') -> bool:
        return (
            current.max_data >= self.max_data
            and current.max_stream_data_bidi_local >= self.max_stream_data_bidi_local
            and current.max_stream_data_bidi_remote >= self.max_stream_data_bidi_remote
            and current.max_stream_data_uni >= self.max_stream_data_uni
            and current.max_streams_bidi >= self.max_streams_bidi
            and current.max_streams_uni >= self.max_streams_uni
            and current.max_udp_payload_size >= self.max_udp_payload_size
            and current.active_connection_id_limit >= self.active_connection_id_limit
            and current.ack_delay_exponent == self.ack_delay_exponent
            and current.max_ack_delay == self.max_ack_delay
            and current.disable_active_migration == self.disable_active_migration
        )


SUPPORTED_SIGNATURE_SCHEMES = (
    SIG_ED25519,
    SIG_RSA_PSS_RSAE_SHA256,
    SIG_RSA_PSS_PSS_SHA256,
    SIG_ECDSA_SECP256R1_SHA256,
)
SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES = (
    SIG_ED25519,
    SIG_RSA_PSS_RSAE_SHA256,
    SIG_RSA_PSS_PSS_SHA256,
    SIG_ECDSA_SECP256R1_SHA256,
    SIG_RSA_PKCS1_SHA256,
)
SUPPORTED_GROUPS = (
    GROUP_X25519,
    GROUP_SECP256R1,
)

_CIPHER_SUITE_PARAMETERS = {
    CIPHER_TLS_AES_256_GCM_SHA384: CipherSuiteParameters(hash_name='sha384', key_length=32, hp_length=32),
    CIPHER_TLS_AES_128_GCM_SHA256: CipherSuiteParameters(hash_name='sha256', key_length=16, hp_length=16),
}

SUPPORTED_CIPHER_SUITES = tuple(_CIPHER_SUITE_PARAMETERS)
_CIPHER_SUITE_NAMES = {
    CIPHER_TLS_AES_128_GCM_SHA256: 'TLS_AES_128_GCM_SHA256',
    CIPHER_TLS_AES_256_GCM_SHA384: 'TLS_AES_256_GCM_SHA384',
}
_CIPHER_SUITE_NAME_TO_ID = {value: key for key, value in _CIPHER_SUITE_NAMES.items()}


def cipher_suite_name(cipher_suite: int) -> str:
    return _CIPHER_SUITE_NAMES.get(cipher_suite, f'0x{cipher_suite:04x}')


def parse_cipher_suite_allowlist(value: str | None) -> tuple[int, ...]:
    if value is None:
        return ()
    tokens = [token.strip() for token in value.replace(',', ':').split(':') if token.strip()]
    if not tokens:
        raise ProtocolError('ssl_ciphers must contain at least one supported TLS 1.3 cipher suite')
    resolved: list[int] = []
    for token in tokens:
        cipher_suite = _CIPHER_SUITE_NAME_TO_ID.get(token)
        if cipher_suite is None:
            raise ProtocolError(f'unsupported TLS cipher suite: {token!r}')
        if cipher_suite not in resolved:
            resolved.append(cipher_suite)
    return tuple(resolved)


def format_cipher_suite_allowlist(cipher_suites: Sequence[int]) -> str:
    return ':'.join(cipher_suite_name(cipher_suite) for cipher_suite in cipher_suites)


def cipher_suite_parameters(cipher_suite: int) -> CipherSuiteParameters:
    try:
        return _CIPHER_SUITE_PARAMETERS[cipher_suite]
    except KeyError as exc:
        raise ProtocolError(f'unsupported TLS cipher suite: {cipher_suite:#06x}') from exc


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
        raise ProtocolError('truncated TLS extension payload')
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



def _read_u8_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u8(data, offset)
    return _read_exact(data, offset, length)



def _read_u16_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u16(data, offset)
    return _read_exact(data, offset, length)



def _read_u24_vector(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u24(data, offset)
    return _read_exact(data, offset, length)



def encode_server_name(server_name: str) -> bytes:
    encoded = server_name.encode('utf-8')
    entry = b'\x00' + _u16_vector(encoded)
    return _u16_vector(entry)



def decode_server_name(data: bytes) -> str:
    names_raw, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid server_name extension')
    inner = 0
    while inner < len(names_raw):
        name_type, inner = _read_u8(names_raw, inner)
        name, inner = _read_u16_vector(names_raw, inner)
        if name_type == 0:
            return name.decode('utf-8')
    raise ProtocolError('server_name extension does not contain a host_name entry')



def encode_supported_versions_client(versions: Sequence[int]) -> bytes:
    payload = b''.join(version.to_bytes(2, 'big') for version in versions)
    return _u8_vector(payload)



def decode_supported_versions_client(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u8_vector(data, 0)
    if offset != len(data) or len(payload) % 2:
        raise ProtocolError('invalid supported_versions extension')
    return tuple(int.from_bytes(payload[index:index + 2], 'big') for index in range(0, len(payload), 2))



def encode_supported_versions_server(version: int) -> bytes:
    return version.to_bytes(2, 'big')



def decode_supported_versions_server(data: bytes) -> int:
    if len(data) != 2:
        raise ProtocolError('invalid selected supported_versions extension')
    return int.from_bytes(data, 'big')



def encode_supported_groups(groups: Sequence[int]) -> bytes:
    payload = b''.join(group.to_bytes(2, 'big') for group in groups)
    return _u16_vector(payload)



def decode_supported_groups(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data) or len(payload) % 2:
        raise ProtocolError('invalid supported_groups extension')
    return tuple(int.from_bytes(payload[index:index + 2], 'big') for index in range(0, len(payload), 2))



def encode_signature_algorithms(schemes: Sequence[int]) -> bytes:
    payload = b''.join(scheme.to_bytes(2, 'big') for scheme in schemes)
    return _u16_vector(payload)



def decode_signature_algorithms(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data) or len(payload) % 2:
        raise ProtocolError('invalid signature_algorithms extension')
    return tuple(int.from_bytes(payload[index:index + 2], 'big') for index in range(0, len(payload), 2))



def encode_alpn(protocols: Sequence[str]) -> bytes:
    payload = bytearray()
    for protocol in protocols:
        raw = protocol.encode('ascii')
        payload.extend(_u8_vector(raw))
    return _u16_vector(bytes(payload))



def decode_alpn(data: bytes) -> tuple[str, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid ALPN extension')
    inner = 0
    protocols: list[str] = []
    while inner < len(payload):
        raw, inner = _read_u8_vector(payload, inner)
        protocols.append(raw.decode('ascii'))
    if not protocols:
        raise ProtocolError('ALPN extension is empty')
    return tuple(protocols)



def encode_psk_key_exchange_modes(modes: Sequence[int]) -> bytes:
    return _u8_vector(bytes(modes))



def decode_psk_key_exchange_modes(data: bytes) -> tuple[int, ...]:
    payload, offset = _read_u8_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid psk_key_exchange_modes extension')
    return tuple(payload)



def encode_keyshare_client(shares: Sequence[tuple[int, bytes]]) -> bytes:
    payload = bytearray()
    for group, key_exchange in shares:
        payload.extend(group.to_bytes(2, 'big'))
        payload.extend(_u16_vector(key_exchange))
    return _u16_vector(bytes(payload))



def decode_keyshare_client(data: bytes) -> dict[int, bytes]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid key_share extension')
    inner = 0
    shares: dict[int, bytes] = {}
    while inner < len(payload):
        group, inner = _read_u16(payload, inner)
        key_exchange, inner = _read_u16_vector(payload, inner)
        shares[group] = key_exchange
    return shares



def encode_keyshare_server(group: int, key_exchange: bytes) -> bytes:
    return group.to_bytes(2, 'big') + _u16_vector(key_exchange)



def decode_keyshare_server(data: bytes) -> tuple[int, bytes]:
    group, offset = _read_u16(data, 0)
    key_exchange, offset = _read_u16_vector(data, offset)
    if offset != len(data):
        raise ProtocolError('invalid server key_share extension')
    return group, key_exchange



def encode_keyshare_hrr(selected_group: int) -> bytes:
    return selected_group.to_bytes(2, 'big')



def decode_keyshare_hrr(data: bytes) -> int:
    if len(data) != 2:
        raise ProtocolError('invalid HelloRetryRequest key_share extension')
    return int.from_bytes(data, 'big')



def encode_cookie(cookie: bytes) -> bytes:
    return _u16_vector(cookie)



def decode_cookie(data: bytes) -> bytes:
    cookie, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid cookie extension')
    return cookie



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



def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 4)
    return int.from_bytes(raw, 'big'), offset



def encode_quic_transport_parameters(parameters: TransportParameters) -> bytes:
    return parameters.to_bytes()



def decode_quic_transport_parameters(data: bytes) -> TransportParameters:
    return TransportParameters.from_bytes(data)



def encode_extensions(extensions: Sequence[TlsExtension], *, message_context: str) -> bytes:
    payload = bytearray()
    for extension in extensions:
        raw = extension.raw_data
        if raw is None:
            raw = encode_extension_value(extension.extension_type, extension.value, message_context=message_context)
        payload.extend(int(extension.extension_type).to_bytes(2, 'big'))
        payload.extend(len(raw).to_bytes(2, 'big'))
        payload.extend(raw)
    return _u16_vector(bytes(payload))



def decode_extensions(data: bytes, *, message_context: str) -> tuple[TlsExtension, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid TLS extensions vector')
    inner = 0
    items: list[TlsExtension] = []
    while inner < len(payload):
        extension_type, inner = _read_u16(payload, inner)
        extension_data, inner = _read_u16_vector(payload, inner)
        value = decode_extension_value(extension_type, extension_data, message_context=message_context)
        items.append(TlsExtension(extension_type=extension_type, value=value, raw_data=extension_data))
    return tuple(items)



def encode_extension_value(extension_type: int, value: object, *, message_context: str) -> bytes:
    ext = ExtensionType(extension_type) if extension_type in set(item.value for item in ExtensionType) else None
    if ext == ExtensionType.SERVER_NAME:
        assert isinstance(value, str)
        return encode_server_name(value)
    if ext == ExtensionType.SUPPORTED_VERSIONS:
        if message_context == 'client_hello':
            return encode_supported_versions_client(tuple(int(item) for item in value))
        return encode_supported_versions_server(int(value))
    if ext == ExtensionType.SUPPORTED_GROUPS:
        return encode_supported_groups(tuple(int(item) for item in value))
    if ext in {ExtensionType.SIGNATURE_ALGORITHMS, ExtensionType.SIGNATURE_ALGORITHMS_CERT}:
        return encode_signature_algorithms(tuple(int(item) for item in value))
    if ext == ExtensionType.ALPN:
        if isinstance(value, str):
            return encode_alpn((value,))
        return encode_alpn(tuple(str(item) for item in value))
    if ext == ExtensionType.PSK_KEY_EXCHANGE_MODES:
        return encode_psk_key_exchange_modes(tuple(int(item) for item in value))
    if ext == ExtensionType.KEY_SHARE:
        if message_context == 'client_hello':
            return encode_keyshare_client(tuple((int(group), bytes(key_exchange)) for group, key_exchange in value))
        if message_context == 'hello_retry_request':
            return encode_keyshare_hrr(int(value))
        group, key_exchange = value
        return encode_keyshare_server(int(group), bytes(key_exchange))
    if ext == ExtensionType.COOKIE:
        return encode_cookie(bytes(value))
    if ext == ExtensionType.EARLY_DATA:
        size = QUIC_EARLY_DATA_SENTINEL if value is True else int(value)
        return encode_early_data(message_context, size)
    if ext == ExtensionType.PRE_SHARED_KEY:
        if message_context == 'client_hello':
            offered = value
            assert isinstance(offered, OfferedPsks)
            return encode_pre_shared_key_client(offered.identities, offered.binders)
        return encode_pre_shared_key_server(int(value))
    if ext == ExtensionType.QUIC_TRANSPORT_PARAMETERS:
        assert isinstance(value, TransportParameters)
        return encode_quic_transport_parameters(value)
    if isinstance(value, bytes):
        return value
    raise ProtocolError(f'unsupported TLS extension type {extension_type}')



def decode_extension_value(extension_type: int, data: bytes, *, message_context: str) -> object:
    try:
        ext = ExtensionType(extension_type)
    except ValueError:
        return data
    if ext == ExtensionType.SERVER_NAME:
        return decode_server_name(data)
    if ext == ExtensionType.SUPPORTED_VERSIONS:
        if message_context == 'client_hello':
            return decode_supported_versions_client(data)
        return decode_supported_versions_server(data)
    if ext == ExtensionType.SUPPORTED_GROUPS:
        return decode_supported_groups(data)
    if ext in {ExtensionType.SIGNATURE_ALGORITHMS, ExtensionType.SIGNATURE_ALGORITHMS_CERT}:
        return decode_signature_algorithms(data)
    if ext == ExtensionType.ALPN:
        protocols = decode_alpn(data)
        return protocols if message_context == 'client_hello' else protocols[0]
    if ext == ExtensionType.PSK_KEY_EXCHANGE_MODES:
        return decode_psk_key_exchange_modes(data)
    if ext == ExtensionType.KEY_SHARE:
        if message_context == 'client_hello':
            return decode_keyshare_client(data)
        if message_context == 'hello_retry_request':
            return decode_keyshare_hrr(data)
        return decode_keyshare_server(data)
    if ext == ExtensionType.COOKIE:
        return decode_cookie(data)
    if ext == ExtensionType.EARLY_DATA:
        return decode_early_data(data, message_context)
    if ext == ExtensionType.PRE_SHARED_KEY:
        if message_context == 'client_hello':
            return decode_pre_shared_key_client(data)
        return decode_pre_shared_key_server(data)
    if ext == ExtensionType.QUIC_TRANSPORT_PARAMETERS:
        return decode_quic_transport_parameters(data)
    return data



def extension_dict(extensions: Iterable[TlsExtension]) -> dict[int, object]:
    return {int(extension.extension_type): extension.value for extension in extensions}
