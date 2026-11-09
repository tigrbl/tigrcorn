from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RELEASE_ROOT = "docs/review/conformance/releases/0.3.9/release-0.3.9/"
BOUNDARY_DOC = "docs/review/conformance/CERTIFICATION_BOUNDARY.md"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert_contains_all(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text


def test_readme_references_canonical_boundary_release_root_and_current_state() -> None:
    text = _read("README.md")
    _assert_contains_all(
        text,
        BOUNDARY_DOC,
        CANONICAL_RELEASE_ROOT,
        "external_matrix.same_stack_replay.json",
        "external_matrix.release.json",
        "external_matrix.current_release.json",
        "certifiably fully RFC compliant under the authoritative certification boundary",
        "docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md",
    )


def test_http3_quic_and_websocket_docs_reference_boundary_and_current_blockers() -> None:
    http3 = _read("docs/protocols/http3.md")
    quic = _read("docs/protocols/quic.md")
    websocket = _read("docs/protocols/websocket.md")
    for text in (http3, quic, websocket):
        assert BOUNDARY_DOC in text
        assert CANONICAL_RELEASE_ROOT in text
    _assert_contains_all(
        http3,
        "preserved passing third-party HTTP/3 request/response",
        "RFC 9220 scenarios",
        "package-owned TCP/TLS condition",
    )
    _assert_contains_all(
        quic,
        "OpenSSL QUIC handshake",
        "preserves passing third-party HTTP/3 feature-axis scenarios",
        "package-wide RFC 8446 target is no longer blocked by the public TCP/TLS listener path",
    )
    _assert_contains_all(
        websocket,
        "RFC 8441 WebSocket-over-HTTP/2",
        "RFC 9220 WebSocket-over-HTTP/3",
        "RFC 7692 across carriers",
    )


def test_conformance_boundary_and_status_docs_are_aligned() -> None:
    boundary = _read("docs/review/conformance/CERTIFICATION_BOUNDARY.md")
    conformance = _read("docs/review/conformance/README.md")
    status = _read("docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md")
    current = _read("docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md")
    hardening = _read("docs/review/conformance/reports/RFC_HARDENING_REPORT.md")
    for text in (boundary, conformance, status, current, hardening):
        assert BOUNDARY_DOC in text
    _assert_contains_all(
        conformance,
        CANONICAL_RELEASE_ROOT,
        "certifiably fully RFC compliant under the authoritative certification boundary",
    )
    _assert_contains_all(
        current,
        "certifiably fully RFC compliant",
        "evaluate_release_gates",
        "RFC 9220",
    )
    _assert_contains_all(
        status,
        "certifiably fully RFC compliant",
        "independent-certification",
        "aioquic",
    )
    _assert_contains_all(
        hardening,
        "preserved third-party `aioquic` HTTP/3 request/response artifacts",
        "package-owned TCP/TLS listener-path integration",
    )
