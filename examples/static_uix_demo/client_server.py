from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).with_name("client")


class ClientHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("cache-control", "no-store")
        super().end_headers()


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), ClientHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
