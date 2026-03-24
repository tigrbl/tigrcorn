from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from ._connect_relay_fixture import DeterministicRelayTarget, observed_request_to_json
from ._content_coding_fixture import decode_response_body


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _parse_response_header_sections(raw: str) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]]]:
    text = raw.replace('\r\n', '\n')
    blocks = [block for block in text.split('\n\n') if block.strip()]
    if not blocks:
        return '', [], []
    first_lines = [line for line in blocks[0].split('\n') if line.strip()]
    status_line = first_lines[0] if first_lines else ''
    headers: list[tuple[str, str]] = []
    for line in first_lines[1:]:
        if ':' not in line:
            continue
        name, value = line.split(':', 1)
        headers.append((name.strip(), value.strip()))
    trailers: list[tuple[str, str]] = []
    for block in blocks[1:]:
        for line in [line for line in block.split('\n') if line.strip()]:
            if ':' not in line:
                continue
            name, value = line.split(':', 1)
            trailers.append((name.strip(), value.strip()))
    return status_line, headers, trailers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-curl-client')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--http1', action='store_true')
    group.add_argument('--http2', action='store_true')
    parser.add_argument('--https', action='store_true')
    parser.add_argument('--cacert', default=os.environ.get('INTEROP_CACERT'))
    parser.add_argument('--servername', default=os.environ.get('INTEROP_SERVER_NAME'))
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/interop'))
    parser.add_argument('--body', default=os.environ.get('INTEROP_REQUEST_BODY', 'hello-curl'))
    parser.add_argument('--connect-relay', action='store_true')
    parser.add_argument('--response-trailers', action='store_true')
    parser.add_argument('--content-coding', action='store_true')
    parser.add_argument('--accept-encoding', default=os.environ.get('INTEROP_ACCEPT_ENCODING', 'gzip'))
    return parser


