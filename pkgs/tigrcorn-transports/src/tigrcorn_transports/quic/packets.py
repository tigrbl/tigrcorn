from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from tigrcorn_core.errors import ProtocolError
from tigrcorn_transports.quic.crypto import compute_retry_integrity_tag, verify_retry_integrity_tag
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint


class QuicLongHeaderType(IntEnum):
    INITIAL = 0x00
    ZERO_RTT = 0x01
    HANDSHAKE = 0x02
    RETRY = 0x03


@dataclass(slots=True)
class QuicLongHeaderPacket:
    packet_type: QuicLongHeaderType
    version: int
    destination_connection_id: bytes
    source_connection_id: bytes
    packet_number: bytes = b'\x00'
    payload: bytes = b''
    token: bytes = b''

    def __post_init__(self) -> None:
        if len(self.destination_connection_id) > 20 or len(self.source_connection_id) > 20:
            raise ValueError('QUIC connection ids must be at most 20 bytes long')
        if self.packet_type != QuicLongHeaderType.RETRY and not 1 <= len(self.packet_number) <= 4:
            raise ValueError('QUIC protected packet number must be 1-4 bytes')
        if self.packet_type == QuicLongHeaderType.RETRY and self.packet_number:
            raise ValueError('Retry packets do not carry a packet number')

    @property
    def pn_length(self) -> int:
        return len(self.packet_number)

    @property
    def payload_length(self) -> int:
        if self.packet_type == QuicLongHeaderType.RETRY:
            return len(self.payload)
        return len(self.packet_number) + len(self.payload)

    @property
    def pn_offset(self) -> int:
        if self.packet_type == QuicLongHeaderType.RETRY:
            raise ProtocolError('Retry packets do not have a packet number offset')
        offset = 1 + 4 + 1 + len(self.destination_connection_id) + 1 + len(self.source_connection_id)
        if self.packet_type == QuicLongHeaderType.INITIAL:
            offset += len(encode_quic_varint(len(self.token))) + len(self.token)
        offset += len(encode_quic_varint(self.payload_length))
        return offset

    def header_bytes(self) -> bytes:
        if self.packet_type == QuicLongHeaderType.RETRY:
            first_byte = 0xF0 | 0x0F
        else:
            first_byte = 0xC0 | 0x40 | (int(self.packet_type) << 4) | ((len(self.packet_number) - 1) & 0x03)
        out = bytearray([first_byte])
        out.extend(self.version.to_bytes(4, 'big'))
        out.append(len(self.destination_connection_id))
        out.extend(self.destination_connection_id)
        out.append(len(self.source_connection_id))
        out.extend(self.source_connection_id)
        if self.packet_type == QuicLongHeaderType.INITIAL:
            out.extend(encode_quic_varint(len(self.token)))
            out.extend(self.token)
        elif self.packet_type == QuicLongHeaderType.RETRY:
            out.extend(self.token)
            return bytes(out)
        out.extend(encode_quic_varint(self.payload_length))
        out.extend(self.packet_number)
        return bytes(out)

    def encode(self) -> bytes:
        return self.header_bytes() + self.payload


@dataclass(slots=True)
class QuicRetryPacket:
    version: int
    destination_connection_id: bytes
    source_connection_id: bytes
    token: bytes
    integrity_tag: bytes = field(default_factory=bytes)

    def __post_init__(self) -> None:
        if len(self.destination_connection_id) > 20 or len(self.source_connection_id) > 20:
            raise ValueError('QUIC connection ids must be at most 20 bytes long')
        if self.integrity_tag and len(self.integrity_tag) != 16:
            raise ValueError('QUIC Retry Integrity Tag must be 16 bytes')

    def packet_without_integrity_tag(self) -> bytes:
        header = QuicLongHeaderPacket(
            packet_type=QuicLongHeaderType.RETRY,
            version=self.version,
            destination_connection_id=self.destination_connection_id,
            source_connection_id=self.source_connection_id,
            token=self.token,
            packet_number=b'',
            payload=b'',
        )
        return header.header_bytes()

    def encode(self, *, original_destination_connection_id: bytes | None = None) -> bytes:
        packet = self.packet_without_integrity_tag()
        tag = self.integrity_tag
        if not tag:
            if original_destination_connection_id is None:
                raise ValueError('original destination connection id required to compute Retry Integrity Tag')
            tag = compute_retry_integrity_tag(packet, original_destination_connection_id)
        return packet + tag

    def validate(self, *, original_destination_connection_id: bytes) -> bool:
        if len(self.integrity_tag) != 16:
            return False
        return verify_retry_integrity_tag(self.packet_without_integrity_tag(), original_destination_connection_id, self.integrity_tag)


