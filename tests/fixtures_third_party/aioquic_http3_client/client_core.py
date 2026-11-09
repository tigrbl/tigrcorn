from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import time
from typing import Any

from .._aioquic_utils import (
    SETTING_ENABLE_CONNECT_PROTOCOL,
    certificate_input_status,
    connect_quic,
    detect_local_control_stream_id,
    detect_peer_qpack_streams,
    detect_retry_observed,
    encode_goaway_frame,
    env_flag,
    flush_pending_datagrams,
    handle_due_timer,
    header_map,
    header_pairs_to_text,
    make_udp_socket,
    received_settings,
    receive_datagram,
    send_ping_if_supported,
    session_ticket_allows_early_data,
    write_json,
)
from tests.fixtures_pkg._connect_relay_fixture import (
    DeterministicRelayTarget,
    build_tunneled_http_request,
    observed_request_to_json,
    parse_tunneled_http_response,
    parsed_response_to_json,
)
from tests.fixtures_pkg._content_coding_fixture import decode_response_body


def _load_aioquic() -> tuple[Any, Any, Any]:
    try:
        from aioquic.h3.connection import H3Connection  # type: ignore
        from aioquic.quic.configuration import QuicConfiguration  # type: ignore
        from aioquic.quic.connection import QuicConnection  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on external runtime
        raise RuntimeError(
            "aioquic is not installed. Install the optional certification dependencies to run the true third-party HTTP/3 certification adapters."
        ) from exc
    return H3Connection, QuicConfiguration, QuicConnection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aioquic-http3-client")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/interop"))
    parser.add_argument("--body", default=os.environ.get("INTEROP_REQUEST_BODY", "hello-http3"))
    parser.add_argument("--servername", default=os.environ.get("INTEROP_SERVER_NAME", "localhost"))
    parser.add_argument("--cacert", default=os.environ.get("INTEROP_CACERT", "tests/fixtures_certs/interop-localhost-cert.pem"))
    parser.add_argument("--client-cert", default=os.environ.get("INTEROP_CLIENT_CERT"))
    parser.add_argument("--client-key", default=os.environ.get("INTEROP_CLIENT_KEY"))
    parser.add_argument("--connect-relay", action="store_true")
    parser.add_argument("--response-trailers", action="store_true")
    parser.add_argument("--content-coding", action="store_true")
    parser.add_argument("--accept-encoding", default=os.environ.get("INTEROP_ACCEPT_ENCODING", "gzip"))
    return parser


def _build_configuration(ns: argparse.Namespace, *, session_ticket: object | None, new_token: bytes | None) -> Any:
    _H3Connection, QuicConfiguration, _QuicConnection = _load_aioquic()
    configuration = QuicConfiguration(is_client=True, alpn_protocols=["h3"])
    configuration.verify_mode = ssl.CERT_REQUIRED
    configuration.load_verify_locations(str(ns.cacert))
    if ns.client_cert and ns.client_key:
        configuration.load_cert_chain(str(ns.client_cert), str(ns.client_key))
    configuration.server_name = str(ns.servername)
    configuration.max_datagram_frame_size = 65536
    if session_ticket is not None:
        configuration.session_ticket = session_ticket
    if new_token:
        configuration.token = bytes(new_token)
    return configuration


def _initial_state() -> dict[str, Any]:
    return {
        "handshake_complete": False,
        "alpn_protocol": "h3",
        "session_resumed": False,
        "early_data_accepted": False,
        "retry_observed": False,
        "streams": {},
        "received_settings": {},
        "qpack_encoder_stream_seen": False,
        "qpack_decoder_stream_seen": False,
        "client_control_stream_id": None,
        "connect_protocol_enabled": False,
        "termination_error": None,
        "connection_ids_issued": 0,
        "connection_ids_retired": 0,
    }


def _stream_state(state: dict[str, Any], stream_id: int) -> dict[str, Any]:
    streams = state.setdefault("streams", {})
    if stream_id not in streams:
        streams[stream_id] = {
            "response_headers": [],
            "response_trailers": [],
            "response_body": bytearray(),
            "response_complete": False,
            "headers_received": False,
            "data_received": False,
        }
    return streams[stream_id]


