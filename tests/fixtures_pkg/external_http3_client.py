from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

from tigrcorn.version import __version__

from ._external_http3_common import (
    env_flag,
    exchange_request,
    load_pem,
    make_client,
    perform_handshake,
    send_client_settings,
    send_pending,
    wait_for_session_ticket,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-http3-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/interop'))
    parser.add_argument('--body', default=os.environ.get('INTEROP_REQUEST_BODY', 'hello-http3'))
    parser.add_argument('--servername', default=os.environ.get('INTEROP_SERVER_NAME', 'localhost'))
    parser.add_argument('--cacert', default=os.environ.get('INTEROP_CACERT', 'tests/fixtures_certs/interop-localhost-cert.pem'))
    parser.add_argument('--client-cert', default=os.environ.get('INTEROP_CLIENT_CERT'))
    parser.add_argument('--client-key', default=os.environ.get('INTEROP_CLIENT_KEY'))
    return parser


def _response_headers_to_map(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    return {name.decode('latin1'): value.decode('latin1') for name, value in headers}


def _perform_single_exchange(
    *,
    target: tuple[str, int],
    ns: argparse.Namespace,
    session_ticket=None,
    enable_early_data: bool = False,
) -> tuple[dict[str, object], dict[str, object], object | None]:
    trusted = [load_pem(str(ns.cacert)) or b'']
    client_cert = load_pem(ns.client_cert)
    client_key = load_pem(ns.client_key)
    body = str(ns.body).encode('utf-8')
    client, core = make_client(
        server_name=str(ns.servername),
        trusted_certificates=trusted,
        client_cert=client_cert,
        client_key=client_key,
        session_ticket=session_ticket,
        enable_early_data=enable_early_data,
    )
    deadline = time.monotonic() + 20.0
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    sock.settimeout(1.0)
    qpack_blocking = env_flag('INTEROP_ENABLE_QPACK_BLOCKING')
    goaway_enabled = env_flag('INTEROP_ENABLE_GOAWAY')
    if enable_early_data and session_ticket is not None:
        sock.sendto(client.start_handshake(), target)
        response_state, sock, migration = exchange_request(
            sock,
            client,
            core,
            target=target,
            path=str(ns.path),
            body=body,
            authority=str(ns.servername).encode('utf-8'),
            deadline=deadline,
            migrate_after_send=env_flag('INTEROP_ENABLE_MIGRATION'),
            early_data=True,
        )
        handshake = perform_handshake(sock, client, core, target=target, deadline=deadline, start=False)
        control_stream_id = None
    else:
        handshake = perform_handshake(sock, client, core, target=target, deadline=deadline)
        control_stream_id = send_client_settings(sock, client, core, target=target, qpack_blocking=qpack_blocking)
        response_state, sock, migration = exchange_request(
            sock,
            client,
            core,
            target=target,
            path=str(ns.path),
            body=body,
            authority=str(ns.servername).encode('utf-8'),
            deadline=deadline,
            migrate_after_send=env_flag('INTEROP_ENABLE_MIGRATION'),
            early_data=False,
        )
    goaway_sent = False
    if goaway_enabled and control_stream_id is not None:
        sock.sendto(client.send_stream_data(control_stream_id, core.encode_goaway(0), fin=False), target)
        send_pending(sock, client, target)
        goaway_sent = True
    ticket = wait_for_session_ticket(sock, client, core, target=target, deadline=time.monotonic() + 3.0)
    driver = client.handshake_driver
    negotiation: dict[str, object] = {
        'implementation': 'tigrcorn-public-client',
        'protocol': 'h3',
        'tls_version': 'TLSv1.3',
        'server_name': str(ns.servername),
        'client_auth_present': bool(client_cert and client_key),
        'retry_observed': handshake['retry_observed'],
        'resumption_used': bool(getattr(driver, '_using_psk', False)) if driver is not None else False,
        'early_data_requested': bool(getattr(driver, 'early_data_requested', False)) if driver is not None else False,
        'early_data_accepted': bool(getattr(driver, 'early_data_accepted', False)) if driver is not None else False,
        'qpack_encoder_stream_seen': core.state.remote_qpack_encoder_stream_id is not None,
        'qpack_decoder_stream_seen': core.state.remote_qpack_decoder_stream_id is not None,
        'migration_used': migration['used'],
        'client_goaway_sent': goaway_sent,
    }
    if control_stream_id is not None:
        negotiation['client_control_stream_id'] = control_stream_id
    transcript: dict[str, object] = {
        'request': {
            'method': 'POST',
            'path': str(ns.path),
            'body': str(ns.body),
            'authority': str(ns.servername),
        },
        'response': {
            'status': int(_response_headers_to_map(response_state.headers).get(':status', '0')),
            'headers': [[name.decode('latin1'), value.decode('latin1')] for name, value in response_state.headers],
            'body': response_state.body.decode('utf-8', errors='replace'),
        },
        'quic': {
            'retry_observed': handshake['retry_observed'],
            'migration': migration,
            'session_ticket_received': ticket is not None,
            'client_goaway_sent': goaway_sent,
        },
    }
    sock.close()
    return transcript, negotiation, ticket


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        print(f'tigrcorn-public-http3-client {__version__}')
        return 0

    host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    target = (host, port)

    resumption = env_flag('INTEROP_ENABLE_RESUMPTION')
    zero_rtt = env_flag('INTEROP_ENABLE_ZERO_RTT')
    transcript, negotiation, ticket = _perform_single_exchange(target=target, ns=ns)

    if resumption:
        if ticket is None:
            transcript['quic']['resumption_seeded'] = False
            negotiation['resumption_used'] = False
            negotiation['early_data_requested'] = False
            negotiation['early_data_accepted'] = False
        else:
            transcript['quic']['resumption_seeded'] = True
            transcript, negotiation, _ = _perform_single_exchange(
                target=target,
                ns=ns,
                session_ticket=ticket,
                enable_early_data=zero_rtt,
            )
            transcript['quic']['resumption_seeded'] = True
            transcript['quic']['resumption_attempted'] = True
            transcript['quic']['zero_rtt_attempted'] = zero_rtt
    else:
        transcript['quic']['resumption_seeded'] = ticket is not None
        transcript['quic']['resumption_attempted'] = False
        transcript['quic']['zero_rtt_attempted'] = False

    write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps({'transcript': transcript, 'negotiation': negotiation}, sort_keys=True))
    return 0 if transcript['response']['status'] == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
