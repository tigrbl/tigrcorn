from __future__ import annotations

from dataclasses import dataclass

from tigrcorn_security.tls13.messages import (
    Certificate,
    CertificateVerify,
    ClientHello,
    EncryptedExtensions,
    Finished,
    HandshakeMessage,
    NewSessionTicket,
    ServerHello,
    decode_handshake_messages,
)

PACKET_SPACE_INITIAL = 'initial'
PACKET_SPACE_HANDSHAKE = 'handshake'
PACKET_SPACE_APPLICATION = 'application'
PACKET_SPACE_ZERO_RTT = '0rtt'


@dataclass(slots=True)
class QuicTlsFlight:
    packet_space: str
    data: bytes



def message_packet_space(message: HandshakeMessage) -> str:
    if isinstance(message, ClientHello):
        return PACKET_SPACE_INITIAL
    if isinstance(message, ServerHello):
        return PACKET_SPACE_INITIAL
    if isinstance(message, NewSessionTicket):
        return PACKET_SPACE_APPLICATION
    if isinstance(message, (EncryptedExtensions, Certificate, CertificateVerify, Finished)):
        return PACKET_SPACE_HANDSHAKE
    return PACKET_SPACE_HANDSHAKE



def split_handshake_flights(data: bytes) -> list[QuicTlsFlight]:
    flights: list[QuicTlsFlight] = []
    current_space: str | None = None
    payload = bytearray()
    for message in decode_handshake_messages(data):
        encoded = message.encode()
        packet_space = message_packet_space(message)
        if current_space is None:
            current_space = packet_space
        elif current_space != packet_space:
            flights.append(QuicTlsFlight(packet_space=current_space, data=bytes(payload)))
            payload.clear()
            current_space = packet_space
        payload.extend(encoded)
    if current_space is not None and payload:
        flights.append(QuicTlsFlight(packet_space=current_space, data=bytes(payload)))
    return flights
