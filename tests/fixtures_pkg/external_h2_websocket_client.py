from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

import h2.connection
import h2.events
import h2.settings
import wsproto.extensions as ws_extensions
import wsproto.frame_protocol as ws_frames


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-h2-websocket-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/ws'))
    parser.add_argument('--text', default=os.environ.get('INTEROP_REQUEST_BODY', 'hello-h2-websocket'))
    parser.add_argument('--compression', default=os.environ.get('INTEROP_WEBSOCKET_COMPRESSION', 'off'))
    return parser


def _response_header(headers: list[tuple[str, str]], name: str) -> str | None:
    target = name.lower()
    for key, value in headers:
        if key.lower() == target:
            return value
    return None


def _build_extension_offer(compression: str) -> tuple[list[tuple[str, str]], list[Any]]:
    if compression != 'permessage-deflate':
        return [], []
    extension = ws_extensions.PerMessageDeflate()
    offer = extension.offer()
    value = 'permessage-deflate'
    if isinstance(offer, str) and offer:
        value += '; ' + offer
    return [('sec-websocket-extensions', value)], [extension]


def _build_frame_protocol(*, compression: str, response_extension_header: str | None, offered_extensions: list[Any]) -> tuple[Any, list[str]]:
    if compression != 'permessage-deflate' or not response_extension_header or not response_extension_header.lower().startswith('permessage-deflate'):
        return ws_frames.FrameProtocol(client=True, extensions=[]), []
    finalized: list[Any] = []
    for extension in offered_extensions:
        if isinstance(extension, ws_extensions.PerMessageDeflate):
            extension.finalize(response_extension_header)
            finalized.append(extension)
    if not finalized:
        return ws_frames.FrameProtocol(client=True, extensions=[]), []
    return ws_frames.FrameProtocol(client=True, extensions=finalized), [type(item).__name__ for item in finalized]


def _decode_frames(protocol: Any, payload: bytes) -> tuple[str, int | None]:
    protocol.receive_bytes(payload)
    text_value = ''
    close_code: int | None = None
    for frame in protocol.received_frames():
        opcode = getattr(frame, 'opcode', None)
        if opcode == ws_frames.Opcode.TEXT:
            body = frame.payload
            if isinstance(body, str):
                text_value += body
            elif isinstance(body, (bytes, bytearray)):
                text_value += bytes(body).decode('utf-8', errors='replace')
            else:
                text_value += str(body)
        elif opcode == ws_frames.Opcode.CLOSE:
            body = frame.payload
            if isinstance(body, tuple) and len(body) == 2:
                close_code = int(body[0])
            elif isinstance(body, (bytes, bytearray)) and len(body) >= 2:
                close_code = int.from_bytes(bytes(body[:2]), 'big')
    return text_value, close_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        print(f'h2 {getattr(h2, "__version__", "unknown")}')
        return 0

    host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    path = str(ns.path)
    text = str(ns.text)
    compression = str(ns.compression)
    stream_id = 1
    extension_headers, offered_extensions = _build_extension_offer(compression)
    request_headers = [
        (':method', 'CONNECT'),
        (':protocol', 'websocket'),
        (':scheme', 'http'),
        (':path', path),
        (':authority', 'example'),
        ('sec-websocket-version', '13'),
        *extension_headers,
    ]

    conn = h2.connection.H2Connection()
    sock = socket.create_connection((host, port), timeout=5.0)
    sock.settimeout(5.0)
    response_headers: list[tuple[str, str]] = []
    response_body = bytearray()
    enable_connect = False
    stream_ended = False
    headers_received = False
    deadline = time.monotonic() + 10.0
    try:
        conn.initiate_connection()
        sock.sendall(conn.data_to_send())
        while time.monotonic() < deadline and not enable_connect:
            data = sock.recv(65535)
            if not data:
                break
            events = conn.receive_data(data)
            for event in events:
                if isinstance(event, h2.events.RemoteSettingsChanged):
                    setting = event.changed_settings.get(h2.settings.SettingCodes.ENABLE_CONNECT_PROTOCOL)
                    if setting is not None and int(setting.new_value) == 1:
                        enable_connect = True
                elif h2.settings.SettingCodes.ENABLE_CONNECT_PROTOCOL in conn.remote_settings:
                    try:
                        enable_connect = int(conn.remote_settings[h2.settings.SettingCodes.ENABLE_CONNECT_PROTOCOL]) == 1
                    except Exception:
                        pass
            pending = conn.data_to_send()
            if pending:
                sock.sendall(pending)
        if not enable_connect:
            raise RuntimeError('server did not advertise SETTINGS_ENABLE_CONNECT_PROTOCOL')

        conn.send_headers(stream_id, request_headers, end_stream=False)
        sock.sendall(conn.data_to_send())

        while time.monotonic() < deadline and not headers_received:
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
                    headers_received = True
                elif isinstance(event, h2.events.StreamEnded):
                    stream_ended = True
            pending = conn.data_to_send()
            if pending:
                sock.sendall(pending)
        if not headers_received:
            raise RuntimeError('server did not return HTTP/2 WebSocket response headers before the deadline')

        response_extension_header = _response_header(response_headers, 'sec-websocket-extensions')
        websocket_protocol, negotiated_extensions = _build_frame_protocol(
            compression=compression,
            response_extension_header=response_extension_header,
            offered_extensions=offered_extensions,
        )
        conn.send_data(stream_id, bytes(websocket_protocol.send_data(text, fin=True)), end_stream=False)
        sock.sendall(conn.data_to_send())

        echoed_text = ''
        close_code = None
        close_sent = False
        while time.monotonic() < deadline and not stream_ended:
            data = sock.recv(65535)
            if not data:
                break
            events = conn.receive_data(data)
            for event in events:
                if isinstance(event, h2.events.DataReceived):
                    response_body.extend(event.data)
                    text_chunk, close_chunk = _decode_frames(websocket_protocol, event.data)
                    if text_chunk:
                        echoed_text += text_chunk
                    if close_chunk is not None:
                        close_code = close_chunk
                    conn.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                elif isinstance(event, h2.events.StreamEnded):
                    stream_ended = True
            if echoed_text and not close_sent:
                conn.send_data(stream_id, bytes(websocket_protocol.close(1000)), end_stream=True)
                close_sent = True
            pending = conn.data_to_send()
            if pending:
                sock.sendall(pending)
            if close_sent and close_code is not None:
                break

        transcript = {
            'request': {
                'path': path,
                'text': text,
                'authority': 'example',
                'compression': compression,
                'extension_offer': _response_header(request_headers, 'sec-websocket-extensions'),
            },
            'response': {
                'headers': response_headers,
                'text': echoed_text,
                'close_code': close_code,
                'extension_header': response_extension_header,
            },
        }
        negotiation = {
            'implementation': 'python-h2',
            'protocol': 'h2c',
            'settings_enable_connect_protocol': enable_connect,
            'compression_requested': compression,
            'response_extension_header': response_extension_header or '',
            'negotiated_extensions': negotiated_extensions,
        }
        _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
        _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
        print(json.dumps({'transcript': transcript, 'negotiation': negotiation}, sort_keys=True))
        status = _response_header(response_headers, ':status')
        return 0 if status == '200' and echoed_text == text else 1
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
