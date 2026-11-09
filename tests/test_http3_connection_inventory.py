from __future__ import annotations

from tigrcorn_config.defaults import default_config
from tigrcorn_config.model import ListenerConfig
from tigrcorn_observability.logging import AccessLogger, configure_logging
from tigrcorn_protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn_protocols.http3.handler.session import HTTP3Session
from tigrcorn_protocols.sessions import RuntimeConnectionInventory, peer_id_from_address
from tigrcorn_transports.quic.connection import QuicConnection


async def _app(scope, receive, send):
    return None


def _handler(inventory: RuntimeConnectionInventory) -> HTTP3DatagramHandler:
    return HTTP3DatagramHandler(
        app=_app,
        config=default_config(),
        listener=ListenerConfig(
            kind="udp",
            host="127.0.0.1",
            port=4433,
            protocols=["quic", "http3", "webtransport"],
        ),
        access_logger=AccessLogger(configure_logging("warning"), enabled=False),
        connection_inventory=inventory,
    )


def test_http3_handler_registers_updates_and_closes_connection_inventory() -> None:
    inventory = RuntimeConnectionInventory()
    handler = _handler(inventory)
    session = HTTP3Session(
        addr=("203.0.113.10", 4433),
        quic=QuicConnection(is_client=False, secret=b"shared", local_cid=b"localcid", remote_cid=b"remotecid"),
    )

    handler._assign_session_runtime_id(session)
    handler._register_h3_connection(session)
    session.bytes_received = 10
    session.bytes_sent = 5
    handler._update_h3_connection(session)
    handler._close_h3_connection(session, reason="test-close")
    snapshot = inventory.snapshot()

    connection_id = f"conn:h3:{session.runtime_id}"
    assert snapshot["connections"][connection_id]["transport"] == "quic"
    assert snapshot["connections"][connection_id]["state"] == "closed"
    assert snapshot["connections"][connection_id]["counters"]["bytes_received"] == 10
    assert snapshot["peers"][peer_id_from_address("203.0.113.10:4433")]["connection_ids"] == [connection_id]