def _run_curl(command: list[str], *, headers_path: Path, body_path: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], str, list[tuple[str, str]], list[tuple[str, str]], bytes]:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=15.0)
    metadata = json.loads(completed.stdout or '{}') if completed.stdout.strip() else {}
    raw_headers = headers_path.read_text(encoding='utf-8', errors='replace') if headers_path.exists() else ''
    status_line, headers, trailers = _parse_response_header_sections(raw_headers)
    body = body_path.read_bytes() if body_path.exists() else b''
    return completed, metadata, status_line, headers, trailers, body



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        completed = subprocess.run(['curl', '--version'], capture_output=True, text=True, timeout=10.0)
        print(completed.stdout.splitlines()[0] if completed.stdout else 'curl (unknown)')
        return completed.returncode

    target_host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    server_name = str(ns.servername or target_host)
    scheme = 'https' if ns.https else 'http'
    url_host = server_name if ns.https else target_host
    mode = 'http2' if ns.http2 else 'http1'
    body_text = str(ns.body)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        headers_path = tmpdir_path / 'headers.txt'
        body_path = tmpdir_path / 'body.bin'
        if ns.connect_relay:
            with DeterministicRelayTarget() as relay_target:
                proxy_url = f'http://{target_host}:{port}'
                url = f'http://{relay_target.authority}{ns.path}'
                command = [
                    'curl',
                    '--silent',
                    '--show-error',
                    '--proxytunnel',
                    '--proxy', proxy_url,
                    '--request', 'POST',
                    '--data', body_text,
                    '--output', str(body_path),
                    '--dump-header', str(headers_path),
                    '--write-out', '%{json}',
                    '--http1.1',
                    url,
                ]
                completed, metadata, status_line, headers, trailers, body = _run_curl(command, headers_path=headers_path, body_path=body_path)
                observed = relay_target.wait_for_request(timeout=5.0)
            transcript = {
                'request': {
                    'mode': 'connect-relay',
                    'method': 'CONNECT',
                    'authority': relay_target.authority,
                    'path': ns.path,
                    'body': body_text,
                    'proxy_url': proxy_url,
                    'url': url,
                    'server_name': server_name,
                },
                'response': {
                    'status': int(metadata.get('response_code') or 0),
                    'status_line': status_line,
                    'body': body.decode('utf-8', errors='replace'),
                    'headers': headers,
                    'trailers': trailers,
                },
                'tunnel': {
                    'connect_status': int(metadata.get('http_connect') or 0),
                    'proxy_used': bool(metadata.get('proxy_used')),
                    'observed_target': observed_request_to_json(observed),
                },
                'curl': metadata,
            }
            negotiation = {
                'implementation': 'curl',
                'http_version': str(metadata.get('http_version') or ''),
                'protocol': 'http/1.1',
                'scheme': str(metadata.get('scheme') or 'http'),
                'curl_version': str(metadata.get('curl_version') or ''),
                'server_name': server_name,
                'connect_tunnel_established': int(metadata.get('http_connect') or 0) == 200,
            }
            _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
            _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
            print(json.dumps(transcript, sort_keys=True))
            return 0 if completed.returncode == 0 and int(metadata.get('http_connect') or 0) == 200 and int(metadata.get('response_code') or 0) == 200 and transcript['response']['body'] == f'echo:{body_text}' else 1

        url = f'{scheme}://{url_host}:{port}{ns.path}'
        command = [
            'curl',
            '--silent',
            '--show-error',
            '--request', 'POST',
            '--data', body_text,
            '--output', str(body_path),
            '--dump-header', str(headers_path),
            '--write-out', '%{json}',
        ]
        if ns.response_trailers or ns.content_coding:
            command = [
                'curl',
                '--silent',
                '--show-error',
                '--request', 'GET',
                '--output', str(body_path),
                '--dump-header', str(headers_path),
                '--write-out', '%{json}',
            ]
        if ns.content_coding:
            command.extend(['--header', f'Accept-Encoding: {ns.accept_encoding}'])
        if mode == 'http2':
            if ns.https:
                command.append('--http2')
            else:
                command.append('--http2-prior-knowledge')
        else:
            command.append('--http1.1')
        if ns.https:
            if ns.cacert:
                command.extend(['--cacert', ns.cacert])
            if server_name != target_host:
                command.extend(['--resolve', f'{server_name}:{port}:{target_host}'])
        command.append(url)
        completed, metadata, status_line, headers, trailers, body = _run_curl(command, headers_path=headers_path, body_path=body_path)

    response_payload = {
        'status': int(metadata.get('response_code') or 0),
        'status_line': status_line,
        'body': body.decode('utf-8', errors='replace') if not ns.content_coding else '',
        'headers': headers,
        'trailers': trailers,
    }
    if ns.content_coding:
        response_payload.update(decode_response_body(headers, body))
    transcript = {
        'request': {
            'method': 'GET' if (ns.response_trailers or ns.content_coding) else 'POST',
            'path': ns.path,
            'body': '' if (ns.response_trailers or ns.content_coding) else body_text,
            'url': url,
            'server_name': server_name,
            'accept_encoding': ns.accept_encoding if ns.content_coding else None,
        },
        'response': response_payload,
        'curl': metadata,
    }
    http_version = str(metadata.get('http_version') or '')
    protocol = 'http/1.1'
    if http_version.startswith('2'):
        protocol = 'h2' if scheme == 'https' else 'h2c'
    negotiation = {
        'implementation': 'curl',
        'http_version': http_version,
        'protocol': protocol,
        'scheme': str(metadata.get('scheme') or scheme),
        'curl_version': str(metadata.get('curl_version') or ''),
        'server_name': server_name,
        'response_trailers_mode': bool(ns.response_trailers),
        'content_coding_mode': bool(ns.content_coding),
    }
    _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps(transcript, sort_keys=True))
    if ns.response_trailers:
        success = completed.returncode == 0 and int(metadata.get('response_code') or 0) == 200 and response_payload['body'] == 'ok' and ('x-trailer-one', 'yes') in trailers and ('x-trailer-two', 'done') in trailers
        return 0 if success else 1
    if ns.content_coding:
        vary = (response_payload.get('vary') or '').lower()
        success = completed.returncode == 0 and int(metadata.get('response_code') or 0) == 200 and response_payload.get('content_encoding') == 'gzip' and 'accept-encoding' in vary and response_payload.get('decoded_body') == 'compress-me'
        return 0 if success else 1
    return 0 if completed.returncode == 0 and int(metadata.get('response_code') or 0) == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
