from __future__ import annotations

import json

import pytest

from tigrcorn.config import ListenerConfig, ServerConfig
from tigrcorn.transports.quic.security import (
    QuicOperationalSecurityRuntime,
    QuicSecurityCertificationError,
)
from tigrcorn_runtime.server.runner import TigrCornServer


async def _app(scope, receive, send) -> None:
    return None


def _server() -> TigrCornServer:
    config = ServerConfig(
        listeners=[
            ListenerConfig(
                kind="udp",
                host="127.0.0.1",
                port=0,
                protocols=["quic", "http3"],
                quic_secret=b"runtime-retry-secret",
            )
        ]
    )
    return TigrCornServer(_app, config)


def test_quic_retry_token_issuer_used_by_runtime_retry_path() -> None:
    runtime = QuicOperationalSecurityRuntime(secret=b"runtime-retry-secret")
    token = runtime.issue_retry_token(
        address=("203.0.113.10", 4433),
        original_destination_connection_id=b"raw-odcid-secret",
        issued_at_ms=1_000,
    )

    result = runtime.validate_retry_token(
        token,
        address=("203.0.113.10", 4433),
        now_ms=1_050,
        consume=False,
    )
    rendered = json.dumps(runtime.runtime_evidence(), sort_keys=True)

    assert result["accepted"] is True
    assert result["path"] == "runtime_retry"
    assert result["token_hash"]
    assert "raw-odcid-secret" not in rendered
    assert token.decode("utf-8") not in rendered


def test_quic_anti_amplification_blocks_runtime_send_budget() -> None:
    runtime = QuicOperationalSecurityRuntime(secret=b"runtime-anti-amplification")

    with pytest.raises(QuicSecurityCertificationError, match="anti_amplification_limit"):
        runtime.enforce_anti_amplification(
            bytes_received=1200,
            attempted_send_bytes=3601,
            address_validated=False,
        )

    evidence = runtime.runtime_evidence()
    assert evidence["anti_amplification"]["allowed"] is False
    assert evidence["anti_amplification"]["limit_bytes"] == 3600
    assert evidence["anti_amplification"]["reason"] == "anti_amplification_limit"


def test_quic_qlog_redaction_applied_before_evidence_write() -> None:
    runtime = QuicOperationalSecurityRuntime(secret=b"runtime-qlog-secret")

    qlog = runtime.record_qlog_event(
        {
            "connection_id": "cid-secret",
            "event": "packet_sent",
            "packet_number": 7,
            "retry_token": "retry-token-secret",
            "secrets": {"key": "traffic-secret"},
        }
    )
    rendered = json.dumps(qlog, sort_keys=True)

    assert qlog["redacted"] is True
    assert "cid-secret" not in rendered
    assert "retry-token-secret" not in rendered
    assert "traffic-secret" not in rendered
    assert rendered.count("[redacted]") == 3


def test_quic_certification_gate_fails_without_runtime_qlog_artifact() -> None:
    runtime = QuicOperationalSecurityRuntime(secret=b"runtime-certification-secret")
    token = runtime.issue_retry_token(
        address=("203.0.113.10", 4433),
        original_destination_connection_id=b"odcid",
        issued_at_ms=1_000,
    )
    runtime.validate_retry_token(
        token,
        address=("203.0.113.10", 4433),
        now_ms=1_050,
        consume=False,
    )
    runtime.record_loss_recovery()

    with pytest.raises(QuicSecurityCertificationError, match="qlog"):
        runtime.certify()

    runtime.record_qlog_event({"event": "packet_received", "connection_id": "cid-secret"})
    assert runtime.certify()["certification_state"] == "certified"


def test_quic_path_validation_event_feeds_certification_artifact() -> None:
    server = _server()
    listener = server.config.listeners[0]

    evidence = server._record_quic_operational_security_packet(
        listener,
        b"\xc3" + b"packet-body",
        ("203.0.113.10", 53000),
    )
    exported = server.quic_operational_security_evidence()

    assert evidence is not None
    assert evidence["address_validation"]["path_state"] == "unchanged"
    assert evidence["qlog"]["events"][0]["connection_id"] == "[redacted]"
    assert exported["udp://127.0.0.1:0"]["address_validation"]["active_address"] == ["203.0.113.10", 53000]
    assert server.describe()["quic_operational_security"]["udp://127.0.0.1:0"]["qlog"]["redacted"] is True
