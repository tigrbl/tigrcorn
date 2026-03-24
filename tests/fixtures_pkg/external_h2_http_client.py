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

import h2.config
import h2.connection
import h2.events
import hpack
import hyperframe.frame

from ._connect_relay_fixture import (
    DeterministicRelayTarget,
    build_tunneled_http_request,
    observed_request_to_json,
    parse_tunneled_http_response,
    parsed_response_to_json,
)
from ._content_coding_fixture import decode_response_body

CLIENT_PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'


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
    parser.add_argument('--connect-relay', action='store_true')
    parser.add_argument('--response-trailers', action='store_true')
    parser.add_argument('--content-coding', action='store_true')
    parser.add_argument('--accept-encoding', default=os.environ.get('INTEROP_ACCEPT_ENCODING', 'gzip'))
    return parser


def _open_socket(*, target_host: str, port: int, ns: argparse.Namespace, server_name: str) -> tuple[socket.socket | ssl.SSLSocket, str | None, str]:
    raw_sock = socket.create_connection((target_host, port), timeout=5.0)
    raw_sock.settimeout(5.0)
    scheme = 'https' if ns.https else 'http'
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
    return sock, alpn, scheme


def _collect_stream_response(conn: h2.connection.H2Connection, sock: socket.socket | ssl.SSLSocket, *, stream_id: int, deadline: float) -> tuple[list[tuple[str, str]], bytes, list[tuple[str, str]], bool]:
    response_headers: list[tuple[str, str]] = []
    response_trailers: list[tuple[str, str]] = []
    response_body = bytearray()
    stream_ended = False
    while time.monotonic() < deadline and not stream_ended:
        data = sock.recv(65535)
        if not data:
            break
        events = conn.receive_data(data)
        for event in events:
            if isinstance(event, h2.events.ResponseReceived) and event.stream_id == stream_id:
                response_headers = [
                    (
                        name.decode('ascii') if isinstance(name, bytes) else str(name),
                        value.decode('ascii') if isinstance(value, bytes) else str(value),
                    )
                    for name, value in event.headers
                ]
            elif isinstance(event, h2.events.TrailersReceived) and event.stream_id == stream_id:
                response_trailers = [
                    (
                        name.decode('ascii') if isinstance(name, bytes) else str(name),
                        value.decode('ascii') if isinstance(value, bytes) else str(value),
                    )
                    for name, value in event.headers
                ]
            elif isinstance(event, h2.events.DataReceived) and event.stream_id == stream_id:
                response_body.extend(event.data)
                conn.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
            elif isinstance(event, h2.events.StreamEnded) and event.stream_id == stream_id:
                stream_ended = True
        pending = conn.data_to_send()
        if pending:
            sock.sendall(pending)
    return response_headers, bytes(response_body), response_trailers, stream_ended



def _recv_exact(sock: socket.socket | ssl.SSLSocket, size: int) -> bytes:
    buf = bytearray()
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise EOFError('unexpected EOF while reading HTTP/2 frame')
        buf.extend(chunk)
    return bytes(buf)



def _recv_h2_frame(sock: socket.socket | ssl.SSLSocket) -> hyperframe.frame.Frame:
    header = memoryview(_recv_exact(sock, 9))
    frame, length = hyperframe.frame.Frame.parse_frame_header(header)
    payload = memoryview(_recv_exact(sock, length)) if length else memoryview(b'')
    frame.parse_body(payload)
    return frame



def _send_settings_ack(sock: socket.socket | ssl.SSLSocket) -> None:
    ack = hyperframe.frame.SettingsFrame(0)
    ack.flags.add('ACK')
    sock.sendall(ack.serialize())



