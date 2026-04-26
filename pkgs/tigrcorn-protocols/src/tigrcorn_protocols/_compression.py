from __future__ import annotations

from tigrcorn_core.errors import ProtocolError

# Shared HPACK/QPACK Huffman tables from RFC 7541 Appendix B.
HUFFMAN_CODES: tuple[int, ...] = (
    8184, 8388568, 268435426, 268435427, 268435428, 268435429, 268435430, 268435431,
    268435432, 16777194, 1073741820, 268435433, 268435434, 1073741821, 268435435, 268435436,
    268435437, 268435438, 268435439, 268435440, 268435441, 268435442, 1073741822, 268435443,
    268435444, 268435445, 268435446, 268435447, 268435448, 268435449, 268435450, 268435451,
    20, 1016, 1017, 4090, 8185, 21, 248, 2042,
    1018, 1019, 249, 2043, 250, 22, 23, 24,
    0, 1, 2, 25, 26, 27, 28, 29,
    30, 31, 92, 251, 32764, 32, 4091, 1020,
    8186, 33, 93, 94, 95, 96, 97, 98,
    99, 100, 101, 102, 103, 104, 105, 106,
    107, 108, 109, 110, 111, 112, 113, 114,
    252, 115, 253, 8187, 524272, 8188, 16380, 34,
    32765, 3, 35, 4, 36, 5, 37, 38,
    39, 6, 116, 117, 40, 41, 42, 7,
    43, 118, 44, 8, 9, 45, 119, 120,
    121, 122, 123, 32766, 2044, 16381, 8189, 268435452,
    1048550, 4194258, 1048551, 1048552, 4194259, 4194260, 4194261, 8388569,
    4194262, 8388570, 8388571, 8388572, 8388573, 8388574, 16777195, 8388575,
    16777196, 16777197, 4194263, 8388576, 16777198, 8388577, 8388578, 8388579,
    8388580, 2097116, 4194264, 8388581, 4194265, 8388582, 8388583, 16777199,
    4194266, 2097117, 1048553, 4194267, 4194268, 8388584, 8388585, 2097118,
    8388586, 4194269, 4194270, 16777200, 2097119, 4194271, 8388587, 8388588,
    2097120, 2097121, 4194272, 2097122, 8388589, 4194273, 8388590, 8388591,
    1048554, 4194274, 4194275, 4194276, 8388592, 4194277, 4194278, 8388593,
    67108832, 67108833, 1048555, 524273, 4194279, 8388594, 4194280, 33554412,
    67108834, 67108835, 67108836, 134217694, 134217695, 67108837, 16777201, 33554413,
    524274, 2097123, 67108838, 134217696, 134217697, 67108839, 134217698, 16777202,
    2097124, 2097125, 67108840, 67108841, 268435453, 134217699, 134217700, 134217701,
    1048556, 16777203, 1048557, 2097126, 4194281, 2097127, 2097128, 8388595,
    4194282, 4194283, 33554414, 33554415, 16777204, 16777205, 67108842, 8388596,
    67108843, 134217702, 67108844, 67108845, 134217703, 134217704, 134217705, 134217706,
    134217707, 268435454, 134217708, 134217709, 134217710, 134217711, 134217712, 67108846,
    1073741823,
)

HUFFMAN_CODE_LENGTHS: tuple[int, ...] = (
    13, 23, 28, 28, 28, 28, 28, 28, 28, 24, 30, 28, 28, 30, 28, 28,
    28, 28, 28, 28, 28, 28, 30, 28, 28, 28, 28, 28, 28, 28, 28, 28,
    6, 10, 10, 12, 13, 6, 8, 11, 10, 10, 8, 11, 8, 6, 6, 6,
    5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 7, 8, 15, 6, 12, 10,
    13, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 8, 7, 8, 13, 19, 13, 14, 6,
    15, 5, 6, 5, 6, 5, 6, 6, 6, 5, 7, 7, 6, 6, 6, 5,
    6, 7, 6, 5, 5, 6, 7, 7, 7, 7, 7, 15, 11, 14, 13, 28,
    20, 22, 20, 20, 22, 22, 22, 23, 22, 23, 23, 23, 23, 23, 24, 23,
    24, 24, 22, 23, 24, 23, 23, 23, 23, 21, 22, 23, 22, 23, 23, 24,
    22, 21, 20, 22, 22, 23, 23, 21, 23, 22, 22, 24, 21, 22, 23, 23,
    21, 21, 22, 21, 23, 22, 23, 23, 20, 22, 22, 22, 23, 22, 22, 23,
    26, 26, 20, 19, 22, 23, 22, 25, 26, 26, 26, 27, 27, 26, 24, 25,
    19, 21, 26, 27, 27, 26, 27, 24, 21, 21, 26, 26, 28, 27, 27, 27,
    20, 24, 20, 21, 22, 21, 21, 23, 22, 22, 25, 25, 24, 24, 26, 23,
    26, 27, 26, 26, 27, 27, 27, 27, 27, 28, 27, 27, 27, 27, 27, 26,
    30,
)

EOS_SYMBOL = 256

def encode_prefixed_integer(value: int, prefix_bits: int, prefix_mask: int = 0) -> bytes:
    if value < 0:
        raise ValueError("header-compression integers must be non-negative")
    max_prefix = (1 << prefix_bits) - 1
    if value < max_prefix:
        return bytes([prefix_mask | value])
    out = bytearray([prefix_mask | max_prefix])
    value -= max_prefix
    while value >= 128:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)

