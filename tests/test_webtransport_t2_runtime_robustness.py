from __future__ import annotations

import json
from pathlib import Path

import pytest

from tigrcorn.webtransport.wire import (
    CAPSULE_DATAGRAM,
    CAPSULE_WT_CLOSE_SESSION,
    CAPSULE_WT_DATA_BLOCKED,
    CAPSULE_WT_DRAIN_SESSION,
    CAPSULE_WT_MAX_DATA,
    CAPSULE_WT_STREAM_DATA_BLOCKED,
    Capsule,
    Carrier,
    ConnectRequest,
    StreamDirection,
    WebTransportWireError,
    WebTransportWireRuntime,
    decode_h3_datagram_payload,
    encode_close_session_payload,
    encode_varints,
    h2_webtransport_settings,
    h3_draft13_settings,
)

T2_TEST_ID = "tst:webtransport-t2-runtime-robustness"
T2_EVIDENCE_ID = "evd:webtransport-t2-runtime-robustness-pytest"


def _request(stream_id: int, carrier: Carrier, settings: dict[int, int]) -> ConnectRequest:
    return ConnectRequest(
        stream_id=stream_id,
        headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
        carrier=carrier,
        negotiated_settings=settings,
    )


def _accept_h2(runtime: WebTransportWireRuntime, stream_id: int = 3) -> None:
    assert runtime.accept(_request(stream_id, Carrier.H2, h2_webtransport_settings(1))).accepted is True


def _accept_h3(runtime: WebTransportWireRuntime, stream_id: int = 4) -> None:
    assert runtime.accept(_request(stream_id, Carrier.H3, h3_draft13_settings(1))).accepted is True


def test_webtransport_t2_negative_flow_amounts_do_not_mutate_state() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    _accept_h2(runtime)
    flow = runtime.sessions["3"].flow
    flow.allow_data(3)
    flow.allow_stream_data(1, StreamDirection.BIDI, 2)
    data_sent = flow.data_sent
    stream_data_sent = dict(flow.stream_data_sent)

    with pytest.raises(WebTransportWireError, match="non-negative"):
        flow.allow_data(-1)
    with pytest.raises(WebTransportWireError, match="non-negative"):
        flow.allow_stream_data(1, StreamDirection.BIDI, -1)

    assert flow.data_sent == data_sent
    assert flow.stream_data_sent == stream_data_sent


def test_webtransport_t2_malformed_and_wrong_shape_flow_capsules_fail_closed() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    _accept_h2(runtime)

    with pytest.raises(WebTransportWireError, match="malformed flow-control capsule"):
        runtime.apply_capsule("3", Capsule(CAPSULE_WT_MAX_DATA, b"\xff"))
    with pytest.raises(WebTransportWireError, match="WT_DATA_BLOCKED requires one integer"):
        runtime.apply_capsule("3", Capsule(CAPSULE_WT_DATA_BLOCKED, b""))
    with pytest.raises(WebTransportWireError, match="WT_STREAM_DATA_BLOCKED requires two integers"):
        runtime.apply_capsule("3", Capsule(CAPSULE_WT_STREAM_DATA_BLOCKED, encode_varints(1)))

    event = runtime.apply_capsule("3", Capsule(CAPSULE_WT_STREAM_DATA_BLOCKED, encode_varints(1, 8)))
    assert event == {"event": "webtransport.flow-control", "capsule_type": CAPSULE_WT_STREAM_DATA_BLOCKED}


def test_webtransport_t2_drain_rejects_new_traffic_but_allows_close() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    _accept_h3(runtime)
    assert runtime.apply_capsule("4", Capsule(CAPSULE_WT_DRAIN_SESSION, b"")) == {"event": "webtransport.drain"}

    with pytest.raises(WebTransportWireError, match="draining"):
        runtime.receive_stream_data("4", 8, b"abc", StreamDirection.BIDI)
    with pytest.raises(WebTransportWireError, match="draining"):
        runtime.apply_capsule("4", Capsule(CAPSULE_DATAGRAM, b"abc"))

    event = runtime.apply_capsule("4", Capsule(CAPSULE_WT_CLOSE_SESSION, encode_close_session_payload(0, "done")))
    assert event == {"event": "webtransport.close", "code": 0, "reason": "done"}


