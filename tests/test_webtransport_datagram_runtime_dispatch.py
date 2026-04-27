from __future__ import annotations

import json
from pathlib import Path

import pytest

from tigrcorn.protocols.http3.codec import SETTING_ENABLE_WEBTRANSPORT, SETTING_H3_DATAGRAM


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"
H3_HANDLER_PATH = ROOT / "pkgs" / "tigrcorn-protocols" / "src" / "tigrcorn_protocols" / "http3" / "handler.py"
QUIC_STREAMS_PATH = ROOT / "pkgs" / "tigrcorn-transports" / "src" / "tigrcorn_transports" / "quic" / "streams.py"
QUIC_CONNECTION_PATH = ROOT / "pkgs" / "tigrcorn-transports" / "src" / "tigrcorn_transports" / "quic" / "connection.py"
DEMO_SERVER_PATH = ROOT / "examples" / "webtransport_mtls_demo" / "server.py"

FEATURE_ID = "feat:webtransport-h3-quic-datagram-runtime-dispatch"
ISSUE_ID = "iss:webtransport-h3-quic-datagram-runtime-dispatch"
TEST_ID = "tst:pytest-tests-test-webtransport-datagram-runtime-dispatch-py"


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _by_id(rows: object) -> dict[str, dict[str, object]]:
    assert isinstance(rows, list)
    return {str(row["id"]): row for row in rows if isinstance(row, dict)}


def test_ssot_feature_record_tracks_runtime_datagram_dispatch() -> None:
    features = _by_id(_registry()["features"])

    feature = features[FEATURE_ID]

    assert feature["title"] == "WebTransport H3/QUIC DATAGRAM runtime dispatch"
    assert feature["implementation_status"] == "absent"
    assert feature["plan"]["horizon"] == "current"
    assert feature["plan"]["slot"] == "webtransport-runtime"
    assert "feat:webtransport-h3-quic-datagram-events" in feature["requires"]


def test_ssot_issue_record_blocks_release_until_runtime_dispatch_exists() -> None:
    issues = _by_id(_registry()["issues"])

    issue = issues[ISSUE_ID]

    assert issue["status"] == "open"
    assert issue["severity"] == "high"
    assert issue["release_blocking"] is True
    assert issue["feature_ids"] == [FEATURE_ID]
    assert TEST_ID in issue["test_ids"]


def test_ssot_test_record_links_to_feature_and_planned_pytest_file() -> None:
    tests = _by_id(_registry()["tests"])

    test = tests[TEST_ID]

    assert test["status"] == "planned"
    assert test["kind"] == "pytest"
    assert test["path"] == "tests/test_webtransport_datagram_runtime_dispatch.py"
    assert test["feature_ids"] == [FEATURE_ID]


def test_webtransport_settings_advertise_h3_datagram_support() -> None:
    assert SETTING_H3_DATAGRAM == 0x33
    assert SETTING_ENABLE_WEBTRANSPORT == 0x2B603742


@pytest.mark.xfail(strict=True, reason="QUIC DATAGRAM frame support is not implemented yet.")
def test_quic_datagram_frame_constant_is_declared() -> None:
    source = QUIC_STREAMS_PATH.read_text(encoding="utf-8")

    assert "FRAME_DATAGRAM = 0x30" in source


@pytest.mark.xfail(strict=True, reason="QUIC receive does not emit DATAGRAM frame events yet.")
def test_quic_receive_emits_single_datagram_event_kind() -> None:
    source = QUIC_CONNECTION_PATH.read_text(encoding="utf-8")

    assert "kind='datagram'" in source


@pytest.mark.xfail(strict=True, reason="QUIC send-side DATAGRAM frame API is not implemented yet.")
def test_quic_connection_exposes_datagram_sender() -> None:
    source = QUIC_CONNECTION_PATH.read_text(encoding="utf-8")

    assert "def send_datagram_frame(" in source


@pytest.mark.xfail(strict=True, reason="Accepted WebTransport CONNECT streams are not dispatched to ASGI yet.")
def test_webtransport_connect_starts_asgi_session_task() -> None:
    source = H3_HANDLER_PATH.read_text(encoding="utf-8")

    assert "asyncio.create_task" in source
    assert "webtransport.connect" in source
    assert "_start_webtransport_app" in source


@pytest.mark.xfail(strict=True, reason="Incoming QUIC DATAGRAM frames are not translated to ASGI receive events yet.")
def test_incoming_datagram_dispatches_asgi_receive_event() -> None:
    source = H3_HANDLER_PATH.read_text(encoding="utf-8")

    assert "webtransport.datagram.receive" in source
    assert "datagram_id" in source


@pytest.mark.xfail(strict=True, reason="ASGI webtransport.datagram.send events are not encoded as QUIC DATAGRAM frames yet.")
def test_outgoing_asgi_datagram_send_uses_quic_datagram_frame() -> None:
    source = H3_HANDLER_PATH.read_text(encoding="utf-8")

    assert "webtransport.datagram.send" in source
    assert "send_datagram_frame(" in source


@pytest.mark.xfail(strict=True, reason="WebTransport DATAGRAM payload limits are not enforced on runtime dispatch yet.")
def test_datagram_payload_limit_uses_webtransport_listener_configuration() -> None:
    source = H3_HANDLER_PATH.read_text(encoding="utf-8")

    assert "webtransport.max_datagram_size" in source
    assert "max_datagram_size" in source
    assert "webtransport.datagram.receive" in source


@pytest.mark.xfail(strict=True, reason="The demo app currently echoes DATAGRAMs but does not log them for container debugging.")
def test_demo_server_logs_datagram_receive_and_acknowledgement() -> None:
    source = DEMO_SERVER_PATH.read_text(encoding="utf-8")

    assert "logging.getLogger" in source
    assert "webtransport.datagram.receive" in source
    assert "datagram received" in source
    assert "datagram acknowledged" in source
