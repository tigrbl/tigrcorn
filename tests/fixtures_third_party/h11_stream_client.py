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
class H11StreamProbeResult:
    status: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    data_chunks: tuple[bytes, ...]
    complete: bool

    @property
    def data_event_count(self) -> int:
        return len(self.data_chunks)

    def header_map(self) -> dict[bytes, bytes]:
        return {name.lower(): value for name, value in self.headers}

    def to_jsonable(self) -> dict:
        return {
            "status": self.status,
            "headers": [
                [name.decode("latin-1", errors="replace"), value.decode("latin-1", errors="replace")]
                for name, value in self.headers
            ],
            "body": self.body.decode("utf-8", errors="replace"),
            "data_event_count": self.data_event_count,
            "chunk_sizes": [len(chunk) for chunk in self.data_chunks],
            "complete": self.complete,
        }


def _normalize_headers(headers: Iterable[tuple[bytes | str, bytes | str]]) -> list[tuple[bytes, bytes]]:
    normalized: list[tuple[bytes, bytes]] = []
    for name, value in headers:
        name_bytes = name.encode("ascii") if isinstance(name, str) else name
        value_bytes = value.encode("latin-1") if isinstance(value, str) else value
        normalized.append((name_bytes.lower(), value_bytes))
    return normalized


async def probe_h11_stream(
    host: str,
    port: int,
    *,
    method: bytes | str = b"GET",
    target: bytes | str = b"/stream",
    headers: Iterable[tuple[bytes | str, bytes | str]] = (),
    body: bytes = b"",
    read_size: int = 8,
    timeout: float = 5.0,
) -> H11StreamProbeResult:
    method_bytes = method.encode("ascii") if isinstance(method, str) else method
    target_bytes = target.encode("ascii") if isinstance(target, str) else target
    request_headers = _normalize_headers(headers)
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
        response_headers: tuple[tuple[bytes, bytes], ...] = ()
        chunks: list[bytes] = []
        complete = False
        while not complete:
            event = connection.next_event()
            if event is h11.NEED_DATA:
                data = await asyncio.wait_for(reader.read(read_size), timeout=timeout)
                connection.receive_data(data)
                if not data:
                    break
                continue
            if isinstance(event, h11.Response):
                status = event.status_code
                response_headers = tuple(event.headers)
            elif isinstance(event, h11.Data):
                chunks.append(event.data)
            elif isinstance(event, h11.EndOfMessage):
                complete = True
            elif isinstance(event, h11.ConnectionClosed):
                break

        if status is None:
            raise RuntimeError("h11 stream probe did not receive a response")
        return H11StreamProbeResult(
            status=status,
            headers=response_headers,
            body=b"".join(chunks),
            data_chunks=tuple(chunks),
            complete=complete,
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
    parser = argparse.ArgumentParser(description="h11 stream probe fixture")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/stream"))
    args = parser.parse_args(argv)
    if args.version:
        print("h11-stream-client 1.0")
        return 0
    result = await probe_h11_stream(os.environ["INTEROP_TARGET_HOST"], int(os.environ["INTEROP_TARGET_PORT"]), target=args.path)
    payload = {"response": result.to_jsonable()}
    _write_json("INTEROP_TRANSCRIPT_PATH", payload)
    print(json.dumps(payload, sort_keys=True))
    return 0 if result.status == 200 and result.complete else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
