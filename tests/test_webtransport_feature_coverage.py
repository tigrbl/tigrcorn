from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from examples.webtransport_mtls_demo.server import app as demo_app
from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config, build_config_from_namespace, build_config_from_sources, config_from_mapping
from tigrcorn.contract import (
    asgi3_extensions,
    datagram_identity,
    emit_complete,
    endpoint_metadata,
    security_metadata,
    stream_identity,
    transport_identity,
    validate_event_order,
    webtransport_accept,
    webtransport_close,
    webtransport_connect,
    webtransport_datagram_receive,
    webtransport_datagram_send,
    webtransport_disconnect,
    webtransport_stream_receive,
    webtransport_stream_send,
)
from tigrcorn.errors import ConfigError, ProtocolError
from tigrcorn.protocols.http3.codec import (
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_ENABLE_WEBTRANSPORT,
    SETTING_H3_DATAGRAM,
    decode_settings,
    encode_settings,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".ssot" / "registry.json"
FIXTURE_MANIFEST_PATH = ROOT / "tests" / "fixtures_protocol_scope" / "fixture_manifest.json"

IMPLEMENTED_WEBTRANSPORT_FEATURE_IDS = {
    "feat:contract-webtransport-events",
    "feat:contract-webtransport-scope",
    "feat:contract-webtransport-session-identity",
    "feat:contract-webtransport-stream-identity",
    "feat:webtransport-h3-quic-completion-events",
    "feat:webtransport-h3-quic-datagram-events",
    "feat:webtransport-h3-quic-scope",
    "feat:webtransport-h3-quic-session-events",
    "feat:webtransport-h3-quic-stream-events",
    "feat:webtransport-carrier-fail-closed",
    "feat:webtransport-carrier-normalization",
    "feat:webtransport-config-toml",
    "feat:webtransport-env-var",
    "feat:webtransport-max-datagram-size-flag",
    "feat:webtransport-max-sessions-flag",
    "feat:webtransport-max-streams-flag",
    "feat:webtransport-origin-flag",
    "feat:webtransport-path-flag",
    "feat:webtransport-protocol-cli-flag",
    "feat:webtransport-public-api",
    "feat:fixture-asgi-webtransport-scope",
    "feat:fixture-webtransport-protocol",
}
PLANNED_WEBTRANSPORT_FEATURE_IDS = {
    "feat:webtransport-h3-quic-datagram-runtime-dispatch",
}


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _rows_by_id(name: str) -> dict[str, dict[str, object]]:
    rows = _registry()[name]
    assert isinstance(rows, list)
    return {str(row["id"]): row for row in rows if isinstance(row, dict)}


def test_ssot_declares_every_expected_webtransport_feature() -> None:
    features = _rows_by_id("features")

    for feature_id in IMPLEMENTED_WEBTRANSPORT_FEATURE_IDS | PLANNED_WEBTRANSPORT_FEATURE_IDS:
        assert feature_id in features


def test_ssot_marks_current_webtransport_features_implemented() -> None:
    features = _rows_by_id("features")

    for feature_id in IMPLEMENTED_WEBTRANSPORT_FEATURE_IDS:
        feature = features[feature_id]
        assert feature["implementation_status"] == "implemented"
        assert feature["lifecycle"]["stage"] == "active"


def test_ssot_keeps_datagram_runtime_dispatch_open_until_runtime_exists() -> None:
    feature = _rows_by_id("features")["feat:webtransport-h3-quic-datagram-runtime-dispatch"]
    issue = _rows_by_id("issues")["iss:webtransport-h3-quic-datagram-runtime-dispatch"]

    assert feature["implementation_status"] == "absent"
    assert feature["plan"]["slot"] == "webtransport-runtime"
    assert issue["status"] == "open"
    assert issue["release_blocking"] is True


def test_each_webtransport_feature_has_at_least_one_ssot_test() -> None:
    features = _rows_by_id("features")

    for feature_id in IMPLEMENTED_WEBTRANSPORT_FEATURE_IDS | PLANNED_WEBTRANSPORT_FEATURE_IDS:
        assert features[feature_id]["test_ids"], feature_id


def test_webtransport_category_boundary_tracks_runtime_and_operator_features() -> None:
    boundaries = _rows_by_id("boundaries")
    boundary_features = set(boundaries["bnd:category-webtransport"]["feature_ids"])
    expected = {
        feature_id
        for feature_id in IMPLEMENTED_WEBTRANSPORT_FEATURE_IDS | PLANNED_WEBTRANSPORT_FEATURE_IDS
        if not feature_id.startswith("feat:fixture-")
    }

    assert expected <= boundary_features


def test_webtransport_fixture_manifest_declares_scope_and_protocol_fixtures() -> None:
    manifest = json.loads(FIXTURE_MANIFEST_PATH.read_text(encoding="utf-8"))
    fixture_ids = {fixture["id"] for fixture in manifest["fixtures"]}

    assert "fixture-asgi-webtransport-scope" in fixture_ids
    assert "fixture-webtransport-protocol" in fixture_ids


def test_webtransport_contract_session_events_have_stable_payloads() -> None:
    assert webtransport_connect("s1") == {"type": "webtransport.connect", "session_id": "s1"}
    assert webtransport_accept("s1") == {"type": "webtransport.accept", "session_id": "s1"}
    assert webtransport_disconnect("s1", code=100, reason="done") == {
        "type": "webtransport.disconnect",
        "session_id": "s1",
        "code": 100,
        "reason": "done",
    }


def test_webtransport_contract_stream_events_preserve_session_stream_and_payload() -> None:
    received = webtransport_stream_receive("s1", "st1", b"abc", more=True)
    sent = webtransport_stream_send("s1", "st1", b"xyz", more=False)

    assert received == {
        "type": "webtransport.stream.receive",
        "session_id": "s1",
        "stream_id": "st1",
        "data": b"abc",
        "more": True,
    }
    assert sent == {
        "type": "webtransport.stream.send",
        "session_id": "s1",
        "stream_id": "st1",
        "data": b"xyz",
        "more": False,
    }


def test_webtransport_contract_datagram_events_preserve_datagram_identity() -> None:
    received = webtransport_datagram_receive("s1", "d1", b"abc")
    sent = webtransport_datagram_send("s1", "d2", b"xyz")

    assert received == {"type": "webtransport.datagram.receive", "session_id": "s1", "datagram_id": "d1", "data": b"abc"}
    assert sent == {"type": "webtransport.datagram.send", "session_id": "s1", "datagram_id": "d2", "data": b"xyz"}


def test_webtransport_contract_completion_events_normalize_acknowledged_alias() -> None:
    complete = emit_complete("s1", level="acknowledged")

    assert complete == {
        "type": "transport.emit.complete",
        "unit_id": "s1",
        "level": "flushed_to_transport",
        "status": "ok",
    }


def test_webtransport_event_order_requires_connect_first() -> None:
    events = [webtransport_connect("s1"), webtransport_accept("s1"), webtransport_close("s1")]

    validate_event_order(events, required_first="webtransport.connect", terminal_prefixes=("webtransport.disconnect", "webtransport.close"))


def test_webtransport_event_order_rejects_accept_before_connect() -> None:
    with pytest.raises(ProtocolError):
        validate_event_order(
            [webtransport_accept("s1"), webtransport_connect("s1")],
            required_first="webtransport.connect",
            terminal_prefixes=("webtransport.disconnect", "webtransport.close"),
        )


def test_webtransport_event_order_rejects_events_after_terminal_close() -> None:
    with pytest.raises(ProtocolError):
        validate_event_order(
            [webtransport_connect("s1"), webtransport_close("s1"), webtransport_accept("s1")],
            required_first="webtransport.connect",
            terminal_prefixes=("webtransport.disconnect", "webtransport.close"),
        )


def test_webtransport_identity_extensions_include_session_stream_and_datagram_metadata() -> None:
    endpoint = endpoint_metadata("tcp", address="127.0.0.1", port=8443)
    transport = transport_identity("quic", "conn-1", peer="client", local="server")
    security = security_metadata(tls=True, mtls=True, alpn="h3", sni="example.test", peer_certificate="sha256:peer")
    stream = stream_identity("webtransport-stream", "conn-1", "stream-1", session_id="session-1")
    datagram = datagram_identity("conn-1", "dgram-1", session_id="session-1")

    extensions = asgi3_extensions(endpoint=endpoint, transport=transport, security=security, stream=stream, datagram=datagram)

    assert extensions["tigrcorn.transport"]["kind"] == "quic"
    assert extensions["tigrcorn.security"]["mtls"] is True
    assert extensions["tigrcorn.stream"]["session_id"] == "session-1"
    assert extensions["tigrcorn.datagram"]["datagram_id"] == "dgram-1"


def test_webtransport_cli_protocol_normalizes_udp_quic_http3_carrier() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["tests.fixtures_pkg.appmod:app", "--transport", "udp", "--protocol", "webtransport"])

    config = build_config_from_namespace(namespace)
    listener = config.listeners[0]

    assert listener.kind == "udp"
    assert listener.enabled_protocols == ("quic", "http3", "webtransport")
    assert "3" in listener.http_versions
    assert listener.scheme == "https"