@dataclass(slots=True)
class QuicVersionNegotiationPacket:
    destination_connection_id: bytes
    source_connection_id: bytes
    supported_versions: list[int]
    first_byte: int = 0xC0

    def __post_init__(self) -> None:
        if len(self.destination_connection_id) > 20 or len(self.source_connection_id) > 20:
            raise ValueError('QUIC connection ids must be at most 20 bytes long')
        if not self.supported_versions:
            raise ValueError('Version Negotiation packets must advertise at least one version')

    def encode(self) -> bytes:
        out = bytearray([self.first_byte & 0xFF])
        out.extend((0).to_bytes(4, 'big'))
        out.append(len(self.destination_connection_id))
        out.extend(self.destination_connection_id)
        out.append(len(self.source_connection_id))
        out.extend(self.source_connection_id)
        for version in self.supported_versions:
            out.extend(int(version).to_bytes(4, 'big'))
        return bytes(out)


@dataclass(slots=True)
class QuicShortHeaderPacket:
    destination_connection_id: bytes
    packet_number: bytes
    payload: bytes = b''
    key_phase: bool = False
    spin_bit: bool = False

    def __post_init__(self) -> None:
        if not 1 <= len(self.packet_number) <= 4:
            raise ValueError('QUIC short-header packet number must be 1-4 bytes')

    @property
    def pn_offset(self) -> int:
        return 1 + len(self.destination_connection_id)

    def header_bytes(self) -> bytes:
        first_byte = 0x40 | ((1 if self.spin_bit else 0) << 5) | ((1 if self.key_phase else 0) << 2) | ((len(self.packet_number) - 1) & 0x03)
        return bytes([first_byte]) + self.destination_connection_id + self.packet_number

    def encode(self) -> bytes:
        return self.header_bytes() + self.payload


@dataclass(slots=True)
class QuicStatelessResetPacket:
    stateless_reset_token: bytes
    unpredictable_bits: bytes = field(default_factory=lambda: b'\x00' * 5)

    def __post_init__(self) -> None:
        if len(self.stateless_reset_token) != 16:
            raise ValueError('stateless reset token must be 16 bytes')
        if len(self.unpredictable_bits) < 5:
            raise ValueError('stateless reset requires at least 5 bytes of unpredictable bits')

    def encode(self) -> bytes:
        return self.unpredictable_bits + self.stateless_reset_token


QuicPacket = QuicLongHeaderPacket | QuicRetryPacket | QuicVersionNegotiationPacket | QuicShortHeaderPacket | QuicStatelessResetPacket



def decode_long_header_packet(data: bytes) -> QuicLongHeaderPacket | QuicRetryPacket | QuicVersionNegotiationPacket:
    if len(data) < 7:
        raise ProtocolError('QUIC packet underflow')
    first_byte = data[0]
    if not (first_byte & 0x80):
        raise ProtocolError('not a QUIC long-header packet')
    version = int.from_bytes(data[1:5], 'big')
    offset = 5
    if offset >= len(data):
        raise ProtocolError('truncated QUIC destination connection id length')
    dcid_len = data[offset]
    offset += 1
    if offset + dcid_len > len(data):
        raise ProtocolError('truncated QUIC destination connection id')
    dcid = data[offset:offset + dcid_len]
    offset += dcid_len
    if offset >= len(data):
        raise ProtocolError('truncated QUIC source connection id length')
    scid_len = data[offset]
    offset += 1
    if offset + scid_len > len(data):
        raise ProtocolError('truncated QUIC source connection id')
    scid = data[offset:offset + scid_len]
    offset += scid_len
    if version == 0:
        versions: list[int] = []
        while offset < len(data):
            if offset + 4 > len(data):
                raise ProtocolError('truncated Version Negotiation packet')
            versions.append(int.from_bytes(data[offset:offset + 4], 'big'))
            offset += 4
        if not versions:
            raise ProtocolError('Version Negotiation packet missing supported versions')
        return QuicVersionNegotiationPacket(destination_connection_id=dcid, source_connection_id=scid, supported_versions=versions, first_byte=first_byte)

    packet_type = QuicLongHeaderType((first_byte >> 4) & 0x03)
    if packet_type == QuicLongHeaderType.RETRY:
        if len(data) - offset < 16:
            raise ProtocolError('truncated QUIC Retry Integrity Tag')
        token = data[offset:-16]
        integrity_tag = data[-16:]
        return QuicRetryPacket(
            version=version,
            destination_connection_id=dcid,
            source_connection_id=scid,
            token=token,
            integrity_tag=integrity_tag,
        )

    token = b''
    if packet_type == QuicLongHeaderType.INITIAL:
        token_length, offset = decode_quic_varint(data, offset)
        end = offset + token_length
        if end > len(data):
            raise ProtocolError('truncated QUIC Initial token')
        token = data[offset:end]
        offset = end
    payload_length, offset = decode_quic_varint(data, offset)
    pn_length = (first_byte & 0x03) + 1
    if offset + pn_length > len(data):
        raise ProtocolError('truncated QUIC packet number')
    packet_number = data[offset:offset + pn_length]
    offset += pn_length
    payload_length -= pn_length
    if payload_length < 0 or offset + payload_length > len(data):
        raise ProtocolError('truncated QUIC payload')
    payload = data[offset:offset + payload_length]
    return QuicLongHeaderPacket(
        packet_type=packet_type,
        version=version,
        destination_connection_id=dcid,
        source_connection_id=scid,
        token=token,
        packet_number=packet_number,
        payload=payload,
    )



