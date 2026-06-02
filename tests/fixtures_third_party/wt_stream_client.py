from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from dataclasses import dataclass

from tigrcorn.constants import DEFAULT_QUIC_SECRET
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import (
    FRAME_SETTINGS,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_ENABLE_WEBTRANSPORT,
    SETTING_H3_DATAGRAM,
    STREAM_TYPE_CONTROL,
    encode_frame,
    encode_settings,
)
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver
from tigrcorn.utils.bytes import decode_quic_varint, encode_quic_varint


@dataclass(frozen=True)
class WebTransportStreamProbeResult:
    stream_id: int
    status: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    received_initial_headers: bool
    ended: bool
    remote_settings: dict[int, int]
    quic_events: tuple[str, ...]
    datagrams_sent: int
    datagrams_received: int
    stream_bodies: dict[int, bytes]
    datagram_body: bytes

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
            "received_initial_headers": self.received_initial_headers,
            "ended": self.ended,
            "remote_settings": {str(key): value for key, value in self.remote_settings.items()},
            "quic_events": list(self.quic_events),
            "datagrams_sent": self.datagrams_sent,
            "datagrams_received": self.datagrams_received,
            "stream_bodies": {str(key): value.decode("utf-8", errors="replace") for key, value in self.stream_bodies.items()},
            "datagram_body": self.datagram_body.decode("utf-8", errors="replace"),
        }