def test_webtransport_config_mapping_normalizes_path_and_origin_list() -> None:
    config = config_from_mapping(
        {
            "listeners": [{"kind": "udp", "protocols": ["webtransport"]}],
            "webtransport": {"origins": [" https://one.test ", "https://two.test"], "path": "wt/"},
        }
    )

    assert config.webtransport.origins == ["https://one.test", "https://two.test"]
    assert config.webtransport.path == "/wt"


def test_webtransport_env_vars_configure_all_tuning_fields() -> None:
    with patch.dict(
        os.environ,
        {
            "WT_TRANSPORT": "udp",
            "WT_PROTOCOL": "webtransport",
            "WT_WEBTRANSPORT_MAX_SESSIONS": "5",
            "WT_WEBTRANSPORT_MAX_STREAMS": "55",
            "WT_WEBTRANSPORT_MAX_DATAGRAM_SIZE": "1001",
            "WT_WEBTRANSPORT_ORIGIN": "https://one.test,https://two.test",
            "WT_WEBTRANSPORT_PATH": "wt",
        },
        clear=False,
    ):
        config = build_config_from_sources(env_prefix="WT")

    assert config.webtransport.max_sessions == 5
    assert config.webtransport.max_streams == 55
    assert config.webtransport.max_datagram_size == 1001
    assert config.webtransport.origins == ["https://one.test", "https://two.test"]
    assert config.webtransport.path == "/wt"