def decode_short_header_packet(data: bytes, *, destination_connection_id_length: int) -> QuicShortHeaderPacket:
    if not data:
        raise ProtocolError('QUIC packet underflow')
    if data[0] & 0x80:
        raise ProtocolError('not a QUIC short-header packet')
    offset = 1
    end = offset + destination_connection_id_length
    if end > len(data):
        raise ProtocolError('truncated QUIC short-header destination connection id')
    destination_connection_id = data[offset:end]
    offset = end
    pn_length = (data[0] & 0x03) + 1
    end = offset + pn_length
    if end > len(data):
        raise ProtocolError('truncated QUIC short-header packet number')
    packet_number = data[offset:end]
    offset = end
    return QuicShortHeaderPacket(
        destination_connection_id=destination_connection_id,
        packet_number=packet_number,
        payload=data[offset:],
        key_phase=bool(data[0] & 0x04),
        spin_bit=bool(data[0] & 0x20),
    )



def decode_packet(data: bytes, *, destination_connection_id_length: int | None = None) -> QuicPacket:
    if not data:
        raise ProtocolError('QUIC packet underflow')
    if data[0] & 0x80:
        return decode_long_header_packet(data)
    if destination_connection_id_length is None:
        raise ProtocolError('destination_connection_id_length is required for QUIC short-header decoding')
    return decode_short_header_packet(data, destination_connection_id_length=destination_connection_id_length)



def parse_stateless_reset(data: bytes, *, expected_token: bytes) -> QuicStatelessResetPacket:
    if len(expected_token) != 16:
        raise ValueError('expected stateless reset token must be 16 bytes')
    if len(data) < len(expected_token) + 5:
        raise ProtocolError('truncated stateless reset packet')
    token = data[-16:]
    if token != expected_token:
        raise ProtocolError('stateless reset token mismatch')
    return QuicStatelessResetPacket(stateless_reset_token=token, unpredictable_bits=data[:-16])



def packet_wire_length(data: bytes, *, offset: int = 0, destination_connection_id_length: int | None = None) -> int:
    if offset >= len(data):
        raise ProtocolError('QUIC packet underflow')
    first_byte = data[offset]
    if first_byte & 0x80:
        cursor = offset + 1
        if cursor + 4 > len(data):
            raise ProtocolError('truncated QUIC version field')
        version = int.from_bytes(data[cursor:cursor + 4], 'big')
        cursor += 4
        if cursor >= len(data):
            raise ProtocolError('truncated QUIC destination connection id length')
        dcid_len = data[cursor]
        cursor += 1 + dcid_len
        if cursor > len(data):
            raise ProtocolError('truncated QUIC destination connection id')
        if cursor >= len(data):
            raise ProtocolError('truncated QUIC source connection id length')
        scid_len = data[cursor]
        cursor += 1 + scid_len
        if cursor > len(data):
            raise ProtocolError('truncated QUIC source connection id')
        if version == 0:
            return len(data) - offset
        packet_type = QuicLongHeaderType((first_byte >> 4) & 0x03)
        if packet_type == QuicLongHeaderType.RETRY:
            return len(data) - offset
        if packet_type == QuicLongHeaderType.INITIAL:
            token_length, cursor = decode_quic_varint(data, cursor)
            cursor += token_length
            if cursor > len(data):
                raise ProtocolError('truncated QUIC Initial token')
        payload_length, cursor = decode_quic_varint(data, cursor)
        end = cursor + payload_length
        if end > len(data):
            raise ProtocolError('truncated QUIC payload')
        return end - offset
    if destination_connection_id_length is None:
        raise ProtocolError('destination_connection_id_length is required for QUIC short-header packet length')
    minimum = offset + 1 + destination_connection_id_length + 1
    if minimum > len(data):
        raise ProtocolError('truncated QUIC short-header packet')
    return len(data) - offset



def split_coalesced_packets(data: bytes, *, destination_connection_id_length: int | None = None) -> list[bytes]:
    packets: list[bytes] = []
    offset = 0
    while offset < len(data):
        length = packet_wire_length(data, offset=offset, destination_connection_id_length=destination_connection_id_length)
        if length <= 0:
            raise ProtocolError('invalid QUIC packet length')
        end = offset + length
        if end > len(data):
            raise ProtocolError('truncated QUIC packet in datagram')
        packet = data[offset:end]
        packets.append(packet)
        offset = end
        if packet and not (packet[0] & 0x80) and offset < len(data):
            raise ProtocolError('short-header packet must be the final packet in a coalesced datagram')
    return packets



def coalesce_packets(packets: list[bytes], *, max_datagram_size: int | None = None) -> list[bytes]:
    datagrams: list[bytes] = []
    current = bytearray()
    for packet in packets:
        if not packet:
            continue
        if max_datagram_size is not None and len(packet) > max_datagram_size:
            raise ValueError('packet exceeds maximum datagram size')
        if current and max_datagram_size is not None and len(current) + len(packet) > max_datagram_size:
            datagrams.append(bytes(current))
            current.clear()
        current.extend(packet)
    if current:
        datagrams.append(bytes(current))
    return datagrams
