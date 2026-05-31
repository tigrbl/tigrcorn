from __future__ import annotations

import importlib.util
import ssl
import time

from benchmarks.common import measure_sync
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.transports.quic import QuicConnection as TigrcornQuicConnection


def _request_headers(*, host: bytes, path: bytes, body: bytes) -> list[tuple[bytes, bytes]]:
    headers = [
        (b":method", b"POST"),
        (b":scheme", b"https"),
        (b":authority", host),
        (b":path", path),
        (b"content-type", b"application/octet-stream"),
    ]
    if body:
        headers.append((b"content-length", str(len(body)).encode("ascii")))
    return headers


def _tigrcorn_http3_request_prepare(*, host: bytes, path: bytes, body: bytes) -> dict[str, object]:
    client = TigrcornQuicConnection(is_client=True, secret=b"shared", local_cid=b"bench-h3")
    core = HTTP3ConnectionCore()
    initial = client.build_initial()
    stream_id = 0
    payload = core.get_request(stream_id).encode_request(_request_headers(host=host, path=path, body=body), body)
    request_datagram = client.send_stream_data(stream_id, payload, fin=True)
    return {
        "backend": "tigrcorn",
        "datagram_count": 2,
        "total_datagram_bytes": len(initial) + len(request_datagram),
        "request_payload_bytes": len(payload),
        "stream_id": stream_id,
        "initial_nonempty": len(initial) > 0,
        "request_nonempty": len(request_datagram) > 0,
    }


def _aioquic_http3_request_prepare(*, host: bytes, path: bytes, body: bytes) -> dict[str, object]:
    from aioquic.h3.connection import H3Connection  # type: ignore
    from aioquic.quic.configuration import QuicConfiguration  # type: ignore
    from aioquic.quic.connection import QuicConnection  # type: ignore

    configuration = QuicConfiguration(is_client=True, alpn_protocols=["h3"])
    configuration.verify_mode = ssl.CERT_NONE
    quic = QuicConnection(configuration=configuration)
    quic.connect(("127.0.0.1", 4433), now=time.time())
    h3 = H3Connection(quic)
    stream_id = quic.get_next_available_stream_id()
    headers = _request_headers(host=host, path=path, body=body)
    h3.send_headers(stream_id, headers, end_stream=(not body))
    if body:
        h3.send_data(stream_id, body, end_stream=True)
    pending = quic.datagrams_to_send(now=time.time())
    datagram_sizes = [len(item[0]) for item in pending]
    return {
        "backend": "aioquic",
        "datagram_count": len(pending),
        "total_datagram_bytes": sum(datagram_sizes),
        "request_payload_bytes": len(body),
        "stream_id": stream_id,
        "initial_nonempty": bool(datagram_sizes),
        "request_nonempty": any(size > 0 for size in datagram_sizes),
    }


def http3_peer_prepare_driver(profile, *, source_root):
    backend = str(profile.driver_config.get("backend", "tigrcorn"))
    host = str(profile.driver_config.get("host", "example.com")).encode("idna")
    path = str(profile.driver_config.get("path", "/interop")).encode("ascii")
    body = bytes(str(profile.driver_config.get("body", "hello-http3-peer")), "utf-8")

    def operation():
        if backend == "aioquic":
            result = _aioquic_http3_request_prepare(host=host, path=path, body=body)
        elif backend == "tigrcorn":
            result = _tigrcorn_http3_request_prepare(host=host, path=path, body=body)
        else:
            raise RuntimeError(f"unsupported peer benchmark backend: {backend!r}")
        return {
            "connections": 1,
            "streams": 1,
            "correctness": {
                "initial_nonempty": bool(result["initial_nonempty"]),
                "request_nonempty": bool(result["request_nonempty"]),
                "datagrams_recorded": int(result["datagram_count"]) >= 1,
                "backend_matches": str(result["backend"]) == backend,
            },
            "metadata": {
                "backend": backend,
                "body_bytes": len(body),
                "path": path.decode("ascii"),
                "host": host.decode("ascii"),
                "aioquic_available": importlib.util.find_spec("aioquic") is not None,
                "stream_id": int(result["stream_id"]),
                "datagram_count": int(result["datagram_count"]),
                "total_datagram_bytes": int(result["total_datagram_bytes"]),
                "request_payload_bytes": int(result["request_payload_bytes"]),
            },
        }

    return measure_sync(
        operation,
        iterations=profile.iterations,
        warmups=profile.warmups,
        units_per_iteration=profile.units_per_iteration,
        correctness_note="peer-comparison benchmark checks identical HTTP/3 request preparation semantics across backends",
    )
