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
class H3QuicProbeResult:
    stream_id: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    ended: bool
    quic_events: tuple[str, ...]
    datagrams_sent: int
    datagrams_received: int
    bytes_sent: int
    bytes_received: int

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
            "ended": self.ended,
            "quic": {
                "events": list(self.quic_events),
                "datagrams_sent": self.datagrams_sent,
                "datagrams_received": self.datagrams_received,
                "bytes_sent": self.bytes_sent,
                "bytes_received": self.bytes_received,
            },
        }


def _normalize_headers(headers: Iterable[tuple[bytes | str, bytes | str]]) -> list[tuple[bytes, bytes]]:
    normalized: list[tuple[bytes, bytes]] = []
    for name, value in headers:
        name_bytes = name.encode("ascii") if isinstance(name, str) else name
        value_bytes = value.encode("latin-1") if isinstance(value, str) else value
        normalized.append((name_bytes.lower(), value_bytes))
    return normalized


async def probe_h3_quic(
    host: str,
    port: int,
    *,
    method: bytes | str = b"GET",
    path: bytes | str = b"/",
    headers: Iterable[tuple[bytes | str, bytes | str]] = (),
    body: bytes = b"",
    timeout: float = 5.0,
    quic_secret: bytes = b"shared",
    local_cid: bytes = b"h3q-probe",
) -> H3QuicProbeResult:
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
    datagrams_sent = 0
    datagrams_received = 0
    bytes_sent = 0
    bytes_received = 0
    quic_events: list[str] = []
    try:
        initial = client.build_initial()
        sock.sendto(initial, target)
        datagrams_sent += 1
        bytes_sent += len(initial)

        for _attempt in range(4):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65536), timeout=timeout)
            datagrams_received += 1
            bytes_received += len(data)
            for event in client.receive_datagram(data):
                quic_events.append(event.kind)
                if event.kind == "stream":
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            if "ack" in quic_events and "stream" in quic_events:
                break

        stream_id = 0
        payload = core.get_request(stream_id).encode_request(request_headers, body)
        request_datagram = client.send_stream_data(stream_id, payload, fin=True)
        sock.sendto(request_datagram, target)
        datagrams_sent += 1
        bytes_sent += len(request_datagram)

        response_state = None
        while response_state is None or not response_state.ended:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65536), timeout=timeout)
            datagrams_received += 1
            bytes_received += len(data)
            for event in client.receive_datagram(data):
                quic_events.append(event.kind)
                if event.kind != "stream":
                    continue
                state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if event.stream_id == stream_id and state is not None:
                    response_state = state
            if response_state is not None and response_state.ended:
                break

        if response_state is None:
            raise RuntimeError("h3/quic probe did not receive a response stream")
        return H3QuicProbeResult(
            stream_id=stream_id,
            headers=tuple(response_state.headers),
            body=response_state.body,
            ended=response_state.ended,
            quic_events=tuple(quic_events),
            datagrams_sent=datagrams_sent,
            datagrams_received=datagrams_received,
            bytes_sent=bytes_sent,
            bytes_received=bytes_received,
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
    parser = argparse.ArgumentParser(description="h3/quic probe fixture")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--method", default=os.environ.get("INTEROP_REQUEST_METHOD", "POST"))
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/interop"))
    parser.add_argument("--body", default=os.environ.get("INTEROP_REQUEST_BODY", "hello-h3-quic"))
    args = parser.parse_args(argv)
    if args.version:
        print("h3-quic-client 1.0")
        return 0

    host = os.environ["INTEROP_TARGET_HOST"]
    port = int(os.environ["INTEROP_TARGET_PORT"])
    result = await probe_h3_quic(host, port, method=args.method, path=args.path, body=args.body.encode("utf-8"))
    transcript = {
        "request": {"method": args.method, "path": args.path, "body": args.body},
        "response": result.to_jsonable(),
    }
    negotiation = {
        "implementation": "tigrcorn-h3-quic-probe",
        "protocol": "h3",
        "transport": "quic",
        "scheme": "https",
    }
    _write_json("INTEROP_TRANSCRIPT_PATH", transcript)
    _write_json("INTEROP_NEGOTIATION_PATH", negotiation)
    print(json.dumps(transcript, sort_keys=True))
    return 0 if result.status == 200 and result.ended and "ack" in result.quic_events else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
