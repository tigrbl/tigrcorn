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


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _mask_payload(payload: bytes, masking_key: bytes) -> bytes:
    return bytes(byte ^ masking_key[index % 4] for index, byte in enumerate(payload))


def _encode_ws_frame(opcode: int, payload: bytes, *, masked: bool) -> bytes:
    first = 0x80 | (opcode & 0x0F)
    mask_bit = 0x80 if masked else 0x00
    length = len(payload)
    header = bytearray([first])
    if length < 126:
        header.append(mask_bit | length)
    elif length < (1 << 16):
        header.append(mask_bit | 126)
        header.extend(length.to_bytes(2, 'big'))
    else:
        header.append(mask_bit | 127)
        header.extend(length.to_bytes(8, 'big'))
    if masked:
        masking_key = b'\x01\x02\x03\x04'
        header.extend(masking_key)
        payload = _mask_payload(payload, masking_key)
    header.extend(payload)
    return bytes(header)


def _decode_ws_frames(data: bytes) -> list[tuple[int, bytes]]:
    offset = 0
    frames: list[tuple[int, bytes]] = []
    while offset < len(data):
        if len(data) - offset < 2:
            raise ValueError('truncated websocket frame')
        first = data[offset]
        second = data[offset + 1]
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        offset += 2
        if length == 126:
            if len(data) - offset < 2:
                raise ValueError('truncated websocket frame length')
            length = int.from_bytes(data[offset:offset + 2], 'big')
            offset += 2
        elif length == 127:
            if len(data) - offset < 8:
                raise ValueError('truncated websocket frame length')
            length = int.from_bytes(data[offset:offset + 8], 'big')
            offset += 8
        if masked:
            if len(data) - offset < 4:
                raise ValueError('truncated websocket masking key')
            masking_key = data[offset:offset + 4]
            offset += 4
        else:
            masking_key = b''
        if len(data) - offset < length:
            raise ValueError('truncated websocket payload')
        payload = data[offset:offset + length]
        offset += length
        if masked:
            payload = _mask_payload(payload, masking_key)
        frames.append((opcode, payload))
    return frames


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-h2-websocket-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/ws'))
    parser.add_argument('--text', default=os.environ.get('INTEROP_REQUEST_BODY', 'hello-h2-websocket'))
    return parser


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
    stream_id = 1
    request_headers = [
        (':method', 'CONNECT'),
        (':protocol', 'websocket'),
        (':scheme', 'http'),
        (':path', path),
        (':authority', 'example'),
        ('sec-websocket-version', '13'),
    ]

    conn = h2.connection.H2Connection()
    sock = socket.create_connection((host, port), timeout=5.0)
    sock.settimeout(5.0)
    response_headers: list[tuple[str, str]] = []
    response_body = bytearray()
    enable_connect = False
    stream_ended = False
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
        conn.send_data(stream_id, _encode_ws_frame(0x1, text.encode('utf-8'), masked=True), end_stream=False)
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
                if isinstance(event, h2.events.ResponseReceived):
                    response_headers = [(name.decode('ascii') if isinstance(name, bytes) else str(name), value.decode('ascii') if isinstance(value, bytes) else str(value)) for name, value in event.headers]
                elif isinstance(event, h2.events.DataReceived):
                    response_body.extend(event.data)
                    try:
                        frames = _decode_ws_frames(event.data)
                    except Exception:
                        frames = []
                    for opcode, payload in frames:
                        if opcode == 0x1:
                            echoed_text = payload.decode('utf-8')
                        elif opcode == 0x8 and len(payload) >= 2:
                            close_code = int.from_bytes(payload[:2], 'big')
                    conn.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                elif isinstance(event, h2.events.StreamEnded):
                    stream_ended = True
            if echoed_text and not close_sent:
                conn.send_data(stream_id, _encode_ws_frame(0x8, (1000).to_bytes(2, 'big'), masked=True), end_stream=True)
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
            },
            'response': {
                'headers': response_headers,
                'text': echoed_text,
                'close_code': close_code,
            },
        }
        negotiation = {
            'implementation': 'python-h2',
            'protocol': 'h2c',
            'settings_enable_connect_protocol': enable_connect,
        }
        _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
        _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
        print(json.dumps(transcript, sort_keys=True))
        status = dict(response_headers).get(':status')
        return 0 if status == '200' and echoed_text == text else 1
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
