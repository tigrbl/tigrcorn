from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.fixtures_third_party.wt_stream_client import probe_wt_stream
from tigrcorn.config.load import build_config
from tigrcorn.protocols.http3.codec import SETTING_ENABLE_CONNECT_PROTOCOL, SETTING_H3_DATAGRAM, SETTING_WT_ENABLED
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic.handshake import generate_self_signed_certificate


async def _wt_echo_app(scope, receive, send):
    assert scope["type"] == "webtransport"
    connect = await receive()
    assert connect["type"] == "webtransport.connect"
    session_id = connect["session_id"]
    await send({"type": "webtransport.accept", "session_id": session_id})
    while True:
        event = await receive()
        if event["type"] == "webtransport.stream.receive":
            if event.get("stream_direction") == "client_to_server":
                continue
            await send(
                {
                    "type": "webtransport.stream.send",
                    "session_id": session_id,
                    "stream_id": event["stream_id"],
                    "data": b"wt:" + event["data"],
                    "more": False,
                }
            )
        elif event["type"] == "webtransport.datagram.receive":
            await send(
                {
                    "type": "webtransport.datagram.send",
                    "session_id": session_id,
                    "datagram_id": event["datagram_id"],
                    "data": b"dg:" + event["data"],
                }
            )
        elif event["type"] in {"webtransport.close", "webtransport.disconnect"}:
            return


class WebTransportStreamProbeFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_wt_stream_probe_drives_webtransport_stream_roundtrip(self):
        cert_pem, key_pem = generate_self_signed_certificate("server.example")
        with tempfile.TemporaryDirectory() as tmpdir:
            certfile = Path(tmpdir) / "server-cert.pem"
            keyfile = Path(tmpdir) / "server-key.pem"
            certfile.write_bytes(cert_pem)
            keyfile.write_bytes(key_pem)
            config = build_config(
                transport="udp",
                host="127.0.0.1",
                port=0,
                lifespan="off",
                http_versions=["3"],
                protocols=["webtransport"],
                ssl_certfile=str(certfile),
                ssl_keyfile=str(keyfile),
                webtransport_path="/wt",
                webtransport_origins=["https://localhost:8088"],
            )
            server = TigrCornServer(_wt_echo_app, config)
            await server.start()
            port = server._listeners[0].transport.get_extra_info("sockname")[1]
            try:
                response = await probe_wt_stream(
                    "127.0.0.1",
                    port,
                    payload=b"hello",
                    trusted_certificates=[cert_pem],
                )
            finally:
                await server.close()

        self.assertEqual(response.status, 200)
        self.assertTrue(response.received_initial_headers)
        self.assertEqual(response.body, b"wt:hello")
        self.assertTrue(response.ended)
        self.assertEqual(response.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL), 1)
        self.assertEqual(response.remote_settings.get(SETTING_H3_DATAGRAM), 1)
        self.assertEqual(response.remote_settings.get(SETTING_WT_ENABLED), 1)
        self.assertIn("stream", response.quic_events)
        self.assertGreaterEqual(response.datagrams_sent, 3)
        self.assertGreaterEqual(response.datagrams_received, 2)

    async def test_live_webtransport_single_session_multi_lane_roundtrip(self):
        cert_pem, key_pem = generate_self_signed_certificate("server.example")
        with tempfile.TemporaryDirectory() as tmpdir:
            certfile = Path(tmpdir) / "server-cert.pem"
            keyfile = Path(tmpdir) / "server-key.pem"
            certfile.write_bytes(cert_pem)
            keyfile.write_bytes(key_pem)
            config = build_config(
                transport="udp",
                host="127.0.0.1",
                port=0,
                lifespan="off",
                http_versions=["3"],
                protocols=["webtransport"],
                ssl_certfile=str(certfile),
                ssl_keyfile=str(keyfile),
                webtransport_path="/wt",
                webtransport_origins=["https://localhost:8088"],
            )
            server = TigrCornServer(_wt_echo_app, config)
            await server.start()
            port = server._listeners[0].transport.get_extra_info("sockname")[1]
            try:
                response = await probe_wt_stream(
                    "127.0.0.1",
                    port,
                    payload=b"hello",
                    trusted_certificates=[cert_pem],
                    local_cid=b"wtmulti1",
                    child_payloads=(b"one", b"two"),
                    datagram_payload=b"ping",
                    send_unidi=True,
                )
                trace = list(server._datagram_handlers[0].webtransport_trace)
            finally:
                await server.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.stream_bodies[4], b"wt:one")
        self.assertEqual(response.stream_bodies[8], b"wt:two")
        self.assertEqual(response.datagram_body, b"dg:ping")
        session_ids = {row.get("session_id") for row in trace if row.get("session_id")}
        self.assertEqual(len(session_ids), 1)
        self.assertIn("webtransport.connect.response", {row["event"] for row in trace})
        self.assertIn("webtransport.datagram.dispatch", {row["event"] for row in trace})
        self.assertIn("webtransport.datagram.send", {row["event"] for row in trace})
        stream_directions = {row.get("stream_direction") for row in trace if row["event"] == "webtransport.stream.dispatch"}
        self.assertIn("bidi", stream_directions)
        self.assertIn("client_to_server", stream_directions)


if __name__ == "__main__":
    unittest.main()
