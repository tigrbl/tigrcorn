from __future__ import annotations

import asyncio
from importlib import metadata as importlib_metadata
from pathlib import Path
from types import SimpleNamespace
import tomllib

import tigr_asgi_contract as contract
from tigr_asgi_contract.registry import PROTOCOLS

from tigrcorn.asgi.scopes.http import build_http_scope
from tigrcorn.asgi.scopes.lifespan import build_lifespan_scope
from tigrcorn.asgi.scopes.websocket import build_websocket_scope
from tigrcorn.contract import (
    SUPPORTED_SCOPE_TYPES,
    emit_complete,
    http_disconnect,
    http_request,
    http_response_body,
    http_response_pathsend,
    http_response_start,
    lifespan_shutdown,
    lifespan_shutdown_complete,
    lifespan_shutdown_failed,
    lifespan_startup,
    lifespan_startup_complete,
    lifespan_startup_failed,
    validate_scope,
    websocket_accept,
    websocket_close,
    websocket_connect,
    websocket_disconnect,
    websocket_receive,
    websocket_send,
    webtransport_accept,
    webtransport_close,
    webtransport_connect,
    webtransport_datagram_receive,
    webtransport_datagram_send,
    webtransport_disconnect,
    webtransport_stream_receive,
    webtransport_stream_send,
)
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn_protocols.http3.handler.webtransport import _HTTP3WebTransportSession
from tests.contract_closure_assertions import ContractClosureAssertions
from tools.package_boundaries import PACKAGE_BY_DISTRIBUTION


ROOT = Path(__file__).resolve().parents[1]


def _project_dependencies(path: Path) -> set[str]:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    return set(project.get("dependencies", []))


def _project_version(path: Path) -> str:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    return str(project["version"])


def _request(
    *,
    method: str = "GET",
    target: str = "/peer",
    headers: list[tuple[bytes, bytes]] | None = None,
    websocket_upgrade: bool = False,
) -> ParsedRequest:
    path, _, query = target.partition("?")
    return ParsedRequest(
        method=method,
        target=target,
        path=path or "/",
        raw_path=(path or "/").encode("ascii"),
        query_string=query.encode("ascii"),
        http_version="1.1",
        headers=headers or [(b"host", b"example.test")],
        body=b"",
        keep_alive=True,
        expect_continue=False,
        websocket_upgrade=websocket_upgrade,
    )


async def _captured_webtransport_scope() -> dict:
    captured: dict[str, object] = {}

    class LocalCid:
        def hex(self) -> str:
            return "local-cid"

    class Handler:
        config = SimpleNamespace(webtransport=SimpleNamespace(max_streams=4))

        async def app(self, scope: dict, receive, send) -> None:
            captured["scope"] = scope
            captured["first_event"] = await receive()

        def _webtransport_security_extension(self, session) -> dict[str, object]:
            return {"tls": True, "alpn": "h3"}

        def _webtransport_transport_extension(self, session) -> dict[str, object]:
            return {"kind": "quic", "connection_id": session.quic.local_cid.hex()}

        def _webtransport_max_datagram_size(self) -> int:
            return 1200

        async def _send_webtransport_stream_data(self, *args, **kwargs) -> None:
            return None

        def _on_webtransport_stream_closed(self, session, stream_id: int) -> None:
            return None

    session = SimpleNamespace(quic=SimpleNamespace(local_cid=LocalCid()))
    transport = _HTTP3WebTransportSession(
        handler=Handler(),
        session=session,
        stream_id=4,
        request=_request(method="CONNECT", target="/wt"),
        client=("127.0.0.1", 10001),
        server=("127.0.0.1", 443),
        scheme="https",
        endpoint=SimpleNamespace(),
    )
    await transport.start()
    assert transport.task is not None
    await transport.task
    assert captured["first_event"] == {"type": "webtransport.connect", "session_id": "h3-4"}
    scope = captured["scope"]
    assert isinstance(scope, dict)
    return scope


def _runtime_scopes_by_peer_type() -> dict[str, dict]:
    return {
        "http": build_http_scope(
            _request(),
            client=("127.0.0.1", 10001),
            server=("127.0.0.1", 80),
            scheme="http",
            extensions={"tigrcorn.unit": {"request_id": "peer-http"}},
        ),
        "websocket": build_websocket_scope(
            _request(
                target="/ws",
                headers=[(b"host", b"example.test"), (b"sec-websocket-protocol", b"chat")],
                websocket_upgrade=True,
            ),
            client=("127.0.0.1", 10001),
            server=("127.0.0.1", 443),
            scheme="wss",
        ),
        "lifespan": build_lifespan_scope(),
        "webtransport": asyncio.run(_captured_webtransport_scope()),
    }


