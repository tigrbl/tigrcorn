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
    write_json,
)


def _load_dependencies() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from aioquic.h3.connection import H3Connection  # type: ignore
        from aioquic.quic.configuration import QuicConfiguration  # type: ignore
        from aioquic.quic.connection import QuicConnection  # type: ignore
        import wsproto.extensions as ws_extensions  # type: ignore
        import wsproto.frame_protocol as ws_frames  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on external runtime
        raise RuntimeError(
            "aioquic and wsproto are required to run the true third-party RFC 9220 certification adapters."
        ) from exc
    return H3Connection, QuicConfiguration, QuicConnection, ws_extensions, ws_frames


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aioquic-http3-websocket-client")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--path", default=os.environ.get("INTEROP_REQUEST_PATH", "/ws"))
    parser.add_argument("--text", default=os.environ.get("INTEROP_REQUEST_BODY", "hello-h3-websocket"))
    parser.add_argument("--compression", default=os.environ.get("INTEROP_WEBSOCKET_COMPRESSION", "off"))
    parser.add_argument("--servername", default=os.environ.get("INTEROP_SERVER_NAME", "localhost"))
    parser.add_argument("--cacert", default=os.environ.get("INTEROP_CACERT", "tests/fixtures_certs/interop-localhost-cert.pem"))
    parser.add_argument("--client-cert", default=os.environ.get("INTEROP_CLIENT_CERT"))
    parser.add_argument("--client-key", default=os.environ.get("INTEROP_CLIENT_KEY"))
    return parser


def _build_configuration(ns: argparse.Namespace) -> Any:
    _H3Connection, QuicConfiguration, _QuicConnection, _ws_extensions, _ws_frames = _load_dependencies()
    configuration = QuicConfiguration(is_client=True, alpn_protocols=["h3"])
    configuration.verify_mode = ssl.CERT_REQUIRED
    configuration.load_verify_locations(str(ns.cacert))
    if ns.client_cert and ns.client_key:
        configuration.load_cert_chain(str(ns.client_cert), str(ns.client_key))
    configuration.server_name = str(ns.servername)
    configuration.max_datagram_frame_size = 65536
    return configuration


def _initial_state() -> dict[str, Any]:
    return {
        "handshake_complete": False,
        "alpn_protocol": "h3",
        "retry_observed": False,
        "streams": {},
        "received_settings": {},
        "connect_protocol_enabled": False,
        "client_control_stream_id": None,
        "qpack_encoder_stream_seen": False,
        "qpack_decoder_stream_seen": False,
        "termination_error": None,
    }


