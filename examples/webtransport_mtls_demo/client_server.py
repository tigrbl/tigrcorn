from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLIENT_ROOT = ROOT / "client"
CERT_HASH = Path("/certs/cert-hash.json")


class DemoClientHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CLIENT_ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/cert-hash.json":
            if not CERT_HASH.exists():
                self.send_error(503, "certificate hash is not ready")
                return
            body = CERT_HASH.read_bytes()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), DemoClientHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
