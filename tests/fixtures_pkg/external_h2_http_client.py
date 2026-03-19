from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import time
from pathlib import Path
from typing import Any

import h2.connection
import h2.events


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-h2-http-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--https', action='store_true')
    parser.add_argument('--cacert', default=os.environ.get('INTEROP_CACERT'))
    parser.add_argument('--servername', default=os.environ.get('INTEROP_SERVER_NAME'))
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/interop'))
    parser.add_argument('--body', default=os.environ.get('INTEROP_REQUEST_BODY', 'hello-h2'))
    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        print(f'h2 {getattr(h2, "__version__", "unknown")}')
        return 0

    target_host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    server_name = str(ns.servername or target_host)
    scheme = 'https' if ns.https else 'http'
    body_text = str(ns.body)
    body = body_text.encode('utf-8')

    raw_sock = socket.create_connection((target_host, port), timeout=5.0)
    raw_sock.settimeout(5.0)
    sock: socket.socket | ssl.SSLSocket
    alpn = None
    if ns.https:
        context = ssl.create_default_context(cafile=ns.cacert or None)
        context.check_hostname = True
        context.set_alpn_protocols(['h2'])
        sock = context.wrap_socket(raw_sock, server_hostname=server_name)
        alpn = sock.selected_alpn_protocol()
    else:
        sock = raw_sock

    conn = h2.connection.H2Connection()
    stream_id = 1
    response_headers: list[tuple[str, str]] = []
    response_body = bytearray()
    stream_ended = False
    deadline = time.monotonic() + 15.0
    try:
        conn.initiate_connection()
        sock.sendall(conn.data_to_send())
        headers = [
            (':method', 'POST'),
            (':scheme', scheme),
            (':authority', server_name if ns.https else target_host),
            (':path', str(ns.path)),
            ('content-length', str(len(body))),
        ]
        conn.send_headers(stream_id, headers, end_stream=(len(body) == 0))
        if body:
            conn.send_data(stream_id, body, end_stream=True)
        pending = conn.data_to_send()
        if pending:
            sock.sendall(pending)

        while time.monotonic() < deadline and not stream_ended:
            data = sock.recv(65535)
            if not data:
                break
            events = conn.receive_data(data)
            for event in events:
                if isinstance(event, h2.events.ResponseReceived):
                    response_headers = [
                        (
                            name.decode('ascii') if isinstance(name, bytes) else str(name),
                            value.decode('ascii') if isinstance(value, bytes) else str(value),
                        )
                        for name, value in event.headers
                    ]
                elif isinstance(event, h2.events.DataReceived):
                    response_body.extend(event.data)
                    conn.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                elif isinstance(event, h2.events.StreamEnded):
                    stream_ended = True
            pending = conn.data_to_send()
            if pending:
                sock.sendall(pending)

        status = dict(response_headers).get(':status', '0')
        transcript = {
            'request': {
                'method': 'POST',
                'path': str(ns.path),
                'body': body_text,
                'authority': server_name if ns.https else target_host,
                'scheme': scheme,
            },
            'response': {
                'status': int(status),
                'headers': response_headers,
                'body': response_body.decode('utf-8', errors='replace'),
            },
        }
        negotiation = {
            'implementation': 'python-h2',
            'protocol': 'h2' if ns.https else 'h2c',
            'scheme': scheme,
            'alpn': alpn,
            'server_name': server_name,
        }
        _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
        _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
        print(json.dumps(transcript, sort_keys=True))
        return 0 if int(status) == 200 else 1
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
