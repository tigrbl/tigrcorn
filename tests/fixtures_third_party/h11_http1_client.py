from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Iterable

import h11


@dataclass(frozen=True)
class H11ProbeResult:
    status: int
    reason: bytes
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    informational: tuple[tuple[int, tuple[tuple[bytes, bytes], ...]], ...]

    def header_map(self) -> dict[bytes, bytes]:
        return {name.lower(): value for name, value in self.headers}

    def to_jsonable(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason.decode("latin-1", errors="replace"),
            "headers": [
                [name.decode("latin-1", errors="replace"), value.decode("latin-1", errors="replace")]
                for name, value in self.headers
            ],
            "body": self.body.decode("utf-8", errors="replace"),
            "informational": [
                {
                    "status": status,
                    "headers": [
                        [name.decode("latin-1", errors="replace"), value.decode("latin-1", errors="replace")]
                        for name, value in headers
                    ],
                }
                for status, headers in self.informational
            ],
        }


def _normalize_header_pairs(headers: Iterable[tuple[bytes | str, bytes | str]]) -> list[tuple[bytes, bytes]]:
    normalized: list[tuple[bytes, bytes]] = []
    for name, value in headers:
        name_bytes = name.encode("ascii") if isinstance(name, str) else name
        value_bytes = value.encode("latin-1") if isinstance(value, str) else value
        normalized.append((name_bytes.lower(), value_bytes))
    return normalized


async def probe_http11(
    host: str,
    port: int,
    *,
    method: bytes | str = b"GET",
    target: bytes | str = b"/",
    headers: Iterable[tuple[bytes | str, bytes | str]] = (),
    body: bytes = b"",
    timeout: float = 5.0,
) -> H11ProbeResult:
    method_bytes = method.encode("ascii") if isinstance(method, str) else method
    target_bytes = target.encode("ascii") if isinstance(target, str) else target
    request_headers = _normalize_header_pairs(headers)
    if not any(name == b"host" for name, _value in request_headers):
        request_headers.append((b"host", host.encode("idna")))
    if body and not any(name == b"content-length" for name, _value in request_headers):
        request_headers.append((b"content-length", str(len(body)).encode("ascii")))
    if not any(name == b"connection" for name, _value in request_headers):
        request_headers.append((b"connection", b"close"))

    connection = h11.Connection(our_role=h11.CLIENT)
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    try:
        writer.write(connection.send(h11.Request(method=method_bytes, target=target_bytes, headers=request_headers)))
        if body:
            writer.write(connection.send(h11.Data(data=body)))
        writer.write(connection.send(h11.EndOfMessage()))
        await asyncio.wait_for(writer.drain(), timeout=timeout)

        status: int | None = None
        reason = b""
        response_headers: tuple[tuple[bytes, bytes], ...] = ()
        informational: list[tuple[int, tuple[tuple[bytes, bytes], ...]]] = []
        chunks = bytearray()

        while True:
            event = connection.next_event()
            if event is h11.NEED_DATA:
                data = await asyncio.wait_for(reader.read(65536), timeout=timeout)
                connection.receive_data(data)
                if not data and connection.their_state is h11.CLOSED:
                    break
                continue
            if isinstance(event, h11.InformationalResponse):
                informational.append((event.status_code, tuple(event.headers)))
            elif isinstance(event, h11.Response):
                status = event.status_code
                reason = event.reason
                response_headers = tuple(event.headers)
            elif isinstance(event, h11.Data):
                chunks.extend(event.data)
            elif isinstance(event, h11.EndOfMessage):
                break
            elif isinstance(event, h11.ConnectionClosed):
                break

        if status is None:
            raise RuntimeError("h11 probe did not receive a final response")
        return H11ProbeResult(
            status=status,
            reason=reason,
            headers=response_headers,
            body=bytes(chunks),
            informational=tuple(informational),
        )
    finally:
        writer.close()
        await writer.wait_closed()


def _write_json(path_env: str, payload: dict) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)


async def _amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="h11 HTTP/1.1 probe fixture")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--method", default=os.environ.get("INTEROP_REQUEST_METHOD", "POST"))
    parser.add_argument("--target", default=os.environ.get("INTEROP_REQUEST_TARGET", "/interop"))
    parser.add_argument("--body", default=os.environ.get("INTEROP_REQUEST_BODY", "hello-interop"))
    args = parser.parse_args(argv)
    if args.version:
        print("h11-http1-client 1.0")
        return 0

    host = os.environ["INTEROP_TARGET_HOST"]
    port = int(os.environ["INTEROP_TARGET_PORT"])
    result = await probe_http11(host, port, method=args.method, target=args.target, body=args.body.encode("utf-8"))
    transcript = {
        "request": {"method": args.method, "path": args.target, "body": args.body},
        "response": result.to_jsonable(),
    }
    negotiation = {"alpn": "http/1.1", "client": "h11"}
    _write_json("INTEROP_TRANSCRIPT_PATH", transcript)
    _write_json("INTEROP_NEGOTIATION_PATH", negotiation)
    print(json.dumps(transcript, sort_keys=True))
    return 0 if result.status == 200 else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