def test_webtransport_t2_h3_datagram_payload_underflow_fails_closed() -> None:
    with pytest.raises(WebTransportWireError, match="malformed H3 datagram payload"):
        decode_h3_datagram_payload(b"")


def test_webtransport_t2_buffering_rejects_established_session() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    _accept_h3(runtime)

    with pytest.raises(WebTransportWireError, match="session already established"):
        runtime.buffer_before_session("4", "stream", b"late")


def test_webtransport_t2_keying_material_uses_injected_exporter_and_checks_length() -> None:
    calls: list[tuple[str, bytes, int]] = []

    def exporter(label: str, context: bytes, length: int) -> bytes:
        calls.append((label, context, length))
        return b"k" * length

    runtime = WebTransportWireRuntime(max_sessions=1, keying_material_exporter=exporter)
    _accept_h3(runtime)

    assert runtime.keying_material_exporter("4", "EXPORTER-WebTransport", b"context", 12) == b"k" * 12
    assert calls == [("EXPORTER-WebTransport", b"context", 12)]

    runtime.apply_capsule("4", Capsule(CAPSULE_WT_CLOSE_SESSION, encode_close_session_payload(0, "")))
    with pytest.raises(WebTransportWireError, match="closed"):
        runtime.keying_material_exporter("4", "EXPORTER-WebTransport", b"context", 12)

    bad_runtime = WebTransportWireRuntime(max_sessions=1, keying_material_exporter=lambda _label, _context, _length: b"short")
    _accept_h3(bad_runtime)
    with pytest.raises(WebTransportWireError, match="wrong length"):
        bad_runtime.keying_material_exporter("4", "EXPORTER-WebTransport", b"context", 12)


def test_webtransport_t2_settings_reject_negative_session_count() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        h2_webtransport_settings(-1)
    with pytest.raises(ValueError, match="non-negative"):
        h3_draft13_settings(-1)


def test_webtransport_t2_registry_links_every_draft_feature_to_runtime_robustness() -> None:
    registry = json.loads(Path(".ssot/registry.json").read_text(encoding="utf-8"))
    features = [
        feature
        for feature in registry["features"]
        if feature["id"].startswith("feat:webtransport-h2-") or feature["id"].startswith("feat:webtransport-h3-draft13-")
    ]
    claim_by_id = {claim["id"]: claim for claim in registry["claims"]}
    test_by_id = {test["id"]: test for test in registry["tests"]}
    evidence_by_id = {evidence["id"]: evidence for evidence in registry["evidence"]}
    t2_claim_ids: list[str] = []

    assert len(features) == 23
    for feature in features:
        assert T2_TEST_ID in feature.get("test_ids", [])
        feature_t2_claim_ids = [claim_id for claim_id in feature["claim_ids"] if claim_id.endswith("-planned-t2") or claim_id.endswith(".t2")]
        assert len(feature_t2_claim_ids) == 1
        t2_claim_ids.extend(feature_t2_claim_ids)
        for claim_id in feature_t2_claim_ids:
            claim = claim_by_id[claim_id]
            assert T2_TEST_ID in claim.get("test_ids", [])
            assert T2_EVIDENCE_ID in claim.get("evidence_ids", [])

    robustness_test = test_by_id[T2_TEST_ID]
    robustness_evidence = evidence_by_id[T2_EVIDENCE_ID]
    feature_ids = {feature["id"] for feature in features}
    assert feature_ids.issubset(set(robustness_test["feature_ids"]))
    assert set(t2_claim_ids).issubset(set(robustness_test["claim_ids"]))
    assert robustness_evidence["test_ids"] == [T2_TEST_ID]