async def probe_wt_stream(
    host: str,
    port: int,
    *,
    path: bytes = b"/wt",
    origin: bytes = b"https://localhost:8088",
    authority: bytes = b"server.example",
    payload: bytes = b"hello-webtransport",
    trusted_certificates: list[bytes] | None = None,
    timeout: float = 5.0,
    local_cid: bytes = b"wtprobe1",
    child_payloads: tuple[bytes, ...] = (),
    datagram_payload: bytes | None = None,
    send_unidi: bool = False,
    burst_child_streams: bool = False,
    close_connection: bool = True,
) -> WebTransportStreamProbeResult:
    target = (host, port)
    client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=local_cid)
    client.configure_handshake(
        QuicTlsHandshakeDriver(
            is_client=True,
            server_name=authority.decode("ascii"),
            trusted_certificates=trusted_certificates or [],
        )
    )
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    quic_events: list[str] = []
    datagrams_sent = 0
    datagrams_received = 0

    def send(raw: bytes) -> None:
        nonlocal datagrams_sent
        sock.sendto(raw, target)
        datagrams_sent += 1

    async def receive_once():
        nonlocal datagrams_received
        states = []
        stream_events = []
        data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65536), timeout=timeout)
        datagrams_received += 1
        for event in client.receive_datagram(data):
            quic_events.append(event.kind)
            if event.kind in {"stream", "datagram"}:
                stream_events.append(event)
            if event.kind == "stream":
                try:
                    state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                except Exception:
                    state = None
                if state is not None:
                    states.append((event.stream_id, state))
        for datagram in client.take_handshake_datagrams():
            send(datagram)
        return states, stream_events

    try:
        send(client.start_handshake())
        for _attempt in range(12):
            await receive_once()
            if client.handshake_driver is not None and client.handshake_driver.complete:
                break

        if client.handshake_driver is None or not client.handshake_driver.complete:
            raise RuntimeError("webtransport probe did not complete QUIC-TLS handshake")

        control_stream_id = client.streams.next_stream_id(client=True, unidirectional=True)
        settings = encode_settings(
            {
                SETTING_ENABLE_CONNECT_PROTOCOL: 1,
                SETTING_H3_DATAGRAM: 1,
                SETTING_ENABLE_WEBTRANSPORT: 1,
            }
        )
        control_payload = encode_quic_varint(STREAM_TYPE_CONTROL) + encode_frame(FRAME_SETTINGS, settings)
        send(client.send_stream_data(control_stream_id, control_payload, fin=False))
        await asyncio.sleep(0)

        stream_id = 0
        connect_payload = core.get_request(stream_id).encode_request(
            [
                (b":method", b"CONNECT"),
                (b":protocol", b"webtransport"),
                (b":scheme", b"https"),
                (b":path", path),
                (b":authority", authority),
                (b"origin", origin),
                (b"sec-webtransport-http3-draft", b"draft02"),
            ]
        )
        send(client.send_stream_data(stream_id, connect_payload, fin=False))

        response_state = None
        for _attempt in range(12):
            states, _stream_events = await receive_once()
            for candidate_stream_id, candidate in states:
                if candidate_stream_id == stream_id and candidate.received_initial_headers:
                    response_state = candidate
                    break
            if response_state is not None:
                break
        if response_state is None:
            raise RuntimeError("webtransport probe did not receive CONNECT response headers")

        requested_payloads = child_payloads or (payload,)
        expected_child_streams = tuple(4 + (index * 4) for index in range(len(requested_payloads)))
        stream_bodies: dict[int, bytes] = {}
        first_child_stream_id = 4
        first_child_fin = False
        datagram_body = b""

        if burst_child_streams:
            stream_body_parts = {child_stream_id: bytearray() for child_stream_id in expected_child_streams}
            stream_fins = {child_stream_id: False for child_stream_id in expected_child_streams}
            for child_stream_id, child_data in zip(expected_child_streams, requested_payloads):
                child_payload = encode_quic_varint(0x41) + encode_quic_varint(stream_id) + child_data
                send(client.send_stream_data(child_stream_id, child_payload, fin=True))

            if send_unidi:
                unidi_stream_id = client.streams.next_stream_id(client=True, unidirectional=True)
                unidi_payload = encode_quic_varint(0x54) + encode_quic_varint(stream_id) + b"unidi:" + payload
                send(client.send_stream_data(unidi_stream_id, unidi_payload, fin=True))

            if datagram_payload is not None:
                datagram_wire_payload = encode_quic_varint(stream_id // 4) + datagram_payload
                send(client.send_datagram_frame(datagram_wire_payload))

            for _attempt in range(24):
                _states, stream_events = await receive_once()
                for event in stream_events:
                    if event.kind == "stream" and event.stream_id in stream_body_parts:
                        stream_body_parts[event.stream_id].extend(event.data)
                        stream_fins[event.stream_id] = stream_fins[event.stream_id] or event.fin
                    elif event.kind == "datagram" and datagram_payload is not None:
                        try:
                            _session_quarter_id, offset = decode_quic_varint(event.data, 0)
                        except ValueError:
                            continue
                        datagram_body = event.data[offset:]
                streams_complete = all(stream_body_parts[item] or stream_fins[item] for item in expected_child_streams)
                datagram_complete = datagram_payload is None or bool(datagram_body)
                if streams_complete and datagram_complete:
                    break

            stream_bodies = {stream_id_: bytes(body) for stream_id_, body in stream_body_parts.items()}
            first_child_fin = stream_fins.get(first_child_stream_id, False)
        else:
            for child_stream_id, child_data in zip(expected_child_streams, requested_payloads):
                child_payload = encode_quic_varint(0x41) + encode_quic_varint(stream_id) + child_data
                send(client.send_stream_data(child_stream_id, child_payload, fin=True))
                child_body = bytearray()
                child_fin = False
                for _attempt in range(12):
                    _states, stream_events = await receive_once()
                    for event in stream_events:
                        if event.kind == "stream" and event.stream_id == child_stream_id:
                            child_body.extend(event.data)
                            child_fin = child_fin or event.fin
                    if child_body or child_fin:
                        break
                stream_bodies[child_stream_id] = bytes(child_body)
                if child_stream_id == first_child_stream_id:
                    first_child_fin = child_fin

        if send_unidi and not burst_child_streams:
            unidi_stream_id = client.streams.next_stream_id(client=True, unidirectional=True)
            unidi_payload = encode_quic_varint(0x54) + encode_quic_varint(stream_id) + b"unidi:" + payload
            send(client.send_stream_data(unidi_stream_id, unidi_payload, fin=True))
            await asyncio.sleep(0)

        if datagram_payload is not None and not burst_child_streams:
            datagram_wire_payload = encode_quic_varint(stream_id // 4) + datagram_payload
            send(client.send_datagram_frame(datagram_wire_payload))
            for _attempt in range(12):
                _states, stream_events = await receive_once()
                for event in stream_events:
                    if event.kind == "datagram":
                        try:
                            _session_quarter_id, offset = decode_quic_varint(event.data, 0)
                        except ValueError:
                            continue
                        datagram_body = event.data[offset:]
                if datagram_body:
                    break

        if close_connection:
            send(client.close(application=True))
            await asyncio.sleep(0)

        header_map = {name.lower(): value for name, value in response_state.headers}
        return WebTransportStreamProbeResult(
            stream_id=first_child_stream_id,
            status=int(header_map.get(b":status", b"0")),
            headers=tuple(response_state.headers),
            body=stream_bodies.get(first_child_stream_id, b""),
            received_initial_headers=response_state.received_initial_headers,
            ended=first_child_fin,
            remote_settings=dict(core.state.remote_settings),
            quic_events=tuple(quic_events),
            datagrams_sent=datagrams_sent,
            datagrams_received=datagrams_received,
            stream_bodies=stream_bodies,
            datagram_body=datagram_body,
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
    parser = argparse.ArgumentParser(description="WebTransport stream probe fixture")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/wt"))
    parser.add_argument("--origin", default=os.environ.get("INTEROP_ORIGIN", "https://localhost:8088"))
    parser.add_argument("--authority", default=os.environ.get("INTEROP_SERVER_NAME", "server.example"))
    parser.add_argument("--payload", default=os.environ.get("INTEROP_REQUEST_BODY", "hello-webtransport"))
    args = parser.parse_args(argv)
    if args.version:
        print("wt-stream-client 1.0")
        return 0
    result = await probe_wt_stream(
        os.environ["INTEROP_TARGET_HOST"],
        int(os.environ["INTEROP_TARGET_PORT"]),
        path=args.path.encode("ascii"),
        origin=args.origin.encode("ascii"),
        authority=args.authority.encode("ascii"),
        payload=args.payload.encode("utf-8"),
    )
    payload = {"response": result.to_jsonable()}
    _write_json("INTEROP_TRANSCRIPT_PATH", payload)
    print(json.dumps(payload, sort_keys=True))
    return 0 if result.status == 200 and result.body else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
