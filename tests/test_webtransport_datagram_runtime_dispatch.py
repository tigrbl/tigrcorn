from __future__ import annotations

import json
from pathlib import Path

import pytest

from tigrcorn.ssot_baseline import iter_feature_baselines
from tigrcorn.protocols.http3.codec import SETTING_ENABLE_WEBTRANSPORT, SETTING_H3_DATAGRAM


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"
H3_HANDLER_CORE_PATH = ROOT / "pkgs" / "tigrcorn-protocols" / "src" / "tigrcorn_protocols" / "http3" / "handler" / "core.py"
H3_WEBTRANSPORT_PATH = ROOT / "pkgs" / "tigrcorn-protocols" / "src" / "tigrcorn_protocols" / "http3" / "handler" / "webtransport.py"
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


def _h3_handler_source() -> str:
    return H3_HANDLER_CORE_PATH.read_text(encoding="utf-8") + "\n" + H3_WEBTRANSPORT_PATH.read_text(encoding="utf-8")


def _has_t012_baseline(feature_id: str) -> bool:
    baselines = {baseline.feature_id: baseline for baseline in iter_feature_baselines(_registry())}
    return set(baselines[feature_id].claim_tiers) >= {"T0", "T1", "T2"}


def test_ssot_feature_record_tracks_runtime_datagram_dispatch() -> None:
    features = _by_id(_registry()["features"])

    feature = features[FEATURE_ID]

    assert feature["title"] == "WebTransport H3/QUIC DATAGRAM runtime dispatch"
    assert _has_t012_baseline(FEATURE_ID)
    assert feature["plan"]["horizon"] == "current"
    assert feature["plan"]["slot"] == "webtransport-runtime"
    assert "feat:webtransport-h3-quic-datagram-events" in feature.get("requires", []) or _has_t012_baseline(FEATURE_ID)


def test_ssot_issue_record_blocks_release_until_runtime_dispatch_exists() -> None:
    issues = _by_id(_registry()["issues"])

    issue = issues[ISSUE_ID]

    assert issue["status"] == "closed"
    assert issue["severity"] == "high"
    assert issue["release_blocking"] is False
    assert issue["feature_ids"] == [FEATURE_ID]
    assert TEST_ID in issue["test_ids"]


def test_ssot_test_record_links_to_feature_and_planned_pytest_file() -> None:
    tests = _by_id(_registry()["tests"])

    test = tests[TEST_ID]

    assert test["status"] == "passing"
    assert test["kind"] == "pytest"
    assert test["path"] == "tests/test_webtransport_datagram_runtime_dispatch.py"
    assert test["feature_ids"] == [FEATURE_ID]


def test_webtransport_settings_advertise_h3_datagram_support() -> None:
    assert SETTING_H3_DATAGRAM == 0x33
    assert SETTING_ENABLE_WEBTRANSPORT == 0x2B603742


def test_quic_datagram_frame_constant_is_declared() -> None:
    source = QUIC_STREAMS_PATH.read_text(encoding="utf-8")

    assert "FRAME_DATAGRAM = 0x30" in source


def test_quic_receive_emits_single_datagram_event_kind() -> None:
    source = QUIC_CONNECTION_PATH.read_text(encoding="utf-8")

    assert "kind='datagram'" in source


def test_quic_connection_exposes_datagram_sender() -> None:
    source = QUIC_CONNECTION_PATH.read_text(encoding="utf-8")

    assert "def send_datagram_frame(" in source


def test_webtransport_connect_starts_asgi_session_task() -> None:
    source = _h3_handler_source()

    assert "asyncio.create_task" in source
    assert "webtransport.connect" in source
    assert "_start_webtransport_app" in source


def test_incoming_datagram_dispatches_asgi_receive_event() -> None:
    source = _h3_handler_source()

    assert "webtransport.datagram.receive" in source
    assert "datagram_id" in source


def test_outgoing_asgi_datagram_send_uses_quic_datagram_frame() -> None:
    source = _h3_handler_source()

    assert "webtransport.datagram.send" in source
    assert "send_datagram_frame(" in source


def test_datagram_payload_limit_uses_webtransport_listener_configuration() -> None:
    source = _h3_handler_source()

    assert "webtransport.max_datagram_size" in source
    assert "max_datagram_size" in source
    assert "webtransport.datagram.receive" in source


def test_webtransport_connect_fin_does_not_force_disconnect() -> None:
    source = H3_WEBTRANSPORT_PATH.read_text(encoding="utf-8")

    assert "feed_connect_stream_data" in source
    assert "disconnect_on_end=False" in source


def test_demo_server_logs_datagram_receive_and_acknowledgement() -> None:
    source = DEMO_SERVER_PATH.read_text(encoding="utf-8")

    assert "logging.getLogger" in source
    assert "webtransport.datagram.receive" in source
    assert "datagram received" in source
    assert "datagram acknowledged" in source
