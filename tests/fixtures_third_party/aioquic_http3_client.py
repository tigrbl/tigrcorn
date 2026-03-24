from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import time
from typing import Any

from ._aioquic_utils import (
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


def _perform_single_exchange(
    *,
    target: tuple[str, int],
    ns: argparse.Namespace,
    session_ticket: object | None = None,
    new_token: bytes | None = None,
    zero_rtt: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], object | None, bytes | None]:
    H3Connection, _QuicConfiguration, QuicConnection = _load_aioquic()
    configuration = _build_configuration(ns, session_ticket=session_ticket, new_token=new_token)

    captured_ticket: dict[str, object] = {}
    captured_token: dict[str, bytes] = {}

    quic = QuicConnection(
        configuration=configuration,
        session_ticket_handler=lambda ticket: captured_ticket.setdefault("value", ticket),
        token_handler=lambda token: captured_token.setdefault("value", bytes(token)),
    )
    http = H3Connection(quic)
    sock = make_udp_socket(_local_bind_host_for_target(target[0]))
    local_before = list(sock.getsockname()[:2])
    state = _initial_state()
    deadline = time.monotonic() + 20.0
    qpack_enabled = env_flag("INTEROP_ENABLE_QPACK_BLOCKING")
    qpack_details: dict[str, Any] = {"enabled": False, "warmup_rounds": [], "encoder_stream_seen_before_main_request": False}

    connect_quic(quic, target)
    flush_pending_datagrams(sock, quic, target)

    if not zero_rtt:
        _pump_until(
            sock=sock,
            quic=quic,
            http=http,
            target=target,
            state=state,
            deadline=deadline,
            predicate=lambda: bool(state.get("handshake_complete")),
            error_message="QUIC handshake did not complete before the HTTP/3 request was sent",
        )
        if qpack_enabled:
            qpack_details = _exercise_qpack(
                sock=sock,
                quic=quic,
                http=http,
                target=target,
                ns=ns,
                state=state,
                deadline=deadline,
            )

    main_stream_id = quic.get_next_available_stream_id()
    request_sent_before_handshake = not bool(state.get("handshake_complete"))
    _send_request(http=http, stream_id=main_stream_id, ns=ns, body_text=str(ns.body), qpack_hints=qpack_enabled)
    flush_pending_datagrams(sock, quic, target)

    migration = {
        "used": False,
        "from": local_before,
        "strategy": None,
        "connection_id_rotated": False,
        "ping_requested": False,
    }
    if env_flag("INTEROP_ENABLE_MIGRATION"):
        migrated = make_udp_socket(_local_bind_host_for_target(target[0]))
        migration["connection_id_rotated"] = _rotate_connection_id(quic)
        migration["ping_requested"] = send_ping_if_supported(quic)
        sock.close()
        sock = migrated
        flush_pending_datagrams(sock, quic, target)
        migration.update(
            {
                "used": True,
                "to": list(sock.getsockname()[:2]),
                "strategy": "udp-rebind-and-cid-rotation",
            }
        )

    _pump_until(
        sock=sock,
        quic=quic,
        http=http,
        target=target,
        state=state,
        deadline=deadline,
        predicate=lambda: bool(_stream_state(state, main_stream_id).get("response_complete"))
        and (not zero_rtt or bool(state.get("handshake_complete"))),
        error_message="HTTP/3 response was not received before the deadline",
    )

    goaway_sent = False
    if env_flag("INTEROP_ENABLE_GOAWAY"):
        control_stream_id = state.get("client_control_stream_id")
        if not isinstance(control_stream_id, int):
            control_stream_id = detect_local_control_stream_id(http) or 2
        _send_stream_data(quic, control_stream_id, encode_goaway_frame(0), end_stream=False)
        flush_pending_datagrams(sock, quic, target)
        goaway_sent = True

    ticket_deadline = time.monotonic() + 3.0
    while time.monotonic() < ticket_deadline and "value" not in captured_ticket:
        _network_step(sock=sock, quic=quic, http=http, target=target, state=state, deadline=ticket_deadline)
        if state.get("termination_error"):
            break

    main_stream = _stream_state(state, main_stream_id)
    response_headers = list(main_stream.get("response_headers", []))
    response_trailers = list(main_stream.get("response_trailers", []))
    response_body = bytes(main_stream.get("response_body", b""))
    response_status = int(header_map(response_headers).get(":status", "0"))

    early_data_requested = bool(zero_rtt and session_ticket is not None and request_sent_before_handshake)
    if zero_rtt and session_ticket is not None and not session_ticket_allows_early_data(session_ticket):
        early_data_requested = False
    certificate_inputs = certificate_input_status(
        cacert=ns.cacert,
        client_cert=ns.client_cert,
        client_key=ns.client_key,
    )

    negotiation = {
        "implementation": "aioquic",
        "protocol": state.get("alpn_protocol") or "h3",
        "alpn_requested": ["h3"],
        "tls_version": "TLSv1.3",
        "server_name": str(ns.servername),
        "client_auth_present": bool(ns.client_cert and ns.client_key),
        "handshake_complete": bool(state.get("handshake_complete")),
        "retry_observed": bool(state.get("retry_observed")),
        "resumption_used": bool(state.get("session_resumed")),
        "early_data_requested": early_data_requested,
        "early_data_accepted": bool(state.get("early_data_accepted")),
        "qpack_encoder_stream_seen": bool(state.get("qpack_encoder_stream_seen")),
        "qpack_decoder_stream_seen": bool(state.get("qpack_decoder_stream_seen")),
        "migration_used": bool(migration.get("used")),
        "client_goaway_sent": goaway_sent,
        "response_trailers_mode": bool(ns.response_trailers),
        "certificate_inputs": certificate_inputs,
        "certificate_inputs_ready": certificate_inputs["ready"],
    }
    if isinstance(state.get("client_control_stream_id"), int):
        negotiation["client_control_stream_id"] = int(state["client_control_stream_id"])
    if state.get("received_settings"):
        negotiation["received_settings"] = dict(state["received_settings"])

    response_payload = {
        "status": response_status,
        "headers": [[name, value] for name, value in response_headers],
        "trailers": [[name, value] for name, value in response_trailers],
        "body": response_body.decode("utf-8", errors="replace") if not ns.content_coding else "",
    }
    if ns.content_coding:
        response_payload.update(decode_response_body(response_headers, response_body))

    transcript = {
        "request": {
            "method": "GET" if (ns.response_trailers or ns.content_coding) else "POST",
            "path": str(ns.path),
            "body": "" if (ns.response_trailers or ns.content_coding) else str(ns.body),
            "authority": str(ns.servername),
            "accept_encoding": str(ns.accept_encoding) if ns.content_coding else None,
        },
        "response": response_payload,
        "quic": {
            "handshake_complete": bool(state.get("handshake_complete")),
            "retry_observed": bool(state.get("retry_observed")),
            "migration": migration,
            "session_ticket_received": "value" in captured_ticket,
            "new_token_received": "value" in captured_token,
            "client_goaway_sent": goaway_sent,
            "resumption_hint_available": session_ticket is not None,
            "qpack": {
                "enabled": qpack_enabled,
                "warmup_rounds": list(qpack_details.get("warmup_rounds", [])),
                "encoder_stream_seen_before_main_request": bool(qpack_details.get("encoder_stream_seen_before_main_request")),
                "encoder_stream_seen": bool(state.get("qpack_encoder_stream_seen")),
                "decoder_stream_seen": bool(state.get("qpack_decoder_stream_seen")),
            },
        },
    }
    if state.get("termination_error") is not None:
        transcript["quic"]["termination_error"] = state["termination_error"]

    sock.close()
    return transcript, negotiation, captured_ticket.get("value"), captured_token.get("value")




