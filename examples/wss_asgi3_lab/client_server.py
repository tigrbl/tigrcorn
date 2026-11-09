from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLIENT_ROOT = ROOT / "client"
DEFAULT_WSS_URL = "wss://localhost:8443/ws"


class ClientHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CLIENT_ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/config.js":
            wss_url = os.environ.get("TIGRCORN_WSS_URL", DEFAULT_WSS_URL)
            body = f'window.TIGRCORN_WSS_URL = "{wss_url}";\n'.encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/javascript")
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), ClientHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
