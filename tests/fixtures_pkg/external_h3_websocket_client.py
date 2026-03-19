from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

from tigrcorn.protocols.http3.codec import SETTING_ENABLE_CONNECT_PROTOCOL
from tigrcorn.protocols.websocket.frames import decode_close_payload, encode_frame, parse_frame_bytes
from tigrcorn.version import __version__

from ._external_http3_common import (
    env_flag,
    load_pem,
    make_client,
    perform_handshake,
    send_client_settings,
    send_pending,
    wait_for_session_ticket,
    write_json,
)


def _frame_wire_length(data: bytes) -> int:
    if len(data) < 2:
        raise RuntimeError('truncated websocket frame')
    masked = bool(data[1] & 0x80)
    length = data[1] & 0x7F
    pos = 2
    if length == 126:
        if len(data) < pos + 2:
            raise RuntimeError('truncated websocket frame')
        length = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2
    elif length == 127:
        if len(data) < pos + 8:
            raise RuntimeError('truncated websocket frame')
        length = int.from_bytes(data[pos:pos + 8], 'big')
        pos += 8
    if masked:
        pos += 4
    total = pos + length
    if len(data) < total:
        raise RuntimeError('truncated websocket frame')
    return total


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-h3-websocket-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/ws'))
    parser.add_argument('--text', default=os.environ.get('INTEROP_REQUEST_BODY', 'hello-h3-websocket'))
    parser.add_argument('--servername', default=os.environ.get('INTEROP_SERVER_NAME', 'localhost'))
    parser.add_argument('--cacert', default=os.environ.get('INTEROP_CACERT', 'tests/fixtures_certs/interop-localhost-cert.pem'))
    parser.add_argument('--client-cert', default=os.environ.get('INTEROP_CLIENT_CERT'))
    parser.add_argument('--client-key', default=os.environ.get('INTEROP_CLIENT_KEY'))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        print(f'tigrcorn-public-h3-websocket-client {__version__}')
        return 0

    host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    target = (host, port)
    trusted = [load_pem(str(ns.cacert)) or b'']
    client_cert = load_pem(ns.client_cert)
    client_key = load_pem(ns.client_key)
    client, core = make_client(
        server_name=str(ns.servername),
        trusted_certificates=trusted,
        client_cert=client_cert,
        client_key=client_key,
    )
    deadline = time.monotonic() + 20.0
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    sock.settimeout(1.0)
    handshake = perform_handshake(sock, client, core, target=target, deadline=deadline, expect_connect_protocol=True)
    if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) != 1:
        raise RuntimeError('server did not advertise SETTINGS_ENABLE_CONNECT_PROTOCOL')

    control_stream_id = send_client_settings(sock, client, core, target=target, qpack_blocking=env_flag('INTEROP_ENABLE_QPACK_BLOCKING'))
    if env_flag('INTEROP_ENABLE_MIGRATION'):
        migrated = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        migrated.bind(('127.0.0.1', 0))
        migrated.settimeout(1.0)
        migration = {'used': True, 'from': list(sock.getsockname()[:2]), 'to': list(migrated.getsockname()[:2])}
        sock.close()
        sock = migrated
    else:
        migration = {'used': False, 'from': list(sock.getsockname()[:2])}

    payload = core.get_request(0).encode_request(
        [
            (b':method', b'CONNECT'),
            (b':protocol', b'websocket'),
            (b':scheme', b'https'),
            (b':path', str(ns.path).encode('utf-8')),
            (b':authority', str(ns.servername).encode('utf-8')),
            (b'sec-websocket-version', b'13'),
            (b'sec-websocket-protocol', b'chat'),
        ],
        encode_frame(0x1, str(ns.text).encode('utf-8'), masked=True),
    )
    sock.sendto(client.send_stream_data(0, payload, fin=False), target)
    send_pending(sock, client, target)

    response_state = None
    while time.monotonic() < deadline:
        send_pending(sock, client, target)
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        events = client.receive_datagram(data, addr=addr)
        for event in events:
            if getattr(event, 'kind', None) == 'stream':
                state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if state is not None and getattr(state, 'stream_id', None) == 0:
                    response_state = state
        send_pending(sock, client, target)
        if response_state is not None and getattr(response_state, 'ended', False):
            break
    if response_state is None or not getattr(response_state, 'ended', False):
        raise RuntimeError('HTTP/3 websocket response was not received before deadline')

    first_len = _frame_wire_length(response_state.body)
    message_frame = parse_frame_bytes(response_state.body[:first_len], expect_masked=False)
    close_frame = parse_frame_bytes(response_state.body[first_len:], expect_masked=False)
    close_code, close_reason = decode_close_payload(close_frame.payload)
    echoed_text = message_frame.payload.decode('utf-8', errors='replace')

    goaway_sent = False
    if env_flag('INTEROP_ENABLE_GOAWAY'):
        sock.sendto(client.send_stream_data(control_stream_id, core.encode_goaway(0), fin=False), target)
        send_pending(sock, client, target)
        goaway_sent = True
    ticket = wait_for_session_ticket(sock, client, core, target=target, deadline=time.monotonic() + 3.0)
    driver = client.handshake_driver
    transcript = {
        'request': {
            'path': str(ns.path),
            'text': str(ns.text),
            'authority': str(ns.servername),
        },
        'response': {
            'status': int(dict((name.decode('latin1'), value.decode('latin1')) for name, value in response_state.headers).get(':status', '0')),
            'headers': [[name.decode('latin1'), value.decode('latin1')] for name, value in response_state.headers],
            'text': echoed_text,
            'close_code': close_code,
            'close_reason': close_reason,
        },
        'quic': {
            'retry_observed': handshake['retry_observed'],
            'migration': migration,
            'session_ticket_received': ticket is not None,
            'client_goaway_sent': goaway_sent,
        },
    }
    negotiation = {
        'implementation': 'tigrcorn-public-client',
        'protocol': 'h3',
        'tls_version': 'TLSv1.3',
        'server_name': str(ns.servername),
        'client_auth_present': bool(client_cert and client_key),
        'retry_observed': handshake['retry_observed'],
        'connect_protocol_enabled': core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1,
        'migration_used': migration['used'],
        'client_goaway_sent': goaway_sent,
        'resumption_used': bool(getattr(driver, '_using_psk', False)) if driver is not None else False,
    }
    write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps({'transcript': transcript, 'negotiation': negotiation}, sort_keys=True))
    sock.close()
    return 0 if transcript['response']['status'] == 200 and echoed_text == str(ns.text) and close_code == 1000 else 1


if __name__ == '__main__':
    raise SystemExit(main())