def _stream_state(state: dict[str, Any], stream_id: int) -> dict[str, Any]:
    streams = state.setdefault("streams", {})
    if stream_id not in streams:
        streams[stream_id] = {
            "response_headers": [],
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
        elif event_name == "ProtocolNegotiated":
            state["alpn_protocol"] = getattr(event, "alpn_protocol", state.get("alpn_protocol")) or state.get("alpn_protocol")
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
                    stream["response_headers"] = header_pairs_to_text(list(getattr(http_event, "headers", [])))
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


def _decode_websocket_response(ws_frames: Any, payload: bytes, *, protocol: Any | None = None) -> tuple[str, int | None, str]:
    # This adapter runs on the client side and is decoding server-to-client
    # frames carried inside the RFC 9220 CONNECT stream. Server frames are
    # unmasked, so the wsproto parser must be instantiated in client mode.
    receiver = protocol if protocol is not None else ws_frames.FrameProtocol(client=True, extensions=[])
    receiver.receive_bytes(payload)
    text_value = ""
    close_code: int | None = None
    close_reason = ""
    for frame in receiver.received_frames():
        if getattr(frame, "opcode", None) == ws_frames.Opcode.TEXT:
            body = frame.payload
            if isinstance(body, str):
                text_value += body
            elif isinstance(body, (bytes, bytearray)):
                text_value += bytes(body).decode("utf-8", errors="replace")
            else:
                text_value += str(body)
        elif getattr(frame, "opcode", None) == ws_frames.Opcode.CLOSE:
            body = frame.payload
            if isinstance(body, tuple) and len(body) == 2:
                close_code = int(body[0])
                close_reason = str(body[1])
            elif isinstance(body, (bytes, bytearray)) and len(body) >= 2:
                close_code = int.from_bytes(bytes(body[:2]), "big")
                close_reason = bytes(body[2:]).decode("utf-8", errors="replace")
    return text_value, close_code, close_reason


def _local_bind_host_for_target(host: str) -> str:
    return "::1" if ":" in host else "127.0.0.1"


def _build_extension_offer_header(*, compression: str, ws_extensions: Any) -> tuple[bytes | None, list[Any]]:
    if compression != "permessage-deflate":
        return None, []
    extension = ws_extensions.PerMessageDeflate()
    offer = extension.offer()
    value = "permessage-deflate"
    if isinstance(offer, str) and offer:
        value += "; " + offer
    return value.encode("ascii"), [extension]



def _build_frame_protocol(*, compression: str, response_extension_header: str, offered_extensions: list[Any], ws_frames: Any, ws_extensions: Any) -> tuple[Any, list[str]]:
    if compression != "permessage-deflate" or not response_extension_header.lower().startswith("permessage-deflate"):
        return ws_frames.FrameProtocol(client=True, extensions=[]), []
    finalized: list[Any] = []
    for extension in offered_extensions:
        if isinstance(extension, ws_extensions.PerMessageDeflate):
            extension.finalize(response_extension_header)
            finalized.append(extension)
    if not finalized:
        return ws_frames.FrameProtocol(client=True, extensions=[]), []
    return ws_frames.FrameProtocol(client=True, extensions=finalized), [type(item).__name__ for item in finalized]


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
        H3Connection, _QuicConfiguration, QuicConnection, ws_extensions, ws_frames = _load_dependencies()
        configuration = _build_configuration(ns)

        captured_ticket: dict[str, object] = {}
        quic = QuicConnection(configuration=configuration, session_ticket_handler=lambda ticket: captured_ticket.setdefault("value", ticket))
        http = H3Connection(quic)
        sock = make_udp_socket(_local_bind_host_for_target(target[0]))
        local_before = list(sock.getsockname()[:2])
        state = _initial_state()
        stream_id = quic.get_next_available_stream_id()
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
            predicate=lambda: bool(state.get("handshake_complete")) and bool(state.get("received_settings")),
            error_message="QUIC handshake or HTTP/3 settings negotiation did not complete before the RFC 9220 CONNECT request",
        )
        if not bool(state.get("connect_protocol_enabled")):
            raise RuntimeError("server did not advertise SETTINGS_ENABLE_CONNECT_PROTOCOL")

        compression = str(ns.compression)
        extension_header, offered_extensions = _build_extension_offer_header(compression=compression, ws_extensions=ws_extensions)
        headers = [
            (b":method", b"CONNECT"),
            (b":protocol", b"websocket"),
            (b":scheme", b"https"),
            (b":path", str(ns.path).encode("utf-8")),
            (b":authority", str(ns.servername).encode("utf-8")),
            (b"sec-websocket-version", b"13"),
            (b"sec-websocket-protocol", b"chat"),
        ]
        if extension_header is not None:
            headers.append((b"sec-websocket-extensions", extension_header))
        http.send_headers(stream_id, headers, end_stream=False)
        flush_pending_datagrams(sock, quic, target)

        _pump_until(
            sock=sock,
            quic=quic,
            http=http,
            target=target,
            state=state,
            deadline=deadline,
            predicate=lambda: bool(_stream_state(state, stream_id).get("headers_received")),
            error_message="RFC 9220 response headers were not received before the deadline",
        )
        response_header_pairs = list(_stream_state(state, stream_id).get("response_headers", []))
        response_extension_header = header_map(response_header_pairs).get("sec-websocket-extensions", "")
        sender, negotiated_extensions = _build_frame_protocol(
            compression=compression,
            response_extension_header=str(response_extension_header),
            offered_extensions=offered_extensions,
            ws_frames=ws_frames,
            ws_extensions=ws_extensions,
        )

        # Match the package-owned RFC 9220 client: send a single text frame and
        # keep the CONNECT stream open while waiting for the server's echoed
        # frame and close handshake. Sending an immediate CLOSE frame here races
        # the application echo path and is not part of the scenario assertions.
        websocket_payload = bytes(sender.send_data(str(ns.text), fin=True))
        http.send_data(stream_id, websocket_payload, end_stream=False)
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
            predicate=lambda: bool(_stream_state(state, stream_id).get("response_complete")),
            error_message="RFC 9220 websocket response was not received before the deadline",
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

        response = _stream_state(state, stream_id)
        response_headers = list(response.get("response_headers", []))
        response_status = int(header_map(response_headers).get(":status", "0"))
        text_value, close_code, close_reason = _decode_websocket_response(
            ws_frames,
            bytes(response.get("response_body", b"")),
            protocol=sender,
        )
        response_extension_header = header_map(response_headers).get("sec-websocket-extensions", "")

        negotiation = {
            "implementation": "aioquic",
            "protocol": state.get("alpn_protocol") or "h3",
            "alpn_requested": ["h3"],
            "tls_version": "TLSv1.3",
            "server_name": str(ns.servername),
            "client_auth_present": bool(ns.client_cert and ns.client_key),
            "handshake_complete": bool(state.get("handshake_complete")),
            "retry_observed": bool(state.get("retry_observed")),
            "connect_protocol_enabled": bool(state.get("connect_protocol_enabled")),
            "compression_requested": compression,
            "response_extension_header": str(response_extension_header),
            "negotiated_extensions": negotiated_extensions,
            "qpack_encoder_stream_seen": bool(state.get("qpack_encoder_stream_seen")),
            "qpack_decoder_stream_seen": bool(state.get("qpack_decoder_stream_seen")),
            "migration_used": bool(migration.get("used")),
            "client_goaway_sent": goaway_sent,
            "certificate_inputs": certificate_input_status(
                cacert=ns.cacert,
                client_cert=ns.client_cert,
                client_key=ns.client_key,
            ),
        }
        negotiation["certificate_inputs_ready"] = negotiation["certificate_inputs"]["ready"]
        if isinstance(state.get("client_control_stream_id"), int):
            negotiation["client_control_stream_id"] = int(state["client_control_stream_id"])
        if state.get("received_settings"):
            negotiation["received_settings"] = dict(state["received_settings"])

        transcript = {
            "request": {
                "path": str(ns.path),
                "text": str(ns.text),
                "authority": str(ns.servername),
                "compression": compression,
                "extension_offer": extension_header.decode("ascii") if extension_header is not None else "",
            },
            "response": {
                "status": response_status,
                "headers": [[name, value] for name, value in response_headers],
                "text": text_value,
                "close_code": close_code,
                "close_reason": close_reason,
                "extension_header": str(response_extension_header),
            },
            "quic": {
                "handshake_complete": bool(state.get("handshake_complete")),
                "retry_observed": bool(state.get("retry_observed")),
                "migration": migration,
                "session_ticket_received": "value" in captured_ticket,
                "client_goaway_sent": goaway_sent,
                "qpack": {
                    "encoder_stream_seen": bool(state.get("qpack_encoder_stream_seen")),
                    "decoder_stream_seen": bool(state.get("qpack_decoder_stream_seen")),
                },
            },
        }
        if state.get("termination_error") is not None:
            transcript["quic"]["termination_error"] = state["termination_error"]

        write_json("INTEROP_TRANSCRIPT_PATH", transcript)
        write_json("INTEROP_NEGOTIATION_PATH", negotiation)
        print(json.dumps({"transcript": transcript, "negotiation": negotiation}, sort_keys=True))
        sock.close()
        return 0 if response_status == 200 and text_value == str(ns.text) and close_code == 1000 else 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
