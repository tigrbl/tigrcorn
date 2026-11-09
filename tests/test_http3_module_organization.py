from __future__ import annotations

from pathlib import Path


HTTP3_PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pkgs"
    / "tigrcorn-protocols"
    / "src"
    / "tigrcorn_protocols"
    / "http3"
)


def test_http3_python_files_stay_under_400_loc() -> None:
    oversized = {
        path.relative_to(HTTP3_PACKAGE_ROOT).as_posix(): len(path.read_text().splitlines())
        for path in HTTP3_PACKAGE_ROOT.rglob("*.py")
        if len(path.read_text().splitlines()) > 400
    }

    assert oversized == {}


def test_http3_public_imports_remain_compatible() -> None:
    from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler as RootHTTP3DatagramHandler
    from tigrcorn.protocols.http3.handler import HTTP3Session as RootHTTP3Session
    from tigrcorn_protocols.http3 import HTTP3ConnectionCore
    from tigrcorn_protocols.http3.handler import HTTP3DatagramHandler, HTTP3Session
    from tigrcorn_protocols.http3.handler.webtransport import _HTTP3WebTransportSession
    from tigrcorn_protocols.http3.qpack import QpackDecoder, QpackEncoder, decode_field_section, encode_field_section
    from tigrcorn_protocols.http3.streams import STREAM_TYPE_QPACK_DECODER, STREAM_TYPE_QPACK_ENCODER

    assert RootHTTP3DatagramHandler is HTTP3DatagramHandler
    assert RootHTTP3Session is HTTP3Session
    assert HTTP3ConnectionCore.__name__ == "HTTP3ConnectionCore"
    assert QpackDecoder.__name__ == "QpackDecoder"
    assert QpackEncoder.__name__ == "QpackEncoder"
    assert callable(encode_field_section)
    assert callable(decode_field_section)
    assert STREAM_TYPE_QPACK_ENCODER == 0x02
    assert STREAM_TYPE_QPACK_DECODER == 0x03
    assert _HTTP3WebTransportSession.__name__ == "_HTTP3WebTransportSession"
