from __future__ import annotations


def http_request(body: bytes = b"", more_body: bool = False) -> dict:
    return {"type": "http.request", "body": body, "more_body": more_body}


def http_request_trailers(trailers: list[tuple[bytes, bytes]]) -> dict:
    return {"type": "http.request.trailers", "trailers": trailers}


def http_disconnect() -> dict:
    return {"type": "http.disconnect"}