def test_webtransport_public_api_accepts_all_tuning_fields() -> None:
    config = build_config(
        transport="udp",
        protocols=["webtransport"],
        webtransport_max_sessions=7,
        webtransport_max_streams=70,
        webtransport_max_datagram_size=1007,
        webtransport_origins=["https://api.test"],
        webtransport_path="/transport",
    )

    assert config.listeners[0].enabled_protocols == ("quic", "http3", "webtransport")
    assert config.webtransport.max_sessions == 7
    assert config.webtransport.max_streams == 70
    assert config.webtransport.max_datagram_size == 1007
    assert config.webtransport.origins == ["https://api.test"]
    assert config.webtransport.path == "/transport"


def test_webtransport_config_rejects_non_udp_listener() -> None:
    with pytest.raises(ConfigError, match="webtransport requires an udp listener"):
        config_from_mapping({"listeners": [{"kind": "tcp", "protocols": ["webtransport"]}]})


def test_webtransport_config_rejects_non_positive_tuning_values() -> None:
    with pytest.raises(ConfigError, match="webtransport.max_sessions must be positive"):
        config_from_mapping({"listeners": [{"kind": "udp", "protocols": ["webtransport"]}], "webtransport": {"max_sessions": 0}})


def test_webtransport_h3_settings_round_trip_required_extensions() -> None:
    settings = {
        SETTING_ENABLE_CONNECT_PROTOCOL: 1,
        SETTING_H3_DATAGRAM: 1,
        SETTING_ENABLE_WEBTRANSPORT: 1,
    }

    assert decode_settings(encode_settings(settings)) == settings


def test_webtransport_demo_app_accepts_local_session_and_sends_initial_datagram() -> None:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "webtransport.close", "session_id": "s1"}

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    asyncio.run(
        demo_app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )
    )

    assert sent[0] == {"type": "webtransport.accept", "session_id": "s1"}
    assert sent[1]["type"] == "webtransport.datagram.send"


def test_webtransport_demo_app_echoes_stream_payloads() -> None:
    sent: list[dict[str, object]] = []
    events = iter(
        [
            {"type": "webtransport.stream.receive", "session_id": "s1", "stream_id": "st1", "data": b"payload"},
            {"type": "webtransport.close", "session_id": "s1"},
        ]
    )

    async def receive() -> dict[str, object]:
        return next(events)

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    asyncio.run(
        demo_app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )
    )

    assert {"type": "webtransport.stream.send", "session_id": "s1", "stream_id": "st1", "data": b"echo:payload", "more": False} in sent


def test_webtransport_demo_app_echoes_datagram_payloads() -> None:
    sent: list[dict[str, object]] = []
    events = iter(
        [
            {"type": "webtransport.datagram.receive", "session_id": "s1", "datagram_id": "d1", "data": b"payload"},
            {"type": "webtransport.close", "session_id": "s1"},
        ]
    )

    async def receive() -> dict[str, object]:
        return next(events)

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    asyncio.run(
        demo_app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )
    )

    assert {"type": "webtransport.datagram.send", "session_id": "s1", "datagram_id": "d1", "data": b"ack:payload"} in sent


def test_webtransport_demo_app_rejects_non_mtls_when_strict() -> None:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        raise AssertionError("strict mTLS rejection must not await receive")

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    with patch.dict(os.environ, {"TIGRCORN_DEMO_REQUIRE_MTLS": "true"}, clear=False):
        asyncio.run(
            demo_app(
                {
                    "type": "webtransport",
                    "path": "/wt",
                    "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
                },
                receive,
                send,
            )
        )

    assert sent == [{"type": "webtransport.close", "session_id": "s1", "code": 403, "reason": "mTLS required"}]


def test_webtransport_demo_app_accepts_mtls_when_strict() -> None:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "webtransport.close", "session_id": "s1"}

    async def send(event: dict[str, object]) -> None:
        sent.append(event)

    with patch.dict(os.environ, {"TIGRCORN_DEMO_REQUIRE_MTLS": "true"}, clear=False):
        asyncio.run(
            demo_app(
                {
                    "type": "webtransport",
                    "path": "/wt",
                    "extensions": {"tigrcorn.security": {"tls": True, "mtls": True}, "tigrcorn.unit": {"session_id": "s1"}},
                },
                receive,
                send,
            )
        )

    assert sent[0] == {"type": "webtransport.accept", "session_id": "s1"}
