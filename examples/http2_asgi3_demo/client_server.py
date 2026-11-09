from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .h2_client import H2PriorKnowledgeClient, H2Response


ROOT = Path(__file__).parent / "client"
TARGET_HOST = os.environ.get("TIGRCORN_H2_HOST", "tigrcorn-h2-app")
TARGET_PORT = int(os.environ.get("TIGRCORN_H2_PORT", "8000"))


def _response_payload(response: H2Response) -> dict[str, object]:
    body_text = response.body.decode("utf-8", "replace")
    try:
        body_json: object = json.loads(body_text)
    except json.JSONDecodeError:
        body_json = None
    return {
        "stream_id": response.stream_id,
        "status": response.status,
        "headers": response.headers,
        "body_text": body_text,
        "body_json": body_json,
        "elapsed_ms": round(response.elapsed_ms, 2),
    }


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/request":
            params = parse_qs(parsed.query)
            target = params.get("path", ["/"])[0]
            response = H2PriorKnowledgeClient(TARGET_HOST, TARGET_PORT).request("GET", target)
            self._write_json(_response_payload(response))
            return
        if parsed.path == "/api/multiplex":
            params = parse_qs(parsed.query)
            count = max(1, min(int(params.get("count", ["6"])[0]), 16))
            path = params.get("path", ["/scope"])[0]
            self._write_json({"requests": self._run_many(count, path)})
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/request":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        target = payload.get("path", "/echo")
        body = payload.get("body", "")
        response = H2PriorKnowledgeClient(TARGET_HOST, TARGET_PORT).request(
            "POST",
            str(target),
            str(body).encode("utf-8"),
            headers=[(b"content-type", b"text/plain; charset=utf-8")],
        )
        self._write_json(_response_payload(response))

    def _run_many(self, count: int, path: str) -> list[dict[str, object]]:
        paths = [f"{path}?item={index}" for index in range(1, count + 1)]
        responses = H2PriorKnowledgeClient(TARGET_HOST, TARGET_PORT).multiplex_get(paths)
        results = []
        for index, response in enumerate(responses, start=1):
            payload = _response_payload(response)
            payload["label"] = f"request-{index}"
            results.append(payload)
        return results

    def _write_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    bind = ("0.0.0.0", int(os.environ.get("TIGRCORN_H2_UI_PORT", "8080")))
    server = ThreadingHTTPServer(bind, DemoHandler)
    print(f"HTTP/2 demo UI listening on http://{bind[0]}:{bind[1]}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
