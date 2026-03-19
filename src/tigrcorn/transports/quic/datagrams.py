from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from tigrcorn.errors import ProtocolError
from tigrcorn.utils.bytes import decode_quic_varint, encode_quic_varint, pack_varbytes, unpack_varbytes


class QuicPacketType(IntEnum):
    INITIAL = 0
    HANDSHAKE = 1
    SHORT = 2
    RETRY = 3


@dataclass(slots=True)
class QuicHeader:
    packet_type: QuicPacketType
    version: int
    dst_cid: bytes
    src_cid: bytes = b''
    packet_number: int = 0
    token: bytes = b''


@dataclass(slots=True)
class QuicDatagram:
    header: QuicHeader
    payload: bytes
    tag: bytes = b''


def encode_header(header: QuicHeader) -> bytes:
    out = bytearray()
    out.append(int(header.packet_type) & 0xFF)
    out.extend(header.version.to_bytes(4, 'big'))
    out.extend(pack_varbytes(header.dst_cid))
    out.extend(pack_varbytes(header.src_cid))
    out.extend(encode_quic_varint(header.packet_number))
    out.extend(pack_varbytes(header.token))
    return bytes(out)


def decode_header(data: bytes, offset: int = 0) -> tuple[QuicHeader, int]:
    if offset >= len(data):
        raise ProtocolError('QUIC datagram underflow')
    packet_type = QuicPacketType(data[offset])
    offset += 1
    if offset + 4 > len(data):
        raise ProtocolError('QUIC header underflow')
    version = int.from_bytes(data[offset:offset+4], 'big')
    offset += 4
    dst_cid, offset = unpack_varbytes(data, offset)
    src_cid, offset = unpack_varbytes(data, offset)
    packet_number, offset = decode_quic_varint(data, offset)
    token, offset = unpack_varbytes(data, offset)
    return QuicHeader(packet_type=packet_type, version=version, dst_cid=dst_cid, src_cid=src_cid, packet_number=packet_number, token=token), offset


def encode_datagram(datagram: QuicDatagram) -> bytes:
    header = encode_header(datagram.header)
    return header + pack_varbytes(datagram.payload) + pack_varbytes(datagram.tag)


def decode_datagram(data: bytes) -> QuicDatagram:
    header, offset = decode_header(data)
    payload, offset = unpack_varbytes(data, offset)
    tag, offset = unpack_varbytes(data, offset)
    if offset != len(data):
        raise ProtocolError('trailing data in QUIC datagram')
    return QuicDatagram(header=header, payload=payload, tag=tag)
