from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTTP2_PATH = (
    ROOT
    / "pkgs"
    / "tigrcorn-protocols"
    / "src"
    / "tigrcorn_protocols"
    / "http2"
)
HANDLER_PATH = HTTP2_PATH / "handler"


def _package_source(path: Path) -> str:
    return "\n".join(file.read_text(encoding="utf-8") for file in sorted(path.glob("*.py")))


def test_http2_python_files_stay_under_400_loc() -> None:
    oversized = []
    for path in sorted(HTTP2_PATH.rglob("*.py")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 400:
            oversized.append((path.relative_to(ROOT).as_posix(), line_count))

    assert oversized == []


def test_http2_public_imports_remain_compatible() -> None:
    from tigrcorn.protocols.http2 import HTTP2ConnectionHandler as RootPackageHandler
    from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler as RootHandler
    from tigrcorn_protocols.http2 import HTTP2ConnectionHandler as PackageHandler
    from tigrcorn_protocols.http2.handler import HTTP2ConnectionHandler as DirectHandler

    assert RootHandler is DirectHandler
    assert RootPackageHandler is DirectHandler
    assert PackageHandler is DirectHandler


def test_http2_connect_transport_adjacent_code_is_isolated() -> None:
    connect_source = (HANDLER_PATH / "connect.py").read_text(encoding="utf-8")
    other_handler_source = "\n".join(
        file.read_text(encoding="utf-8")
        for file in sorted(HANDLER_PATH.glob("*.py"))
        if file.name != "connect.py"
    )

    assert "class _HTTP2ConnectTunnel" in connect_source
    assert "asyncio.open_connection" in connect_source
    assert "parse_connect_authority" in connect_source
    assert "asyncio.open_connection" not in other_handler_source


def test_http2_io_adapter_code_is_isolated() -> None:
    io_source = (HANDLER_PATH / "io.py").read_text(encoding="utf-8")
    package_source = _package_source(HANDLER_PATH)

    assert "def _write_raw(" in io_source
    assert "async def _ensure_preface(" in io_source
    assert "await self.reader.readexactly" in io_source
    assert package_source.count("def _write_raw(") == 1


def test_http2_protocol_package_does_not_own_listener_setup() -> None:
    source = _package_source(HTTP2_PATH) + "\n" + _package_source(HANDLER_PATH)

    forbidden = (
        "create_server(",
        "start_server(",
        "sock.bind(",
        "bind(",
        "listen(",
    )
    for token in forbidden:
        assert token not in source

