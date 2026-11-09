from __future__ import annotations

import json
import socket
import socketserver
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).with_name("client")
APP_HOST = "tigrcorn-advanced-delivery-app"
APP_PORT = 8000
CONNECT_ECHO_PORT = 9000


def _read_http_response(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        data = sock.recv(8192)
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


def _raw_request(method: str, target_path: str, headers: list[tuple[str, str]] | None = None, body: bytes = b"") -> dict[str, str]:
    if not target_path.startswith("/"):
        target_path = "/" + target_path
    header_lines = [
        f"{method} {target_path} HTTP/1.1",
        f"Host: {APP_HOST}:{APP_PORT}",
        "User-Agent: tigrcorn-advanced-delivery-uix",
        "Connection: close",
    ]
    for name, value in headers or []:
        header_lines.append(f"{name}: {value}")
    if body:
        header_lines.append(f"Content-Length: {len(body)}")
    request = ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii") + body
    with socket.create_connection((APP_HOST, APP_PORT), timeout=5) as sock:
        sock.sendall(request)
        sock.shutdown(socket.SHUT_WR)
        response = _read_http_response(sock)
    return {
        "request": request.decode("latin1"),
        "response": response.decode("latin1", "replace"),
    }


def _connect_probe() -> dict[str, str]:
    request = (
        f"CONNECT tigrcorn-advanced-delivery-uix:{CONNECT_ECHO_PORT} HTTP/1.1\r\n"
        f"Host: tigrcorn-advanced-delivery-uix:{CONNECT_ECHO_PORT}\r\n"
        "User-Agent: tigrcorn-advanced-delivery-uix\r\n"
        "\r\n"
    ).encode("ascii")
    tunnel_payload = b"connect relay payload"
    with socket.create_connection((APP_HOST, APP_PORT), timeout=5) as sock:
        sock.sendall(request)
        head = b""
        while b"\r\n\r\n" not in head:
            head += sock.recv(1)
        sock.sendall(tunnel_payload)
        echoed = sock.recv(len(tunnel_payload))
    return {
        "request": request.decode("latin1") + tunnel_payload.decode("ascii"),
        "response": head.decode("latin1", "replace") + echoed.decode("latin1", "replace"),
    }


class EchoHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        data = self.request.recv(4096)
        self.request.sendall(data[::-1])


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/probe":
            self._probe(parsed.query)
            return
        super().do_GET()

    def _probe(self, query_string: str) -> None:
        query = parse_qs(query_string)
        feature = query.get("feature", ["resource"])[0]
        probes = {
            "connect": _connect_probe,
            "trailers": lambda: _raw_request("GET", "/trailers", [("TE", "trailers")]),
            "coding": lambda: _raw_request("GET", "/resource", [("Accept-Encoding", "gzip")]),
            "conditional": lambda: _raw_request("GET", "/resource", [("If-None-Match", '"does-not-match"')]),
            "conditional-hit": lambda: _raw_request("GET", "/resource", [("If-Modified-Since", "Wed, 01 Jan 2025 00:00:00 GMT")]),
            "range": lambda: _raw_request("GET", "/resource", [("Range", "bytes=0-31")]),
            "range-unsatisfied": lambda: _raw_request("GET", "/resource", [("Range", "bytes=9999-10000")]),
            "early": lambda: _raw_request("GET", "/early-hints"),
            "alt-svc": lambda: _raw_request("GET", "/alt-svc"),
        }
        try:
            payload = probes.get(feature, probes["range"])()
            status = 200
        except Exception as exc:  # pragma: no cover - diagnostic path for the UI
            payload = {"error": repr(exc)}
            status = 502
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    echo_server = socketserver.ThreadingTCPServer(("0.0.0.0", CONNECT_ECHO_PORT), EchoHandler)
    echo_thread = threading.Thread(target=echo_server.serve_forever, daemon=True)
    echo_thread.start()
    server = ThreadingHTTPServer(("0.0.0.0", 8080), DemoHandler)
    try:
        server.serve_forever()
    finally:
        echo_server.shutdown()
        echo_server.server_close()


if __name__ == "__main__":
    main()