def _send_stream_data(quic: Any, stream_id: int, data: bytes, *, end_stream: bool) -> None:
    sender = getattr(quic, "send_stream_data")
    try:
        sender(stream_id, data, end_stream=end_stream)
        return
    except TypeError:
        pass
    try:
        sender(stream_id, data, fin=end_stream)
        return
    except TypeError:
        pass
    sender(stream_id, data, end_stream)


def _rotate_connection_id(quic: Any) -> bool:
    changer = getattr(quic, "change_connection_id", None)
    if not callable(changer):
        return False
    changer()
    return True


def _drain_events(*, quic: Any, http: Any, state: dict[str, Any]) -> None:
    state["retry_observed"] = bool(state.get("retry_observed")) or detect_retry_observed(quic)

    while True:
        event = quic.next_event()
        if event is None:
            break
        event_name = event.__class__.__name__
        if event_name == "HandshakeCompleted":
            state["handshake_complete"] = True
            state["alpn_protocol"] = getattr(event, "alpn_protocol", state.get("alpn_protocol")) or state.get("alpn_protocol")
            state["session_resumed"] = bool(getattr(event, "session_resumed", False)) or bool(state.get("session_resumed"))
            state["early_data_accepted"] = bool(getattr(event, "early_data_accepted", False)) or bool(state.get("early_data_accepted"))
        elif event_name == "ProtocolNegotiated":
            state["alpn_protocol"] = getattr(event, "alpn_protocol", state.get("alpn_protocol")) or state.get("alpn_protocol")
        elif event_name == "ConnectionIdIssued":
            state["connection_ids_issued"] = int(state.get("connection_ids_issued", 0)) + 1
        elif event_name == "ConnectionIdRetired":
            state["connection_ids_retired"] = int(state.get("connection_ids_retired", 0)) + 1
        elif event_name == "ConnectionTerminated":
            state["termination_error"] = {
                "error_code": int(getattr(event, "error_code", 0)),
                "frame_type": getattr(event, "frame_type", None),
                "reason_phrase": str(getattr(event, "reason_phrase", "")),
            }

        for http_event in http.handle_event(event):
            stream_id = getattr(http_event, "stream_id", None)
            http_event_name = http_event.__class__.__name__
            if isinstance(stream_id, int):
                stream = _stream_state(state, stream_id)
                if http_event_name == "HeadersReceived":
                    decoded_headers = header_pairs_to_text(list(getattr(http_event, "headers", [])))
                    if stream.get("headers_received"):
                        stream["response_trailers"] = decoded_headers
                    else:
                        stream["response_headers"] = decoded_headers
                        stream["headers_received"] = True
                    if bool(getattr(http_event, "stream_ended", False)):
                        stream["response_complete"] = True
                elif http_event_name == "DataReceived":
                    stream["response_body"].extend(bytes(getattr(http_event, "data", b"")))
                    stream["data_received"] = True
                    if bool(getattr(http_event, "stream_ended", False)):
                        stream["response_complete"] = True

        settings = received_settings(http)
        if settings:
            state["received_settings"] = settings
            state["connect_protocol_enabled"] = settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1
        control_stream_id = detect_local_control_stream_id(http)
        if control_stream_id is not None:
            state["client_control_stream_id"] = control_stream_id
        encoder_seen, decoder_seen = detect_peer_qpack_streams(http)
        state["qpack_encoder_stream_seen"] = bool(state.get("qpack_encoder_stream_seen")) or encoder_seen
        state["qpack_decoder_stream_seen"] = bool(state.get("qpack_decoder_stream_seen")) or decoder_seen


def _network_step(
    *,
    sock: socket.socket,
    quic: Any,
    http: Any,
    target: tuple[str, int],
    state: dict[str, Any],
    deadline: float,
) -> None:
    flush_pending_datagrams(sock, quic, target)
    _drain_events(quic=quic, http=http, state=state)

    timeout = min(0.25, max(deadline - time.monotonic(), 0.01))
    timer_at = getattr(quic, "get_timer", lambda: None)()
    if timer_at is not None:
        timeout = min(timeout, max(float(timer_at) - time.time(), 0.0))
    sock.settimeout(max(timeout, 0.01))

    try:
        receive_datagram(sock, quic)
    except socket.timeout:
        handle_due_timer(quic)
    _drain_events(quic=quic, http=http, state=state)
    flush_pending_datagrams(sock, quic, target)


