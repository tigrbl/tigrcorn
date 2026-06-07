from __future__ import annotations

from .imports import *

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
_TP_MAX_DATAGRAM_FRAME_SIZE = 0x20


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
    max_datagram_frame_size: int | None = None
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
        if self.max_datagram_frame_size is not None and self.max_datagram_frame_size < 0:
            raise ValueError('max_datagram_frame_size must be non-negative')
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
        add_int(_TP_MAX_DATAGRAM_FRAME_SIZE, self.max_datagram_frame_size)
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
            elif parameter_id == _TP_MAX_DATAGRAM_FRAME_SIZE:
                values['max_datagram_frame_size'] = decode_int(raw)
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
            and (
                self.max_datagram_frame_size is None
                or (
                    current.max_datagram_frame_size is not None
                    and current.max_datagram_frame_size >= self.max_datagram_frame_size
                )
            )
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

__all__ = [name for name in globals() if not name.startswith('__')]
