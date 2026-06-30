from __future__ import annotations

import json

from tigrcorn.sessions.inventory import RuntimeConnectionInventory, peer_id_from_address


def test_connection_inventory_open_update_close_snapshot() -> None:
    inventory = RuntimeConnectionInventory()
    peer_id = peer_id_from_address("127.0.0.1:12345")

    inventory.open_connection(
        "conn:listener:0:1",
        transport="tcp",
        protocols=("http1",),
        listener_id="listener:0",
        peer_id=peer_id,
        remote_address="127.0.0.1:12345",
        local_address="127.0.0.1:8000",
        security={"tls": False},
    )
    inventory.open_session(
        "conn:listener:0:1:http1:0",
        connection_id="conn:listener:0:1",
        kind="http-request",
        metadata={"path": "/"},
    )
    inventory.increment_connection_counter("conn:listener:0:1", "requests")
    inventory.increment_session_counter("conn:listener:0:1:http1:0", "responses")
    inventory.close_session("conn:listener:0:1:http1:0", reason="done")
    inventory.close_connection("conn:listener:0:1", reason="done")
    inventory.close_connection("conn:listener:0:1", reason="again")

    snapshot = inventory.snapshot()

    assert snapshot["schema_version"] == "1.0"
    assert snapshot["counts"]["connections"] == 1
    assert snapshot["counts"]["active_connections"] == 0
    assert snapshot["peers"][peer_id]["connection_ids"] == ["conn:listener:0:1"]
    assert snapshot["connections"]["conn:listener:0:1"]["counters"]["requests"] == 1
    assert snapshot["sessions"]["conn:listener:0:1:http1:0"]["close_reason"] == "done"
    assert json.loads(json.dumps(snapshot, sort_keys=True)) == snapshot


def test_connection_inventory_groups_peer_connections() -> None:
    inventory = RuntimeConnectionInventory()
    peer_id = peer_id_from_address("203.0.113.10:4433")

    for index in range(2):
        inventory.open_connection(
            f"conn:listener:0:{index}",
            transport="quic",
            protocols=("http3", "webtransport"),
            listener_id="listener:0",
            peer_id=peer_id,
            remote_address="203.0.113.10:4433",
        )

    snapshot = inventory.snapshot()

    assert snapshot["counts"]["active_peers"] == 1
    assert snapshot["peers"][peer_id]["connection_ids"] == ["conn:listener:0:0", "conn:listener:0:1"]
