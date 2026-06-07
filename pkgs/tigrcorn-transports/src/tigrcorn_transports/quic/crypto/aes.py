from __future__ import annotations

from tigrcorn_core.errors import ProtocolError

def _rotl8(value: int, shift: int) -> int:
    shift &= 7
    return ((value << shift) | (value >> (8 - shift))) & 0xFF



def _gf_mul8(left: int, right: int) -> int:
    product = 0
    a = left & 0xFF
    b = right & 0xFF
    for _ in range(8):
        if b & 1:
            product ^= a
        carry = a & 0x80
        a = (a << 1) & 0xFF
        if carry:
            a ^= 0x1B
        b >>= 1
    return product



def _gf_pow8(value: int, exponent: int) -> int:
    result = 1
    base = value & 0xFF
    exp = exponent
    while exp:
        if exp & 1:
            result = _gf_mul8(result, base)
        base = _gf_mul8(base, base)
        exp >>= 1
    return result



def _gf_inv8(value: int) -> int:
    if value == 0:
        return 0
    return _gf_pow8(value, 254)



def _generate_aes_sbox() -> list[int]:
    table: list[int] = []
    for byte in range(256):
        inv = _gf_inv8(byte)
        transformed = inv ^ _rotl8(inv, 1) ^ _rotl8(inv, 2) ^ _rotl8(inv, 3) ^ _rotl8(inv, 4) ^ 0x63
        table.append(transformed & 0xFF)
    return table


_AES_SBOX = _generate_aes_sbox()



def _sub_word(word: list[int]) -> list[int]:
    return [_AES_SBOX[byte] for byte in word]



def _rot_word(word: list[int]) -> list[int]:
    return [word[1], word[2], word[3], word[0]]



def _expand_aes_key(key: bytes) -> tuple[list[bytes], int]:
    if len(key) not in {16, 24, 32}:
        raise ValueError('AES key must be 16, 24, or 32 bytes long')
    nk = len(key) // 4
    nr_by_nk = {4: 10, 6: 12, 8: 14}
    nr = nr_by_nk[nk]
    words: list[list[int]] = [list(key[index:index + 4]) for index in range(0, len(key), 4)]
    rcon = 1
    while len(words) < 4 * (nr + 1):
        temp = list(words[-1])
        if len(words) % nk == 0:
            temp = _sub_word(_rot_word(temp))
            temp[0] ^= rcon
            rcon = _gf_mul8(rcon, 2)
        elif nk > 6 and len(words) % nk == 4:
            temp = _sub_word(temp)
        word = [left ^ right for left, right in zip(words[-nk], temp)]
        words.append(word)
    round_keys = [bytes(byte for word in words[index:index + 4] for byte in word) for index in range(0, len(words), 4)]
    return round_keys, nr



def _mix_single_column(column: list[int]) -> list[int]:
    a0, a1, a2, a3 = column
    return [
        _gf_mul8(a0, 2) ^ _gf_mul8(a1, 3) ^ a2 ^ a3,
        a0 ^ _gf_mul8(a1, 2) ^ _gf_mul8(a2, 3) ^ a3,
        a0 ^ a1 ^ _gf_mul8(a2, 2) ^ _gf_mul8(a3, 3),
        _gf_mul8(a0, 3) ^ a1 ^ a2 ^ _gf_mul8(a3, 2),
    ]



def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError('AES block must be exactly 16 bytes')
    round_keys, nr = _expand_aes_key(key)
    state = [left ^ right for left, right in zip(block, round_keys[0])]
    for round_index in range(1, nr):
        state = [_AES_SBOX[byte] for byte in state]
        state = [
            state[0], state[5], state[10], state[15],
            state[4], state[9], state[14], state[3],
            state[8], state[13], state[2], state[7],
            state[12], state[1], state[6], state[11],
        ]
        mixed = [0] * 16
        for column_index in range(4):
            start = column_index * 4
            mixed[start:start + 4] = _mix_single_column(state[start:start + 4])
        state = [left ^ right for left, right in zip(mixed, round_keys[round_index])]
    state = [_AES_SBOX[byte] for byte in state]
    state = [
        state[0], state[5], state[10], state[15],
        state[4], state[9], state[14], state[3],
        state[8], state[13], state[2], state[7],
        state[12], state[1], state[6], state[11],
    ]
    state = [left ^ right for left, right in zip(state, round_keys[nr])]
    return bytes(state)


# --- AES-GCM ----------------------------------------------------------------------

