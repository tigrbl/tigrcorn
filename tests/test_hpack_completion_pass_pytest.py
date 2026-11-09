import importlib.util

import pytest

from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.http2.hpack import (
    HPACKDecoder,
    HPACKEncoder,
    decode_header_block,
    encode_header,
    encode_header_block,
    encode_integer,
)


def test_dynamic_table_size_update_must_appear_at_start_of_block() -> None:
    block = encode_header(b":method", b"GET") + encode_integer(0, 5, 0x20)
    with pytest.raises(ProtocolError):
        HPACKDecoder().decode_header_block(block)


def test_header_list_size_limit_is_enforced() -> None:
    block = encode_header_block([(b"x-large", b"a" * 64)])
    with pytest.raises(ProtocolError):
        decode_header_block(block, max_header_list_size=32)


def test_malformed_integer_huffman_and_truncation_inputs_are_rejected() -> None:
    decoder = HPACKDecoder()
    with pytest.raises(ProtocolError):
        decoder.decode_header_block(b"@")
    with pytest.raises(ProtocolError):
        decoder.decode_header_block(b"@\x81\xff\x00")
    with pytest.raises(ProtocolError):
        decoder.decode_header_block(b"\xff" + (b"\x81" * 9) + b"\x00")


def test_header_block_size_limit_is_enforced() -> None:
    block = encode_header_block([(b"x-long", b"a" * 128)])
    with pytest.raises(ProtocolError):
        HPACKDecoder(max_header_block_size=16).decode_header_block(block)


@pytest.mark.skipif(importlib.util.find_spec("hpack") is None, reason="third-party hpack package is not installed")
def test_differential_roundtrip_against_independent_hpack_library() -> None:
    from hpack import Decoder as ExternalDecoder
    from hpack import Encoder as ExternalEncoder

    def _external_to_bytes(headers):
        converted = []
        for name, value in headers:
            converted.append((name.encode("ascii") if isinstance(name, str) else name, value.encode("utf-8") if isinstance(value, str) else value))
        return converted

    sequence = [
        [(b":method", b"GET"), (b":path", b"/"), (b"x-test", b"alpha")],
        [(b":method", b"GET"), (b":path", b"/"), (b"x-test", b"alpha")],
        [(b":method", b"GET"), (b":path", b"/second"), (b"x-test", b"alpha")],
        [(b":method", b"POST"), (b":path", b"/submit"), (b"content-type", b"application/json")],
    ]

    external_encoder = ExternalEncoder()
    external_decoder = ExternalDecoder()
    local_encoder = HPACKEncoder()
    local_decoder = HPACKDecoder()

    for headers in sequence:
        external_block = external_encoder.encode(headers)
        assert local_decoder.decode_header_block(external_block) == headers

        local_block = local_encoder.encode_header_block(headers)
        assert _external_to_bytes(external_decoder.decode(local_block)) == headers