def _pump_until(
    *,
    sock: socket.socket,
    quic: Any,
    http: Any,
    target: tuple[str, int],
    state: dict[str, Any],
    deadline: float,
    predicate: Any,
    error_message: str,
) -> None:
    while time.monotonic() < deadline:
        _network_step(sock=sock, quic=quic, http=http, target=target, state=state, deadline=deadline)
        if predicate():
            return
    raise RuntimeError(error_message)


def _send_post_request(
    *,
    http: Any,
    stream_id: int,
    ns: argparse.Namespace,
    body_text: str,
    qpack_hints: bool,
) -> None:
    body_bytes = body_text.encode("utf-8")
    headers = [
        (b":method", b"POST"),
        (b":scheme", b"https"),
        (b":authority", str(ns.servername).encode("utf-8")),
        (b":path", str(ns.path).encode("utf-8")),
        (b"content-length", str(len(body_bytes)).encode("ascii")),
    ]
    if qpack_hints:
        headers.extend(
            [
                (b"x-qpack-signal", body_bytes),
                (b"x-qpack-signal", body_bytes),
                (b"x-qpack-signal-2", body_bytes),
            ]
        )
    http.send_headers(stream_id, headers, end_stream=False)
    http.send_data(stream_id, body_bytes, end_stream=True)


def _exercise_qpack(
    *,
    sock: socket.socket,
    quic: Any,
    http: Any,
    target: tuple[str, int],
    ns: argparse.Namespace,
    state: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "enabled": True,
        "warmup_rounds": [],
        "encoder_stream_seen_before_main_request": False,
    }
    for index in range(2):
        stream_id = quic.get_next_available_stream_id()
        warmup_body = f"{ns.body}-qpack-warmup-{index + 1}"
        _send_post_request(http=http, stream_id=stream_id, ns=ns, body_text=warmup_body, qpack_hints=True)
        flush_pending_datagrams(sock, quic, target)
        _pump_until(
            sock=sock,
            quic=quic,
            http=http,
            target=target,
            state=state,
            deadline=deadline,
            predicate=lambda sid=stream_id: bool(_stream_state(state, sid).get("response_complete")),
            error_message="QPACK warmup response was not received before the deadline",
        )
        stream = _stream_state(state, stream_id)
        response_headers = list(stream.get("response_headers", []))
        response_body = bytes(stream.get("response_body", b""))
        details["warmup_rounds"].append(
            {
                "stream_id": stream_id,
                "status": int(header_map(response_headers).get(":status", "0")),
                "response_body": response_body.decode("utf-8", errors="replace"),
                "qpack_encoder_stream_seen": bool(state.get("qpack_encoder_stream_seen")),
                "qpack_decoder_stream_seen": bool(state.get("qpack_decoder_stream_seen")),
            }
        )
        if state.get("qpack_encoder_stream_seen"):
            break
    details["encoder_stream_seen_before_main_request"] = bool(state.get("qpack_encoder_stream_seen"))
    return details




def _send_request(http: Any, stream_id: int, ns: argparse.Namespace, body_text: str, qpack_hints: bool) -> None:
    if getattr(ns, "response_trailers", False) or getattr(ns, "content_coding", False):
        headers = [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", str(ns.servername).encode("utf-8")),
            (b":path", str(ns.path).encode("utf-8")),
        ]
        if getattr(ns, "content_coding", False):
            headers.append((b"accept-encoding", str(ns.accept_encoding).encode("utf-8")))
        http.send_headers(stream_id, headers, end_stream=True)
        return
    _send_post_request(http=http, stream_id=stream_id, ns=ns, body_text=body_text, qpack_hints=qpack_hints)

def _local_bind_host_for_target(host: str) -> str:
    return "::1" if ":" in host else "127.0.0.1"

__all__ = [name for name in globals() if not name.startswith('__')]
