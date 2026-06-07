from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECURITY_ROOT = ROOT / "pkgs" / "tigrcorn-security" / "src" / "tigrcorn_security"


def test_tigrcorn_security_files_under_400_loc() -> None:
    oversized: list[tuple[int, str]] = []
    for path in SECURITY_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 400:
            oversized.append((line_count, str(path.relative_to(ROOT))))

    assert oversized == []


def test_tls_public_imports_preserved() -> None:
    from tigrcorn_security.tls import (
        PackageOwnedTLSConnection,
        build_server_ssl_context,
        verify_certificate_chain,
        wrap_server_tls_connection,
    )

    assert PackageOwnedTLSConnection.__name__ == "PackageOwnedTLSConnection"
    assert callable(build_server_ssl_context)
    assert callable(verify_certificate_chain)
    assert callable(wrap_server_tls_connection)


def test_tls13_handshake_public_imports_preserved() -> None:
    from tigrcorn_security.tls13.handshake import (
        QuicTlsHandshakeDriver,
        TlsAlertError,
        TransportParameters,
        generate_self_signed_certificate,
    )

    assert QuicTlsHandshakeDriver.__name__ == "QuicTlsHandshakeDriver"
    assert issubclass(TlsAlertError, Exception)
    assert TransportParameters.__name__ == "TransportParameters"
    assert callable(generate_self_signed_certificate)


def test_tls13_extensions_public_imports_preserved() -> None:
    from tigrcorn_security.tls13.extensions import (
        TransportParameters,
        decode_extensions,
        encode_extensions,
        extension_dict,
    )

    assert TransportParameters.__name__ == "TransportParameters"
    assert callable(encode_extensions)
    assert callable(decode_extensions)
    assert callable(extension_dict)


def test_x509_path_public_imports_preserved() -> None:
    from tigrcorn_security.x509.path import (
        CertificateValidationPolicy,
        RevocationMode,
        verify_certificate_chain,
    )

    assert CertificateValidationPolicy.__name__ == "CertificateValidationPolicy"
    assert RevocationMode.REQUIRE.value == "require"
    assert callable(verify_certificate_chain)


def test_root_security_compat_wrappers_resolve_package_surfaces() -> None:
    from tigrcorn.security.tls import build_server_ssl_context
    from tigrcorn.security.tls13.handshake import QuicTlsHandshakeDriver
    from tigrcorn.security.tls13.extensions import TransportParameters
    from tigrcorn.security.x509.path import CertificateValidationPolicy

    assert callable(build_server_ssl_context)
    assert QuicTlsHandshakeDriver.__name__ == "QuicTlsHandshakeDriver"
    assert TransportParameters.__name__ == "TransportParameters"
    assert CertificateValidationPolicy.__name__ == "CertificateValidationPolicy"


def test_security_package_does_not_import_runtime_server_internals() -> None:
    offenders: list[str] = []
    for path in SECURITY_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "tigrcorn_runtime" in text or "tigrcorn_runtime.server" in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_quic_transport_parameter_codec_stays_in_tls13_extensions() -> None:
    extensions_root = SECURITY_ROOT / "tls13" / "extensions"
    extension_sources = "\n".join(path.read_text(encoding="utf-8") for path in extensions_root.rglob("*.py"))
    transport_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "pkgs" / "tigrcorn-transports" / "src").rglob("*.py")
    )

    assert "def encode_quic_transport_parameters" in extension_sources
    assert "def decode_quic_transport_parameters" in extension_sources
    assert "def encode_quic_transport_parameters" not in transport_sources
    assert "def decode_quic_transport_parameters" not in transport_sources
