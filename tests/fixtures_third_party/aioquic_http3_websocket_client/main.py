from __future__ import annotations

import json
import os
import sys
import time

from .client_core import *

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


