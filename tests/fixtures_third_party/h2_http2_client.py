from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Iterable

import h2.config
import h2.connection
import h2.events


@dataclass(frozen=True)
class H2ProbeResult:
    stream_id: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    trailers: tuple[tuple[bytes, bytes], ...]
    stream_ended: bool

    @property
    def status(self) -> int:
        headers = self.header_map()
        return int(headers.get(b":status", b"0"))

    def header_map(self) -> dict[bytes, bytes]:
        return {name.lower(): value for name, value in self.headers}

    def to_jsonable(self) -> dict:
        return {
            "stream_id": self.stream_id,
            "status": self.status,
            "headers": [
                [name.decode("latin-1", errors="replace"), value.decode("latin-1", errors="replace")]
                for name, value in self.headers
            ],
            "body": self.body.decode("utf-8", errors="replace"),
            "trailers": [
                [name.decode("latin-1", errors="replace"), value.decode("latin-1", errors="replace")]
                for name, value in self.trailers
            ],
            "stream_ended": self.stream_ended,
        }


def _normalize_headers(headers: Iterable[tuple[bytes | str, bytes | str]]) -> list[tuple[bytes, bytes]]:
    normalized: list[tuple[bytes, bytes]] = []
    for name, value in headers:
        name_bytes = name.encode("ascii") if isinstance(name, str) else name
        value_bytes = value.encode("latin-1") if isinstance(value, str) else value
        normalized.append((name_bytes.lower(), value_bytes))
    return normalized


async def probe_h2c(
    host: str,
    port: int,
    *,
    method: bytes | str = b"GET",
    path: bytes | str = b"/",
    headers: Iterable[tuple[bytes | str, bytes | str]] = (),
    body: bytes = b"",
    timeout: float = 5.0,
) -> H2ProbeResult:
    method_bytes = method.encode("ascii") if isinstance(method, str) else method
    path_bytes = path.encode("ascii") if isinstance(path, str) else path
    authority = host.encode("idna")
    request_headers = [
        (b":method", method_bytes),
        (b":scheme", b"http"),
        (b":authority", authority),
        (b":path", path_bytes),
    ]
    request_headers.extend(_normalize_headers(headers))
    if body and not any(name == b"content-length" for name, _value in request_headers):
        request_headers.append((b"content-length", str(len(body)).encode("ascii")))

    config = h2.config.H2Configuration(client_side=True, header_encoding=None, validate_outbound_headers=False)
    connection = h2.connection.H2Connection(config=config)
    stream_id = connection.get_next_available_stream_id()

    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    try:
        connection.initiate_connection()
        connection.send_headers(stream_id, request_headers, end_stream=(len(body) == 0))
        if body:
            connection.send_data(stream_id, body, end_stream=True)
        writer.write(connection.data_to_send())
        await asyncio.wait_for(writer.drain(), timeout=timeout)

        response_headers: list[tuple[bytes, bytes]] = []
        response_trailers: list[tuple[bytes, bytes]] = []
        response_body = bytearray()
        stream_ended = False
        while not stream_ended:
            data = await asyncio.wait_for(reader.read(65536), timeout=timeout)
            if not data:
                break
            events = connection.receive_data(data)
            for event in events:
                if isinstance(event, h2.events.ResponseReceived) and event.stream_id == stream_id:
                    response_headers = list(event.headers)
                elif isinstance(event, h2.events.TrailersReceived) and event.stream_id == stream_id:
                    response_trailers = list(event.headers)
                elif isinstance(event, h2.events.DataReceived) and event.stream_id == stream_id:
                    response_body.extend(event.data)
                    connection.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                elif isinstance(event, h2.events.StreamEnded) and event.stream_id == stream_id:
                    stream_ended = True
            pending = connection.data_to_send()
            if pending:
                writer.write(pending)
                await asyncio.wait_for(writer.drain(), timeout=timeout)

        return H2ProbeResult(
            stream_id=stream_id,
            headers=tuple(response_headers),
            body=bytes(response_body),
            trailers=tuple(response_trailers),
            stream_ended=stream_ended,
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
    parser = argparse.ArgumentParser(description="h2c HTTP/2 probe fixture")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--method", default=os.environ.get("INTEROP_REQUEST_METHOD", "POST"))
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/interop"))
    parser.add_argument("--body", default=os.environ.get("INTEROP_REQUEST_BODY", "hello-h2"))
    args = parser.parse_args(argv)
    if args.version:
        print(f"h2-http2-client {getattr(h2, '__version__', 'unknown')}")
        return 0

    host = os.environ["INTEROP_TARGET_HOST"]
    port = int(os.environ["INTEROP_TARGET_PORT"])
    result = await probe_h2c(host, port, method=args.method, path=args.path, body=args.body.encode("utf-8"))
    transcript = {
        "request": {"method": args.method, "path": args.path, "body": args.body},
        "response": result.to_jsonable(),
    }
    negotiation = {"implementation": "python-h2", "protocol": "h2c", "scheme": "http"}
    _write_json("INTEROP_TRANSCRIPT_PATH", transcript)
    _write_json("INTEROP_NEGOTIATION_PATH", negotiation)
    print(json.dumps(transcript, sort_keys=True))
    return 0 if result.status == 200 and result.stream_ended else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