def _perform_connect_relay_exchange(*, target: tuple[str, int], ns: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    H3Connection, _QuicConfiguration, QuicConnection = _load_aioquic()
    configuration = _build_configuration(ns, session_ticket=None, new_token=None)
    quic = QuicConnection(configuration=configuration)
    http = H3Connection(quic)
    sock = make_udp_socket(_local_bind_host_for_target(target[0]))
    state = _initial_state()
    deadline = time.monotonic() + 20.0

    connect_quic(quic, target)
    flush_pending_datagrams(sock, quic, target)
    _pump_until(
        sock=sock,
        quic=quic,
        http=http,
        target=target,
        state=state,
        deadline=deadline,
        predicate=lambda: bool(state.get("handshake_complete")),
        error_message="QUIC handshake did not complete before the CONNECT relay request was sent",
    )

    with DeterministicRelayTarget() as relay_target:
        stream_id = quic.get_next_available_stream_id()
        http.send_headers(
            stream_id,
            [
                (b":method", b"CONNECT"),
                (b":authority", relay_target.authority.encode("ascii")),
            ],
            end_stream=False,
        )
        flush_pending_datagrams(sock, quic, target)
        _pump_until(
            sock=sock,
            quic=quic,
            http=http,
            target=target,
            state=state,
            deadline=deadline,
            predicate=lambda: bool(_stream_state(state, stream_id).get("headers_received")),
            error_message="HTTP/3 CONNECT response headers were not received before the deadline",
        )
        stream = _stream_state(state, stream_id)
        connect_headers = list(stream.get("response_headers", []))
        connect_status = int(header_map(connect_headers).get(":status", "0"))
        parsed = None
        observed = None
        raw_response = b""
        if connect_status == 200:
            tunnel_request = build_tunneled_http_request(
                path=str(ns.path),
                body=str(ns.body).encode("utf-8"),
                host_header=relay_target.authority,
            )
            http.send_data(stream_id, tunnel_request, end_stream=True)
            flush_pending_datagrams(sock, quic, target)
            _pump_until(
                sock=sock,
                quic=quic,
                http=http,
                target=target,
                state=state,
                deadline=deadline,
                predicate=lambda: bool(_stream_state(state, stream_id).get("response_complete")),
                error_message="HTTP/3 CONNECT relay response body was not received before the deadline",
            )
            stream = _stream_state(state, stream_id)
            raw_response = bytes(stream.get("response_body", b""))
            parsed = parse_tunneled_http_response(raw_response)
            observed = relay_target.wait_for_request(timeout=5.0)

    negotiation = {
        "implementation": "aioquic",
        "protocol": state.get("alpn_protocol") or "h3",
        "alpn_requested": ["h3"],
        "tls_version": "TLSv1.3",
        "server_name": str(ns.servername),
        "client_auth_present": bool(ns.client_cert and ns.client_key),
        "handshake_complete": bool(state.get("handshake_complete")),
        "retry_observed": bool(state.get("retry_observed")),
        "connect_tunnel_established": connect_status == 200,
        "certificate_inputs": certificate_input_status(
            cacert=ns.cacert,
            client_cert=ns.client_cert,
            client_key=ns.client_key,
        ),
    }
    negotiation["certificate_inputs_ready"] = negotiation["certificate_inputs"]["ready"]
    if state.get("received_settings"):
        negotiation["received_settings"] = dict(state["received_settings"])

    transcript = {
        "request": {
            "mode": "connect-relay",
            "method": "CONNECT",
            "authority": relay_target.authority,
            "path": str(ns.path),
            "body": str(ns.body),
        },
        "response": parsed_response_to_json(parsed) if parsed is not None else {
            "status": 0,
            "status_line": "",
            "headers": [],
            "body": "",
        },
        "tunnel": {
            "connect_status": connect_status,
            "connect_headers": [[name, value] for name, value in connect_headers],
            "observed_target": observed_request_to_json(observed),
            "raw_response_size": len(raw_response),
        },
        "quic": {
            "retry_observed": bool(state.get("retry_observed")),
            "handshake_complete": bool(state.get("handshake_complete")),
            "termination_error": state.get("termination_error"),
        },
    }
    sock.close()
    return transcript, negotiation
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        try:
            import aioquic  # type: ignore
        except ModuleNotFoundError:
            print("aioquic unavailable")
            return 2
        print(f"aioquic {getattr(aioquic, '__version__', 'unknown')}")
        return 0

    host = os.environ["INTEROP_TARGET_HOST"]
    port = int(os.environ["INTEROP_TARGET_PORT"])
    target = (host, port)

    try:
        if ns.connect_relay:
            transcript, negotiation = _perform_connect_relay_exchange(target=target, ns=ns)
            write_json("INTEROP_TRANSCRIPT_PATH", transcript)
            write_json("INTEROP_NEGOTIATION_PATH", negotiation)
            print(json.dumps({"transcript": transcript, "negotiation": negotiation}, sort_keys=True))
            body_ok = transcript["response"]["body"] == f"echo:{ns.body}"
            return 0 if transcript["tunnel"]["connect_status"] == 200 and transcript["response"]["status"] == 200 and body_ok else 1

        transcript, negotiation, ticket, new_token = _perform_single_exchange(
            target=target,
            ns=ns,
            session_ticket=None,
            new_token=None,
            zero_rtt=False,
        )

        resumption = env_flag("INTEROP_ENABLE_RESUMPTION")
        zero_rtt = env_flag("INTEROP_ENABLE_ZERO_RTT")
        if resumption:
            if ticket is None:
                transcript["quic"]["resumption_seeded"] = False
                transcript["quic"]["resumption_attempted"] = False
                transcript["quic"]["zero_rtt_attempted"] = False
                negotiation["resumption_used"] = False
                negotiation["early_data_requested"] = False
                negotiation["early_data_accepted"] = False
            else:
                transcript, negotiation, _, _ = _perform_single_exchange(
                    target=target,
                    ns=ns,
                    session_ticket=ticket,
                    new_token=new_token,
                    zero_rtt=zero_rtt,
                )
                transcript["quic"]["resumption_seeded"] = True
                transcript["quic"]["resumption_attempted"] = True
                transcript["quic"]["zero_rtt_attempted"] = bool(zero_rtt)
        else:
            transcript["quic"]["resumption_seeded"] = ticket is not None
            transcript["quic"]["resumption_attempted"] = False
            transcript["quic"]["zero_rtt_attempted"] = False

        write_json("INTEROP_TRANSCRIPT_PATH", transcript)
        write_json("INTEROP_NEGOTIATION_PATH", negotiation)
        print(json.dumps({"transcript": transcript, "negotiation": negotiation}, sort_keys=True))
        if ns.response_trailers:
            trailers = {tuple(item) for item in transcript["response"].get("trailers", [])}
            ok = transcript["response"]["status"] == 200 and transcript["response"]["body"] == "ok" and ("x-trailer-one", "yes") in trailers and ("x-trailer-two", "done") in trailers
            return 0 if ok else 1
        if ns.content_coding:
            vary = str(transcript["response"].get("vary") or "").lower()
            ok = transcript["response"]["status"] == 200 and transcript["response"].get("content_encoding") == "gzip" and "accept-encoding" in vary and transcript["response"].get("decoded_body") == "compress-me"
            return 0 if ok else 1
        return 0 if transcript["response"]["status"] == 200 else 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