def decode_prefixed_integer(
    data: bytes,
    offset: int,
    prefix_bits: int,
    *,
    max_octets: int | None = None,
    max_value: int | None = None,
) -> tuple[int, int]:
    if offset >= len(data):
        raise ProtocolError("header-compression integer underflow")
    max_prefix = (1 << prefix_bits) - 1
    value = data[offset] & max_prefix
    offset += 1
    if value < max_prefix:
        if max_value is not None and value > max_value:
            raise ProtocolError("header-compression integer exceeds configured maximum")
        return value, offset
    shift = 0
    octets = 0
    while True:
        if offset >= len(data):
            raise ProtocolError("header-compression integer continuation underflow")
        byte = data[offset]
        offset += 1
        octets += 1
        if max_octets is not None and octets > max_octets:
            raise ProtocolError("header-compression integer exceeds configured maximum")
        value += (byte & 0x7F) << shift
        if max_value is not None and value > max_value:
            raise ProtocolError("header-compression integer exceeds configured maximum")
        if not (byte & 0x80):
            return value, offset
        shift += 7

def huffman_encode(data: bytes) -> bytes:
    if not data:
        return b""
    final_num = 0
    final_len = 0
    for byte in data:
        code_len = HUFFMAN_CODE_LENGTHS[byte]
        code = HUFFMAN_CODES[byte] & ((1 << code_len) - 1)
        final_num = (final_num << code_len) | code
        final_len += code_len
    pad = (8 - (final_len % 8)) % 8
    final_num = (final_num << pad) | ((1 << pad) - 1)
    total_bytes = (final_len + pad) // 8
    return final_num.to_bytes(total_bytes, "big")

class _TrieNode:
    __slots__ = ("zero", "one", "symbol")
    def __init__(self) -> None:
        self.zero: _TrieNode | None = None
        self.one: _TrieNode | None = None
        self.symbol: int | None = None

def _build_huffman_tree() -> _TrieNode:
    root = _TrieNode()
    for symbol, (code, length) in enumerate(zip(HUFFMAN_CODES, HUFFMAN_CODE_LENGTHS)):
        node = root
        for shift in range(length - 1, -1, -1):
            bit = (code >> shift) & 1
            if bit:
                if node.one is None:
                    node.one = _TrieNode()
                node = node.one
            else:
                if node.zero is None:
                    node.zero = _TrieNode()
                node = node.zero
        if node.symbol is not None:
            raise RuntimeError("duplicate Huffman code")
        node.symbol = symbol
    return root

_HUFFMAN_ROOT = _build_huffman_tree()

def huffman_decode(data: bytes, *, max_output_length: int | None = None) -> bytes:
    if not data:
        return b""
    node = _HUFFMAN_ROOT
    decoded = bytearray()
    trailing_value = 0
    trailing_bits = 0
    for byte in data:
        for shift in range(7, -1, -1):
            bit = (byte >> shift) & 1
            trailing_value = (trailing_value << 1) | bit
            trailing_bits += 1
            next_node = node.one if bit else node.zero
            if next_node is None:
                raise ProtocolError("invalid Huffman string")
            node = next_node
            if node.symbol is None:
                continue
            if node.symbol == EOS_SYMBOL:
                raise ProtocolError("EOS symbol is not permitted in header strings")
            decoded.append(node.symbol)
            if max_output_length is not None and len(decoded) > max_output_length:
                raise ProtocolError("header-compression string exceeds configured maximum")
            node = _HUFFMAN_ROOT
            trailing_value = 0
            trailing_bits = 0
    if node is not _HUFFMAN_ROOT:
        if trailing_bits > 7 or trailing_value != (1 << trailing_bits) - 1:
            raise ProtocolError("incomplete Huffman string")
    return bytes(decoded)

def encode_prefixed_string(data: bytes, prefix_bits: int, prefix_mask: int = 0, *, huffman: bool = True) -> bytes:
    payload = data
    huffman_flag = 0
    if huffman and data:
        encoded = huffman_encode(data)
        if len(encoded) < len(data):
            payload = encoded
            huffman_flag = 1 << (prefix_bits - 1)
    return encode_prefixed_integer(len(payload), prefix_bits - 1, prefix_mask | huffman_flag) + payload

def decode_prefixed_string(
    data: bytes,
    offset: int,
    prefix_bits: int,
    *,
    max_length: int | None = None,
    max_decoded_length: int | None = None,
    max_integer_octets: int | None = None,
) -> tuple[bytes, int]:
    if offset >= len(data):
        raise ProtocolError("header-compression string underflow")
    huffman = bool(data[offset] & (1 << (prefix_bits - 1)))
    length, offset = decode_prefixed_integer(data, offset, prefix_bits - 1, max_octets=max_integer_octets, max_value=max_length)
    if max_length is not None and length > max_length:
        raise ProtocolError("header-compression string exceeds configured maximum")
    end = offset + length
    if end > len(data):
        raise ProtocolError("header-compression string overflow")
    payload = data[offset:end]
    if huffman:
        payload = huffman_decode(payload, max_output_length=max_decoded_length)
    elif max_decoded_length is not None and len(payload) > max_decoded_length:
        raise ProtocolError("header-compression string exceeds configured maximum")
    return payload, end
