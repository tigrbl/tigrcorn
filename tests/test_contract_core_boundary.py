from __future__ import annotations

import unittest

from tigrcorn.contract import (
    asgi3_extensions,
    contract_scope,
    emit_complete,
    family_capability,
    http_request,
    http_response_body,
    http_response_start,
    lifespan_shutdown,
    lifespan_shutdown_complete,
    lifespan_startup,
    lifespan_startup_complete,
    map_contract_event,
    security_metadata,
    transport_identity,
    unit_identity,
    validate_binding_legality,
    validate_scope,
    webtransport_datagram_receive,
    webtransport_stream_send,
    websocket_accept,
    websocket_connect,
    websocket_receive,
    websocket_send,
)
from tigrcorn.errors import ConfigError, ProtocolError


class ContractCoreBoundaryTests(unittest.TestCase):
    def test_contract_scope_validation_covers_boundary_scope_families(self) -> None:
        http = contract_scope("http", method="GET", path="/items")
        websocket = contract_scope("websocket", path="/ws", subprotocols=[])
        lifespan = contract_scope("lifespan", state={})
        webtransport = contract_scope(
            "webtransport",
            path="/wt",
            extensions={"h3": {"enabled": True}, "quic": {"datagrams": True}},
        )

        self.assertEqual(http["type"], "http")
        self.assertEqual(websocket["type"], "websocket")
        self.assertEqual(lifespan["type"], "lifespan")
        self.assertEqual(webtransport["type"], "webtransport")

    def test_contract_scope_validation_rejects_lossy_scope_shapes(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_scope({"type": "http", "method": 1})
        with self.assertRaises(ProtocolError):
            validate_scope({"type": "websocket", "subprotocols": "chat"})
        with self.assertRaises(ProtocolError):
            validate_scope({"type": "lifespan", "state": []})
        with self.assertRaises(ProtocolError):
            validate_scope({"type": "webtransport", "extensions": {"h3": {}}})

    def test_http_event_map_and_unit_identity_are_deterministic(self) -> None:
        start = http_response_start("req-1", status=204)
        body = http_response_body("req-1", body=b"")

        self.assertEqual(http_request("req-1")["type"], "http.request")
        self.assertEqual(start["unit_id"], "req-1")
        self.assertEqual(body["type"], "http.response.body")
        self.assertEqual(map_contract_event("http", "request.body_in"), "http.request")
        self.assertEqual(map_contract_event("http", "response.emit_complete"), "transport.emit.complete")

    def test_websocket_event_map_is_deterministic(self) -> None:
        self.assertEqual(websocket_connect("ws-1")["type"], "websocket.connect")
        self.assertEqual(websocket_accept("ws-1", subprotocol="chat")["subprotocol"], "chat")
        self.assertEqual(websocket_receive("ws-1", text="hi")["text"], "hi")
        self.assertEqual(websocket_send("ws-1", bytes_=b"ok")["bytes"], b"ok")
        self.assertEqual(map_contract_event("websocket", "message.out"), "websocket.send")

    def test_lifespan_event_map_is_deterministic(self) -> None:
        self.assertEqual(lifespan_startup("life-1")["type"], "lifespan.startup")
        self.assertEqual(lifespan_startup_complete("life-1")["type"], "lifespan.startup.complete")
        self.assertEqual(lifespan_shutdown("life-1")["type"], "lifespan.shutdown")
        self.assertEqual(lifespan_shutdown_complete("life-1")["type"], "lifespan.shutdown.complete")
        self.assertEqual(map_contract_event("lifespan", "session.ready"), "lifespan.startup.complete")

    def test_webtransport_event_map_covers_stream_datagram_and_completion(self) -> None:
        self.assertEqual(webtransport_stream_send("sess-1", "st-1", b"x")["type"], "webtransport.stream.send")
        self.assertEqual(webtransport_datagram_receive("sess-1", "dg-1", b"x")["type"], "webtransport.datagram.receive")
        self.assertEqual(map_contract_event("webtransport", "stream.chunk_out"), "webtransport.stream.send")
        self.assertEqual(map_contract_event("webtransport", "datagram.in"), "webtransport.datagram.receive")
        self.assertEqual(map_contract_event("webtransport", "session.emit_complete"), "transport.emit.complete")

    def test_unit_identity_propagates_to_asgi3_extensions(self) -> None:
        unit = unit_identity(
            "unit-1",
            family="stream",
            binding="webtransport",
            connection_id="conn-1",
            session_id="sess-1",
            stream_id="stream-1",
        )
        extensions = asgi3_extensions(
            transport=transport_identity("quic", "conn-1"),
            security=security_metadata(tls=True, alpn="h3"),
            completion=emit_complete("unit-1"),
            unit=unit,
        )

        self.assertEqual(extensions["tigrcorn.unit"]["unit_id"], "unit-1")
        self.assertEqual(extensions["tigrcorn.transport"]["connection_id"], "conn-1")
        self.assertEqual(extensions["tigrcorn.security"]["alpn"], "h3")

    def test_transport_and_tls_metadata_are_lossless(self) -> None:
        security = security_metadata(tls=True, mtls=True, alpn="h2", sni="example.test", peer_certificate="sha256:peer")

        self.assertEqual(security.as_dict()["mtls"], True)
        self.assertEqual(security.as_dict()["peer_certificate"], "sha256:peer")
        with self.assertRaises(ProtocolError):
            security_metadata(mtls=True)

    def test_family_capabilities_declare_supported_families(self) -> None:
        self.assertIn("http", family_capability("request").bindings)
        self.assertIn("websocket", family_capability("session").bindings)
        self.assertIn("message.out", family_capability("message").subevents)
        self.assertIn("stream.chunk_out", family_capability("stream").subevents)
        self.assertIn("datagram.out", family_capability("datagram").subevents)

    def test_binding_legality_validation_accepts_supported_combinations(self) -> None:
        validate_binding_legality(binding="http", family="request", subevent="request.body_in", exchange="unary")
        validate_binding_legality(binding="websocket", family="message", subevent="message.out", exchange="duplex")
        validate_binding_legality(binding="webtransport", family="datagram", subevent="datagram.out", exchange="duplex")

    def test_contract_error_semantics_are_deterministic(self) -> None:
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="rest", family="datagram")
        with self.assertRaises(ProtocolError):
            map_contract_event("http", "datagram.out")
        with self.assertRaises(ProtocolError):
            http_response_start("req-1", status=99)
        with self.assertRaises(ProtocolError):
            unit_identity("", family="request", binding="http")


if __name__ == "__main__":
    unittest.main()
