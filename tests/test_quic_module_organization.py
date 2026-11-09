from __future__ import annotations

from pathlib import Path


QUIC_PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pkgs"
    / "tigrcorn-transports"
    / "src"
    / "tigrcorn_transports"
    / "quic"
)


def test_quic_python_files_stay_under_400_loc() -> None:
    oversized = {
        path.relative_to(QUIC_PACKAGE_ROOT).as_posix(): len(path.read_text().splitlines())
        for path in QUIC_PACKAGE_ROOT.rglob("*.py")
        if len(path.read_text().splitlines()) > 400
    }

    assert oversized == {}


def test_quic_public_imports_remain_compatible() -> None:
    from tigrcorn.transports.quic import QuicConnection as RootQuicConnection
    from tigrcorn.transports.quic.connection import PACKET_SPACE_APPLICATION as RootPacketSpaceApplication
    from tigrcorn.transports.quic.connection import QuicConnection as RootConnectionModuleQuicConnection
    from tigrcorn.transports.quic.crypto import hkdf_extract as root_hkdf_extract
    from tigrcorn.transports.quic.recovery import QuicLossRecovery as RootQuicLossRecovery
    from tigrcorn.transports.quic.security import QuicOperationalSecurityRuntime as RootSecurityRuntime
    from tigrcorn.transports.quic.streams import QuicStreamFrame as RootQuicStreamFrame
    from tigrcorn.transports.quic.streams import decode_frame as root_decode_frame
    from tigrcorn.transports.quic.streams import encode_frame as root_encode_frame
    from tigrcorn_transports.quic import QuicConnection
    from tigrcorn_transports.quic.connection import PACKET_SPACE_APPLICATION, QuicEvent
    from tigrcorn_transports.quic.crypto import hkdf_extract, protect_quic_packet
    from tigrcorn_transports.quic.recovery import QuicLossRecovery, quic_recovery_rule_table
    from tigrcorn_transports.quic.security import QuicOperationalSecurityRuntime, quic_security_checks
    from tigrcorn_transports.quic.streams import QuicStreamFrame, decode_frame, encode_frame

    assert RootQuicConnection is QuicConnection
    assert RootConnectionModuleQuicConnection is QuicConnection
    assert RootPacketSpaceApplication == PACKET_SPACE_APPLICATION == "application"
    assert QuicEvent.__name__ == "QuicEvent"
    assert RootQuicStreamFrame is QuicStreamFrame
    assert root_encode_frame is encode_frame
    assert root_decode_frame is decode_frame
    assert root_hkdf_extract is hkdf_extract
    assert callable(protect_quic_packet)
    assert RootQuicLossRecovery is QuicLossRecovery
    assert callable(quic_recovery_rule_table)
    assert RootSecurityRuntime is QuicOperationalSecurityRuntime
    assert callable(quic_security_checks)
