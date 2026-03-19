from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _parse_headers(raw: str) -> tuple[str, list[tuple[str, str]]]:
    text = raw.replace('\r\n', '\n')
    blocks = [block for block in text.split('\n\n') if block.strip()]
    if not blocks:
        return '', []
    lines = [line for line in blocks[-1].split('\n') if line.strip()]
    status_line = lines[0] if lines else ''
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if ':' not in line:
            continue
        name, value = line.split(':', 1)
        headers.append((name.strip(), value.strip()))
    return status_line, headers


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
    return parser


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
    url = f'{scheme}://{url_host}:{port}{ns.path}'
    mode = 'http2' if ns.http2 else 'http1'
    body_text = str(ns.body)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        headers_path = tmpdir_path / 'headers.txt'
        body_path = tmpdir_path / 'body.bin'
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
        completed = subprocess.run(command, capture_output=True, text=True, timeout=15.0)
        metadata = json.loads(completed.stdout or '{}') if completed.stdout.strip() else {}
        raw_headers = headers_path.read_text(encoding='utf-8', errors='replace') if headers_path.exists() else ''
        status_line, headers = _parse_headers(raw_headers)
        body = body_path.read_text(encoding='utf-8', errors='replace') if body_path.exists() else ''

    transcript = {
        'request': {
            'method': 'POST',
            'path': ns.path,
            'body': body_text,
            'url': url,
            'server_name': server_name,
        },
        'response': {
            'status': int(metadata.get('response_code') or 0),
            'status_line': status_line,
            'body': body,
            'headers': headers,
        },
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
    }
    _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps(transcript, sort_keys=True))
    return 0 if completed.returncode == 0 and int(metadata.get('response_code') or 0) == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
