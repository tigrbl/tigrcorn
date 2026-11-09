from __future__ import annotations

from .client_core import *

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