def _peer_event_examples() -> dict[str, dict]:
    return {
        "http.request": http_request("http-1", body=b"hello"),
        "http.disconnect": http_disconnect("http-1"),
        "http.response.start": http_response_start("http-1", status=200),
        "http.response.body": http_response_body("http-1", body=b"ok"),
        "http.response.pathsend": http_response_pathsend("http-1", path="/tmp/index.html"),
        "websocket.connect": websocket_connect("ws-1"),
        "websocket.receive": websocket_receive("ws-1", text="hello"),
        "websocket.disconnect": websocket_disconnect("ws-1", code=1000),
        "websocket.accept": websocket_accept("ws-1", subprotocol="chat"),
        "websocket.send": websocket_send("ws-1", text="ok"),
        "websocket.close": websocket_close("ws-1", code=1000),
        "webtransport.connect": webtransport_connect("wt-1"),
        "webtransport.accept": webtransport_accept("wt-1"),
        "webtransport.stream.receive": webtransport_stream_receive("wt-1", "stream-1", b"in"),
        "webtransport.stream.send": webtransport_stream_send("wt-1", "stream-1", b"out"),
        "webtransport.datagram.receive": webtransport_datagram_receive("wt-1", "datagram-1", b"in"),
        "webtransport.datagram.send": webtransport_datagram_send("wt-1", "datagram-2", b"out"),
        "webtransport.disconnect": webtransport_disconnect("wt-1", code=0),
        "webtransport.close": webtransport_close("wt-1", code=0),
        "lifespan.startup": lifespan_startup("life-1"),
        "lifespan.startup.complete": lifespan_startup_complete("life-1"),
        "lifespan.startup.failed": lifespan_startup_failed("life-1", message="startup failed"),
        "lifespan.shutdown": lifespan_shutdown("life-1"),
        "lifespan.shutdown.complete": lifespan_shutdown_complete("life-1"),
        "lifespan.shutdown.failed": lifespan_shutdown_failed("life-1", message="shutdown failed"),
        "transport.emit.complete": emit_complete("unit-1"),
    }


def test_tigr_asgi_contract_is_external_peer_dependency() -> None:
    boundary = PACKAGE_BY_DISTRIBUTION["tigrcorn-contract"]
    contract_dependencies = _project_dependencies(ROOT / "pkgs" / "tigrcorn-contract" / "pyproject.toml")
    umbrella_dependencies = _project_dependencies(ROOT / "pyproject.toml")

    assert "tigr-asgi-contract" in boundary.depends_on
    assert "tigr-asgi-contract" not in PACKAGE_BY_DISTRIBUTION
    assert any(dependency.startswith("tigr-asgi-contract>=") for dependency in contract_dependencies)
    assert f"tigrcorn-contract=={_project_version(ROOT / 'pkgs' / 'tigrcorn-contract' / 'pyproject.toml')}" in umbrella_dependencies
    assert any(dependency.startswith("tigr-asgi-contract>=") for dependency in umbrella_dependencies)


def test_tigr_asgi_contract_peer_version_matches_installed_surface() -> None:
    assert importlib_metadata.version("tigr-asgi-contract") == contract.CONTRACT_VERSION


def test_tigrcorn_runtime_emits_every_peer_scope_type() -> None:
    peer_scope_types = {scope_type.value for scope_type in contract.ScopeType}
    runtime_scopes = _runtime_scopes_by_peer_type()

    assert set(runtime_scopes) == peer_scope_types
    for scope_type, scope in runtime_scopes.items():
        assert scope["type"] == scope_type
        validate_scope(scope)


def test_tigrcorn_supports_scope_types_used_by_peer_protocol_registry() -> None:
    peer_scope_types = {scope_type.value for scope_type in contract.ScopeType}
    registry_scope_types = {str(row["scope_type"]) for row in PROTOCOLS.values()}

    assert registry_scope_types <= peer_scope_types
    assert peer_scope_types <= set(SUPPORTED_SCOPE_TYPES)


def test_tigrcorn_event_helpers_cover_peer_transport_event_surface() -> None:
    peer_event_types = {event_type.value for event_type in contract.TransportEventType}
    events = _peer_event_examples()

    assert set(events) == peer_event_types
    for event_type, event in events.items():
        assert event["type"] == event_type
        payload = {key: value for key, value in event.items() if key != "type"}
        assert contract.validate_event_payload(event_type, payload)


class TigrASGIContractPeerValidationTests(ContractClosureAssertions):
    def test_tigr_asgi_contract_peer_surface(self) -> None:
        self.assert_contract_validation_surface()
