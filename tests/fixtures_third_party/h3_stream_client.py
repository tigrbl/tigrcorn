from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from dataclasses import dataclass
from typing import Iterable

from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.transports.quic import QuicConnection


@dataclass(frozen=True)
class H3StreamProbeResult:
    stream_id: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    stream_event_count: int
    ended: bool
    quic_events: tuple[str, ...]

    @property
    def status(self) -> int:
        return int(self.header_map().get(b":status", b"0"))

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
            "stream_event_count": self.stream_event_count,
            "ended": self.ended,
            "quic_events": list(self.quic_events),
        }


def _normalize_headers(headers: Iterable[tuple[bytes | str, bytes | str]]) -> list[tuple[bytes, bytes]]:
    normalized: list[tuple[bytes, bytes]] = []
    for name, value in headers:
        name_bytes = name.encode("ascii") if isinstance(name, str) else name
        value_bytes = value.encode("latin-1") if isinstance(value, str) else value
        normalized.append((name_bytes.lower(), value_bytes))
    return normalized


async def probe_h3_stream(
    host: str,
    port: int,
    *,
    method: bytes | str = b"GET",
    path: bytes | str = b"/stream",
    headers: Iterable[tuple[bytes | str, bytes | str]] = (),
    body: bytes = b"",
    timeout: float = 5.0,
    quic_secret: bytes = b"shared",
    local_cid: bytes = b"h3s-probe",
) -> H3StreamProbeResult:
    method_bytes = method.encode("ascii") if isinstance(method, str) else method
    path_bytes = path.encode("ascii") if isinstance(path, str) else path
    request_headers = [
        (b":method", method_bytes),
        (b":scheme", b"https"),
        (b":authority", host.encode("idna")),
        (b":path", path_bytes),
    ]
    request_headers.extend(_normalize_headers(headers))
    if body and not any(name == b"content-length" for name, _value in request_headers):
        request_headers.append((b"content-length", str(len(body)).encode("ascii")))

    target = (host, port)
    client = QuicConnection(is_client=True, secret=quic_secret, local_cid=local_cid)
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    quic_events: list[str] = []
    stream_event_count = 0
    try:
        sock.sendto(client.build_initial(), target)
        for _attempt in range(4):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65536), timeout=timeout)
            for event in client.receive_datagram(data):
                quic_events.append(event.kind)
                if event.kind == "stream":
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            if "ack" in quic_events and "stream" in quic_events:
                break

        stream_id = 0
        payload = core.get_request(stream_id).encode_request(request_headers, body)
        sock.sendto(client.send_stream_data(stream_id, payload, fin=True), target)

        response_state = None
        while response_state is None or not response_state.ended:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65536), timeout=timeout)
            for event in client.receive_datagram(data):
                quic_events.append(event.kind)
                if event.kind != "stream":
                    continue
                if event.stream_id == stream_id:
                    stream_event_count += 1
                state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if event.stream_id == stream_id and state is not None:
                    response_state = state
            if response_state is not None and response_state.ended:
                break

        if response_state is None:
            raise RuntimeError("h3 stream probe did not receive a response stream")
        return H3StreamProbeResult(
            stream_id=stream_id,
            headers=tuple(response_state.headers),
            body=response_state.body,
            stream_event_count=stream_event_count,
            ended=response_state.ended,
            quic_events=tuple(quic_events),
        )
    finally:
        sock.close()


def _write_json(path_env: str, payload: dict) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)


async def _amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="h3 stream probe fixture")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/stream"))
    args = parser.parse_args(argv)
    if args.version:
        print("h3-stream-client 1.0")
        return 0
    result = await probe_h3_stream(os.environ["INTEROP_TARGET_HOST"], int(os.environ["INTEROP_TARGET_PORT"]), path=args.path)
    payload = {"response": result.to_jsonable()}
    _write_json("INTEROP_TRANSCRIPT_PATH", payload)
    print(json.dumps(payload, sort_keys=True))
    return 0 if result.status == 200 and result.ended else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