def _connect_relay_over_h2(sock: socket.socket | ssl.SSLSocket, *, authority: str, request_path: str, body_text: str, deadline: float) -> tuple[dict[str, Any], dict[str, Any]]:
    encoder = hpack.Encoder()
    decoder = hpack.Decoder()
    sock.sendall(CLIENT_PREFACE)
    settings = hyperframe.frame.SettingsFrame(0)
    sock.sendall(settings.serialize())

    connect_frame = hyperframe.frame.HeadersFrame(1)
    connect_frame.data = encoder.encode([(b':method', b'CONNECT'), (b':authority', authority.encode('ascii'))])
    connect_frame.flags.add('END_HEADERS')
    sock.sendall(connect_frame.serialize())

    connect_headers: list[tuple[str, str]] = []
    raw_response = bytearray()
    stream_ended = False
    sent_tunnel_request = False
    while time.monotonic() < deadline:
        frame = _recv_h2_frame(sock)
        if isinstance(frame, hyperframe.frame.SettingsFrame):
            if 'ACK' not in frame.flags:
                _send_settings_ack(sock)
            continue
        if isinstance(frame, hyperframe.frame.WindowUpdateFrame):
            continue
        if isinstance(frame, hyperframe.frame.PingFrame):
            if 'ACK' not in frame.flags:
                pong = hyperframe.frame.PingFrame(0)
                pong.opaque_data = frame.opaque_data
                pong.flags.add('ACK')
                sock.sendall(pong.serialize())
            continue
        if isinstance(frame, hyperframe.frame.HeadersFrame) and frame.stream_id == 1:
            decoded = decoder.decode(frame.data)
            connect_headers.extend(
                [
                    (
                        name.decode('ascii') if isinstance(name, bytes) else str(name),
                        value.decode('ascii') if isinstance(value, bytes) else str(value),
                    )
                    for name, value in decoded
                ]
            )
            connect_status = int(dict(connect_headers).get(':status', '0'))
            if connect_status != 200:
                break
            if not sent_tunnel_request:
                tunnel_request = build_tunneled_http_request(
                    path=request_path,
                    body=body_text.encode('utf-8'),
                    host_header=authority,
                )
                data_frame = hyperframe.frame.DataFrame(1)
                data_frame.data = tunnel_request
                data_frame.flags.add('END_STREAM')
                sock.sendall(data_frame.serialize())
                sent_tunnel_request = True
            continue
        if isinstance(frame, hyperframe.frame.DataFrame) and frame.stream_id == 1:
            raw_response.extend(frame.data)
            if 'END_STREAM' in frame.flags:
                stream_ended = True
                break
        if isinstance(frame, hyperframe.frame.RstStreamFrame) and frame.stream_id == 1:
            break
    parsed = parse_tunneled_http_response(bytes(raw_response)) if raw_response else None
    transcript = {
        'request': {
            'mode': 'connect-relay',
            'method': 'CONNECT',
            'authority': authority,
            'path': request_path,
            'body': body_text,
        },
        'response': parsed_response_to_json(parsed) if parsed is not None else {
            'status': 0,
            'status_line': '',
            'headers': [],
            'body': '',
        },
        'tunnel': {
            'connect_status': int(dict(connect_headers).get(':status', '0')),
            'connect_headers': connect_headers,
            'raw_response_size': len(raw_response),
            'stream_ended': stream_ended,
        },
    }
    negotiation = {
        'implementation': 'python-h2',
        'protocol': 'h2c',
        'scheme': 'http',
        'connect_tunnel_established': int(dict(connect_headers).get(':status', '0')) == 200,
    }
    return transcript, negotiation



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        print(f'h2 {getattr(h2, "__version__", "unknown")}')
        return 0

    target_host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    server_name = str(ns.servername or target_host)
    body_text = str(ns.body)

    sock, alpn, scheme = _open_socket(target_host=target_host, port=port, ns=ns, server_name=server_name)
    stream_id = 1
    deadline = time.monotonic() + 15.0
    try:
        if ns.connect_relay:
            with DeterministicRelayTarget() as relay_target:
                transcript, negotiation = _connect_relay_over_h2(
                    sock,
                    authority=relay_target.authority,
                    request_path=str(ns.path),
                    body_text=body_text,
                    deadline=deadline,
                )
                observed = relay_target.wait_for_request(timeout=5.0)
            transcript['tunnel']['observed_target'] = observed_request_to_json(observed)
            negotiation['alpn'] = alpn
            negotiation['server_name'] = server_name
            _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
            _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
            print(json.dumps(transcript, sort_keys=True))
            return 0 if transcript['tunnel']['connect_status'] == 200 and transcript['response']['status'] == 200 and transcript['response']['body'] == f'echo:{body_text}' else 1

        conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True, validate_outbound_headers=False))
        body = body_text.encode('utf-8')
        conn.initiate_connection()
        sock.sendall(conn.data_to_send())
        if ns.response_trailers:
            headers = [
                (':method', 'GET'),
                (':scheme', scheme),
                (':authority', server_name if ns.https else target_host),
                (':path', str(ns.path)),
            ]
            conn.send_headers(stream_id, headers, end_stream=True)
        elif ns.content_coding:
            headers = [
                (':method', 'GET'),
                (':scheme', scheme),
                (':authority', server_name if ns.https else target_host),
                (':path', str(ns.path)),
                ('accept-encoding', str(ns.accept_encoding)),
            ]
            conn.send_headers(stream_id, headers, end_stream=True)
        else:
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
        response_headers, response_body, response_trailers, stream_ended = _collect_stream_response(conn, sock, stream_id=stream_id, deadline=deadline)
        status = dict(response_headers).get(':status', '0')
        response_payload = {
            'status': int(status),
            'headers': response_headers,
            'body': response_body.decode('utf-8', errors='replace') if not ns.content_coding else '',
            'trailers': response_trailers,
            'stream_ended': stream_ended,
        }
        if ns.content_coding:
            response_payload.update(decode_response_body(response_headers, response_body))
        transcript = {
            'request': {
                'method': 'GET' if (ns.response_trailers or ns.content_coding) else 'POST',
                'path': str(ns.path),
                'body': '' if (ns.response_trailers or ns.content_coding) else body_text,
                'authority': server_name if ns.https else target_host,
                'scheme': scheme,
                'accept_encoding': ns.accept_encoding if ns.content_coding else None,
            },
            'response': response_payload,
        }
        negotiation = {
            'implementation': 'python-h2',
            'protocol': 'h2' if ns.https else 'h2c',
            'scheme': scheme,
            'alpn': alpn,
            'server_name': server_name,
            'response_trailers_mode': bool(ns.response_trailers),
            'content_coding_mode': bool(ns.content_coding),
        }
        _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
        _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
        print(json.dumps(transcript, sort_keys=True))
        if ns.response_trailers:
            success = int(status) == 200 and transcript['response']['body'] == 'ok' and ('x-trailer-one', 'yes') in response_trailers and ('x-trailer-two', 'done') in response_trailers and stream_ended
            return 0 if success else 1
        if ns.content_coding:
            vary = (response_payload.get('vary') or '').lower()
            success = int(status) == 200 and response_payload.get('content_encoding') == 'gzip' and 'accept-encoding' in vary and response_payload.get('decoded_body') == 'compress-me' and stream_ended
            return 0 if success else 1
        return 0 if int(status) == 200 else 1
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
