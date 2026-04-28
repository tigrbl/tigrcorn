from __future__ import annotations

import json
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).with_name("client")
APP_HOST = "tigrcorn-http11-app"
APP_PORT = 8000


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/raw":
            self._raw_probe(parsed.query)
            return
        super().do_GET()

    def _raw_probe(self, query_string: str) -> None:
        query = parse_qs(query_string)
        target_path = query.get("path", ["/trailers"])[0]
        if not target_path.startswith("/"):
            target_path = "/" + target_path
        request = (
            f"GET {target_path} HTTP/1.1\r\n"
            f"Host: {APP_HOST}:{APP_PORT}\r\n"
            "User-Agent: tigrcorn-http11-demo-raw-client\r\n"
            "TE: trailers\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")
        with socket.create_connection((APP_HOST, APP_PORT), timeout=5) as sock:
            sock.sendall(request)
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
        payload = {
            "request": request.decode("ascii"),
            "response": b"".join(chunks).decode("latin1", "replace"),
        }
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), DemoHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
