from __future__ import annotations

import unittest
from importlib import metadata as importlib_metadata

import tigr_asgi_contract as contract
from tigrcorn.contract import (
    asgi3_extensions,
    classify_binding,
    contract_scope,
    datagram_identity,
    datagram_receive,
    datagram_send,
    emit_complete,
    endpoint_metadata,
    require_lossless_metadata,
    runtime_interface_available,
    security_metadata,
    stream_identity,
    stream_receive,
    stream_send,
    transport_identity,
    validate_event_order,
    validate_scope,
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


class ContractClosureAssertions(unittest.TestCase):
    def assert_endpoint_metadata(self, kind: str) -> None:
        kwargs = {
            "tcp": {"address": "127.0.0.1", "port": 8000},
            "uds": {"address": "/tmp/tigrcorn.sock"},
            "fd": {"fd": 3},
            "pipe": {"pipe_name": r"\\.\pipe\tigrcorn"},
            "inproc": {"inproc_name": "worker-1"},
        }[kind]
        metadata = endpoint_metadata(kind, **kwargs)
        payload = metadata.as_dict()
        self.assertEqual(payload["kind"], kind)
        self.assertNotIn("type", payload)

    def assert_connection_identity(self, kind: str) -> None:
        identity = transport_identity(kind, f"{kind}-connection", peer="client", local="server")
        payload = identity.as_dict()
        self.assertEqual(payload["kind"], kind)
        self.assertEqual(payload["connection_id"], f"{kind}-connection")
        self.assertEqual(payload["peer"], "client")

    def assert_stream_identity(self, kind: str) -> None:
        identity = stream_identity(kind, "conn-1", f"{kind}-stream", session_id="session-1")
        payload = identity.as_dict()
        self.assertEqual(payload["kind"], kind)
        self.assertEqual(payload["connection_id"], "conn-1")
        self.assertEqual(payload["stream_id"], f"{kind}-stream")

    def assert_datagram_identity(self) -> None:
        identity = datagram_identity("conn-1", "dgram-7", session_id="session-1")
        payload = identity.as_dict()
        self.assertEqual(payload["kind"], "datagram")
        self.assertEqual(payload["datagram_id"], "dgram-7")
        self.assertEqual(payload["session_id"], "session-1")

    def assert_security_metadata(self, field: str) -> None:
        metadata = security_metadata(
            tls=True,
            mtls=field == "mtls",
            alpn="h3" if field == "alpn" else None,
            sni="example.test" if field == "sni" else None,
            peer_certificate="sha256:peer" if field == "mtls" else None,
            ocsp_status="good" if field == "ocsp" else None,
            crl_status="checked" if field == "ocsp" else None,
        )
        payload = metadata.as_dict()
        if field == "tls":
            self.assertTrue(payload["tls"])
        elif field == "mtls":
            self.assertTrue(payload["mtls"])
            self.assertEqual(payload["peer_certificate"], "sha256:peer")
        elif field == "alpn":
            self.assertEqual(payload["alpn"], "h3")
        elif field == "sni":
            self.assertEqual(payload["sni"], "example.test")
        else:
            self.assertEqual(payload["ocsp_status"], "good")
            self.assertEqual(payload["crl_status"], "checked")

    def assert_asgi3_extension(self, key: str) -> None:
        endpoint = endpoint_metadata("tcp", address="127.0.0.1", port=8000)
        transport = transport_identity("tcp", "conn-1")
        security = security_metadata(tls=True, alpn="h2")
        stream = stream_identity("http2", "conn-1", "1")
        datagram = datagram_identity("conn-1", "d1")
        completion = emit_complete("unit-1")
        extensions = asgi3_extensions(
            endpoint=endpoint,
            transport=transport,
            security=security,
            stream=stream,
            datagram=datagram,
            completion=completion,
        )
        self.assertIn(key, extensions)
        self.assertTrue(key.startswith("tigrcorn."))

    def assert_webtransport_scope(self) -> None:
        scope = contract_scope(
            "webtransport",
            path="/wt",
            extensions={"h3": {"enabled": True}, "quic": {"datagrams": True}},
        )
        self.assertEqual(scope["type"], "webtransport")
        self.assertEqual(scope["extensions"]["h3"]["enabled"], True)

    def assert_webtransport_session_events(self) -> None:
        events = [
            webtransport_connect("s1"),
            webtransport_accept("s1"),
            webtransport_disconnect("s1", code=0),
        ]
        validate_event_order(events, required_first="webtransport.connect", terminal_prefixes=("webtransport.disconnect", "webtransport.close"))
        self.assertEqual(events[1]["type"], "webtransport.accept")

    def assert_webtransport_stream_events(self) -> None:
        received = webtransport_stream_receive("s1", "st1", b"abc", more=True)
        sent = webtransport_stream_send("s1", "st1", b"done")
        self.assertEqual(received["type"], "webtransport.stream.receive")
        self.assertEqual(sent["stream_id"], "st1")

    def assert_webtransport_datagram_events(self) -> None:
        received = webtransport_datagram_receive("s1", "d1", b"a")
        sent = webtransport_datagram_send("s1", "d2", b"b")
        self.assertEqual(received["type"], "webtransport.datagram.receive")
        self.assertEqual(sent["datagram_id"], "d2")

    def assert_webtransport_completion_events(self) -> None:
        close = webtransport_close("s1", code=0)
        complete = emit_complete("s1", level="acknowledged")
        self.assertEqual(close["type"], "webtransport.close")
        self.assertEqual(complete["type"], "transport.emit.complete")
        self.assertEqual(complete["level"], "flushed_to_transport")

    def assert_generic_stream_runtime(self) -> None:
        self.assertEqual(stream_receive("s1", b"hello", more=True)["type"], "transport.stream.receive")
        self.assertEqual(stream_send("s1", b"world")["stream_id"], "s1")

    def assert_generic_datagram_runtime(self) -> None:
        self.assertFalse(datagram_receive("d1", b"hello")["flow_controlled"])
        self.assertTrue(datagram_send("d2", b"world", flow_controlled=True)["flow_controlled"])

    def assert_completion_event(self) -> None:
        complete = emit_complete("unit-1", level="transport", status="ok")
        self.assertEqual(complete, {"type": "transport.emit.complete", "unit_id": "unit-1", "level": "flushed_to_transport", "status": "ok"})

    def assert_binding_classification(self, kind: str) -> None:
        classification = classify_binding(kind)
        self.assertFalse(classification.runtime_owned)
        self.assertTrue(classification.classification_only)
        self.assertEqual(classification.dispatch_runtime, "application")

    def assert_runtime_exclusion(self, name: str) -> None:
        self.assertFalse(runtime_interface_available(name))
        with self.assertRaises(ConfigError):
            classify_binding("rsgi")

    def assert_compat_exclusion(self, name: str) -> None:
        self.assertFalse(runtime_interface_available(name))
        with self.assertRaises(ConfigError):
            classify_binding(name)

    def assert_contract_validation_surface(self) -> None:
        self.assertEqual(importlib_metadata.version("tigr-asgi-contract"), contract.CONTRACT_VERSION)
        self.assertEqual({item.value for item in contract.ScopeType}, {"http", "websocket", "lifespan", "webtransport"})
        self.assertIn("webtransport", {item.value for item in contract.Binding})
        self.assertIn("datagram", {item.value for item in contract.Family})
        self.assertEqual(
            {item.value for item in contract.EmitCompletionLevel},
            {"accepted_by_runtime", "flushed_to_transport"},
        )
        for scope_type in ("http", "websocket", "lifespan", "tigrcorn.stream", "tigrcorn.datagram"):
            validate_scope({"type": scope_type})
        with self.assertRaises(ProtocolError):
            validate_scope({"type": "rest"})

    def assert_unsupported_scope_rejection(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_scope({"type": "wsgi"})

    def assert_lossy_metadata_rejection(self) -> None:
        with self.assertRaises(ProtocolError):
            require_lossless_metadata("connection_id", "")

    def assert_illegal_event_order_rejection(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_event_order(
                [webtransport_accept("s1"), webtransport_connect("s1")],
                required_first="webtransport.connect",
                terminal_prefixes=("webtransport.disconnect", "webtransport.close"),
            )

    def assert_invalid_endpoint_metadata_rejection(self) -> None:
        with self.assertRaises(ProtocolError):
            endpoint_metadata("tcp", address="127.0.0.1")
