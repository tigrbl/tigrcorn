from .crypto import (
    QUIC_V1_INITIAL_SALT,
    QuicPacketProtectionKeys,
    aes_gcm_decrypt,
    aes_gcm_encrypt,
    apply_header_protection,
    derive_initial_packet_protection_keys,
    derive_initial_secret,
    derive_quic_packet_protection_keys,
    derive_secret,
    generate_connection_id,
    hkdf_expand_label,
    hkdf_extract,
    make_integrity_tag,
    packet_nonce,
    protect_payload,
    remove_header_protection,
    unprotect_payload,
    unprotect_quic_packet,
    protect_quic_packet,
)
from .datagrams import QuicDatagram, QuicHeader, QuicPacketType, decode_datagram, encode_datagram
from .packets import (
    QuicLongHeaderPacket,
    QuicLongHeaderType,
    QuicRetryPacket,
    QuicShortHeaderPacket,
    QuicStatelessResetPacket,
    QuicVersionNegotiationPacket,
    decode_packet,
    decode_long_header_packet,
    decode_short_header_packet,
    parse_stateless_reset,
)
from .streams import QuicStreamFrame, QuicAckFrame, QuicConnectionCloseFrame, QuicMaxDataFrame, QuicMaxStreamDataFrame

__all__ = [
    'QuicConnection',
    'QuicEvent',
    'QuicDatagram',
    'QuicHeader',
    'QuicPacketType',
    'QuicStreamFrame',
    'QuicAckFrame',
    'QuicConnectionCloseFrame',
    'QuicMaxDataFrame',
    'QuicMaxStreamDataFrame',
    'decode_datagram',
    'encode_datagram',
    'QuicLongHeaderPacket',
    'QuicLongHeaderType',
    'QuicRetryPacket',
    'QuicShortHeaderPacket',
    'QuicStatelessResetPacket',
    'QuicVersionNegotiationPacket',
    'decode_packet',
    'decode_long_header_packet',
    'decode_short_header_packet',
    'parse_stateless_reset',
    'QUIC_V1_INITIAL_SALT',
    'QuicPacketProtectionKeys',
    'aes_gcm_encrypt',
    'aes_gcm_decrypt',
    'apply_header_protection',
    'remove_header_protection',
    'protect_quic_packet',
    'unprotect_quic_packet',
    'derive_initial_secret',
    'derive_initial_packet_protection_keys',
    'derive_quic_packet_protection_keys',
    'hkdf_extract',
    'hkdf_expand_label',
    'packet_nonce',
    'derive_secret',
    'generate_connection_id',
    'make_integrity_tag',
    'protect_payload',
    'unprotect_payload',
    'QuicTlsHandshakeDriver',
    'TransportParameters',
    'generate_self_signed_certificate',
    'QuicLossRecovery',
]


def __getattr__(name: str):
    if name in {"QuicConnection", "QuicEvent"}:
        from .connection import QuicConnection, QuicEvent

        mapping = {
            "QuicConnection": QuicConnection,
            "QuicEvent": QuicEvent,
        }
        return mapping[name]
    if name in {"QuicTlsHandshakeDriver", "TransportParameters", "generate_self_signed_certificate"}:
        from .handshake import QuicTlsHandshakeDriver, TransportParameters, generate_self_signed_certificate

        mapping = {
            "QuicTlsHandshakeDriver": QuicTlsHandshakeDriver,
            "TransportParameters": TransportParameters,
            "generate_self_signed_certificate": generate_self_signed_certificate,
        }
        return mapping[name]
    if name == "QuicLossRecovery":
        from .recovery import QuicLossRecovery

        return QuicLossRecovery
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
