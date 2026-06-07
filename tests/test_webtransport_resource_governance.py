from __future__ import annotations

import json

import pytest

from tigrcorn.webtransport.governance import (
    WebTransportBudgetPolicy,
    WebTransportGovernanceError,
    WebTransportGovernanceManager,
    certify_webtransport_resource_governance,
    export_webtransport_governance_config,
)


def _policy() -> WebTransportBudgetPolicy:
    return WebTransportBudgetPolicy(
        max_streams=2,
        max_datagram_size=4,
        max_datagrams_per_session=2,
        max_memory_bytes=8,
        max_bandwidth_bytes=16,
        max_peers=1,
        datagram_abuse_threshold=2,
    )


def _manager() -> WebTransportGovernanceManager:
    manager = WebTransportGovernanceManager(_policy())
    manager.open_session("session-a", peer_id="peer-a", address="203.0.113.10:4433")
    return manager


def test_webtransport_budget_model_shape() -> None:
    config = export_webtransport_governance_config(_policy())

    assert set(config["budget_model"]) == {
        "bandwidth",
        "datagrams",
        "memory",
        "peers",
        "streams",
    }
    assert config["budget_model"]["streams"] == 2
    assert config["budget_model"]["datagrams"] == {
        "max_count_per_session": 2,
        "max_size": 4,
    }


def test_webtransport_governance_config_export() -> None:
    first = export_webtransport_governance_config(_policy())
    second = export_webtransport_governance_config(_policy())

    assert first == second
    assert first["surface"] == "tigrcorn.webtransport.resource-governance"
    assert json.dumps(first, sort_keys=True)


def test_webtransport_max_streams_enforced() -> None:
    manager = _manager()

    manager.open_stream("session-a", "stream-1")
    manager.open_stream("session-a", "stream-2")
    with pytest.raises(WebTransportGovernanceError, match="stream budget"):
        manager.open_stream("session-a", "stream-3")


def test_webtransport_max_datagrams_enforced() -> None:
    manager = _manager()

    assert manager.send_datagram("session-a", "d1", b"one")["accepted"] is True
    assert manager.send_datagram("session-a", "d2", b"two")["accepted"] is True
    rejected = manager.send_datagram("session-a", "d3", b"tre")

    assert rejected["accepted"] is False
    assert rejected["closed"] is False
    assert rejected["reason"] == "datagram count budget exceeded"


def test_webtransport_memory_budget_enforced() -> None:
    manager = _manager()

    manager.allocate_memory("session-a", 8)
    with pytest.raises(WebTransportGovernanceError, match="memory budget"):
        manager.allocate_memory("session-a", 1)

    snapshot = manager.snapshot()
    assert snapshot["sessions"]["session-a"]["closed"] is True
    assert snapshot["sessions"]["session-a"]["memory_bytes"] == 0
    assert "session-a" in snapshot["released_sessions"]


def test_webtransport_peer_budget_enforced() -> None:
    manager = _manager()

    with pytest.raises(WebTransportGovernanceError, match="peer budget"):
        manager.open_session("session-b", peer_id="peer-b")

    manager.open_session("session-c", peer_id="peer-a")
    assert manager.snapshot()["active_sessions"] == ("session-a", "session-c")


def test_webtransport_datagram_abuse_fail_closed() -> None:
    manager = _manager()

    first = manager.send_datagram("session-a", "too-large-1", b"toolong")
    second = manager.send_datagram("session-a", "too-large-2", b"toolong")

    assert first["accepted"] is False
    assert first["closed"] is False
    assert second["accepted"] is False
    assert second["closed"] is True
    assert second["session"]["closed"] is True
    with pytest.raises(WebTransportGovernanceError, match="closed"):
        manager.send_datagram("session-a", "late", b"ok")


def test_webtransport_flow_control_fairness() -> None:
    manager = WebTransportGovernanceManager(_policy())
    manager.open_session("session-a", peer_id="peer-a")
    manager.open_session("session-b", peer_id="peer-a")

    allocations = manager.fair_flow_control(
        {
            "session-a": {"stream-a1": 10, "stream-a2": 10},
            "session-b": {"stream-b1": 10, "stream-b2": 10},
        },
        total_credit=8,
    )

    assert allocations == {
        "session-a": {"stream-a1": 2, "stream-a2": 2},
        "session-b": {"stream-b1": 2, "stream-b2": 2},
    }
    assert all(value > 0 for streams in allocations.values() for value in streams.values())


def test_webtransport_cleanup_after_budget_close() -> None:
    manager = _manager()
    manager.open_stream("session-a", "stream-1")
    manager.allocate_memory("session-a", 4)

    closed = manager.close_session("session-a", reason="budget close")
    snapshot = manager.snapshot()

    assert closed["closed"] is True
    assert closed["streams"] == ()
    assert closed["memory_bytes"] == 0
    assert snapshot["active_sessions"] == ()
    assert snapshot["released_sessions"] == ("session-a",)
    assert snapshot["peers"] == ()


def test_webtransport_migration_keeps_budgets() -> None:
    manager = _manager()
    manager.send_datagram("session-a", "d1", b"one")
    migrated = manager.migrate_session("session-a", new_address="203.0.113.10:53000")
    rejected = manager.send_datagram("session-a", "d2-too-large", b"toolong")

    assert migrated["address"] == "203.0.113.10:53000"
    assert migrated["datagrams"] == 1
    assert rejected["accepted"] is False
    assert rejected["session"]["datagrams"] == 1
    assert rejected["session"]["address"] == "203.0.113.10:53000"


def test_webtransport_certification_fails_without_budget_policy() -> None:
    with pytest.raises(WebTransportGovernanceError, match="explicit resource policy"):
        certify_webtransport_resource_governance(
            {
                "stream_limit": True,
                "datagram_limit": True,
                "memory_limit": True,
                "peer_limit": True,
                "cleanup": True,
            }
        )

    result = certify_webtransport_resource_governance(
        {
            "budget_policy": _policy().as_dict(),
            "stream_limit": True,
            "datagram_limit": True,
            "memory_limit": True,
            "peer_limit": True,
            "cleanup": True,
        }
    )
    assert result["certification_state"] == "certified"
