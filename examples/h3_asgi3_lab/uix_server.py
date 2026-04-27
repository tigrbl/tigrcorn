from __future__ import annotations

import asyncio
import json
import os
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tigrcorn.constants import DEFAULT_QUIC_SECRET
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver


ROOT = Path(__file__).resolve().parent
CLIENT_ROOT = ROOT / "uix"
CERT_FILE = Path("/certs/server-cert.pem")


async def _issue_h3_get(path: str) -> dict[str, object]:
    target_host = os.environ.get("TIGRCORN_H3_TARGET_HOST", "tigrcorn-h3-asgi3")
    target_port = int(os.environ.get("TIGRCORN_H3_TARGET_PORT", "8445"))
    server_name = os.environ.get("TIGRCORN_H3_SERVER_NAME", "localhost")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"h3uixprobe0001")
    client.configure_handshake(
        QuicTlsHandshakeDriver(
            is_client=True,
            server_name=server_name,
            trusted_certificates=[CERT_FILE.read_bytes()],
        )
    )
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    target = (target_host, target_port)
    try:
        sock.sendto(client.start_handshake(), target)
        for _ in range(16):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == "stream":
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            for datagram in client.take_handshake_datagrams():
                sock.sendto(datagram, target)
            if client.handshake_driver is not None and client.handshake_driver.complete:
                break

        if client.handshake_driver is None or not client.handshake_driver.complete:
            raise RuntimeError("QUIC TLS handshake did not complete")

        request = core.get_request(0).encode_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", f"{server_name}:{target_port}".encode("ascii")),
                (b":path", path.encode("ascii")),
                (b"user-agent", b"tigrcorn-h3-uix"),
            ]
        )
        sock.sendto(client.send_stream_data(0, request, fin=True), target)
        response_state = None
        for _ in range(24):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == "stream" and event.stream_id == 0:
                    response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            if response_state is not None and response_state.ended:
                break

        if response_state is None:
            raise RuntimeError("HTTP/3 response was not received")

        return {
            "ok": True,
            "target": f"https://{server_name}:{target_port}{path}",
            "transport": "h3/quic",
            "headers": [
                [
                    name.decode("latin1", errors="replace"),
                    value.decode("latin1", errors="replace"),
                ]
                for name, value in response_state.headers
            ],
            "body": bytes(response_state.body).decode("utf-8", errors="replace"),
            "ended": bool(response_state.ended),
        }
    finally:
        sock.close()


def _run_h3_probe(path: str) -> dict[str, object]:
    return asyncio.run(_issue_h3_get(path))


class H3LabHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CLIENT_ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/h3-probe":
            requested = parse_qs(parsed.query).get("path", ["/inspect"])[0]
            if not requested.startswith("/"):
                requested = "/" + requested
            try:
                result = _run_h3_probe(requested)
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            body = json.dumps(result, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8090), H3LabHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
