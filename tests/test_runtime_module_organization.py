from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "pkgs" / "tigrcorn-runtime" / "src" / "tigrcorn_runtime"
RUNNER_ROOT = RUNTIME_ROOT / "server" / "runner"


def test_tigrcorn_runtime_files_under_400_loc() -> None:
    oversized: list[tuple[int, str]] = []
    for path in RUNTIME_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 400:
            oversized.append((line_count, str(path.relative_to(ROOT))))

    assert oversized == []


def test_runner_public_imports_preserved() -> None:
    from tigrcorn_runtime.server.runner import TigrCornServer

    assert TigrCornServer.__name__ == "TigrCornServer"


def test_root_runner_compat_import_preserved() -> None:
    from tigrcorn.server.runner import TigrCornServer as root_server
    from tigrcorn_runtime.server.runner import TigrCornServer as package_server

    assert root_server is package_server


def test_runner_http11_helpers_are_isolated() -> None:
    http11_sources = "\n".join(
        (RUNNER_ROOT / name).read_text(encoding="utf-8")
        for name in ("http11.py", "http11_send.py", "http11_serve.py")
    )
    other_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in RUNNER_ROOT.glob("*.py")
        if path.name not in {"http11.py", "http11_send.py", "http11_serve.py"}
    )

    assert "_handle_http11_connection" in http11_sources
    assert "_serve_http11_request" in http11_sources
    assert "_send_http11_body_segments" in http11_sources
    assert "async def _handle_http11_connection" not in other_sources
    assert "async def _serve_http11_request" not in other_sources


def test_runner_listener_helpers_are_isolated() -> None:
    listener_source = (RUNNER_ROOT / "listeners.py").read_text(encoding="utf-8")
    other_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in RUNNER_ROOT.glob("*.py")
        if path.name != "listeners.py"
    )

    assert "async def _make_listener" in listener_source
    assert "_record_listener_transport_domains" in listener_source
    assert "async def _make_listener" not in other_sources


def test_runner_diagnostics_helpers_are_isolated() -> None:
    diagnostics_source = (RUNNER_ROOT / "diagnostics.py").read_text(encoding="utf-8")
    other_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in RUNNER_ROOT.glob("*.py")
        if path.name != "diagnostics.py"
    )

    assert "def describe" in diagnostics_source
    assert "transport_domain_diagnostics" in diagnostics_source
    assert "quic_operational_security_evidence" in diagnostics_source
    assert "def describe" not in other_sources


def test_runtime_does_not_own_protocol_handler_implementations() -> None:
    runner_sources = "\n".join(path.read_text(encoding="utf-8") for path in RUNNER_ROOT.glob("*.py"))

    assert "class HTTP2ConnectionHandler" not in runner_sources
    assert "class HTTP3DatagramHandler" not in runner_sources
    assert "class WebSocketConnectionHandler" not in runner_sources
