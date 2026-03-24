from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _status_line_and_headers(stdout: str) -> tuple[str, list[tuple[str, str]], str]:
    text = stdout.replace('\r\n', '\n')
    index = text.find('HTTP/')
    if index < 0:
        return '', [], stdout
    body_and_head = text[index:]
    split = body_and_head.split('\n\n', 1)
    header_block = split[0]
    body = split[1] if len(split) == 2 else ''
    lines = [line for line in header_block.split('\n') if line.strip()]
    if not lines:
        return '', [], body
    status_line = lines[0]
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if ':' not in line:
            continue
        name, value = line.split(':', 1)
        headers.append((name.strip(), value.strip()))
    return status_line, headers, body


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-openssl-tls-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--cafile', default=os.environ.get('INTEROP_CAFILE'))
    parser.add_argument('--servername', default=os.environ.get('INTEROP_SERVER_NAME', 'localhost'))
    parser.add_argument('--client-cert', default=os.environ.get('INTEROP_CLIENT_CERT'))
    parser.add_argument('--client-key', default=os.environ.get('INTEROP_CLIENT_KEY'))
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/interop'))
    parser.add_argument('--alpn', default=os.environ.get('INTEROP_ALPN', 'http/1.1'))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        completed = subprocess.run(['openssl', 'version'], capture_output=True, text=True, timeout=10.0)
        print(completed.stdout.strip() or completed.stderr.strip())
        return completed.returncode

    host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    command = [
        'openssl', 's_client',
        '-connect', f'{host}:{port}',
        '-servername', ns.servername,
        '-CAfile', ns.cafile,
        '-verify_return_error',
        '-alpn', ns.alpn,
        '-quiet',
    ]
    if ns.client_cert:
        command.extend(['-cert', ns.client_cert])
    if ns.client_key:
        command.extend(['-key', ns.client_key])
    request = f'GET {ns.path} HTTP/1.1\r\nHost: {ns.servername}\r\nConnection: close\r\n\r\n'
    completed = subprocess.run(command, input=request, capture_output=True, text=True, timeout=20.0)
    status_line, headers, body = _status_line_and_headers(completed.stdout)
    status_match = re.search(r'HTTP/\d\.\d\s+(\d{3})', status_line)
    verification_ok = completed.returncode == 0 and 'verify error' not in completed.stderr.lower() and 'certificate verify failed' not in completed.stderr.lower()
    transcript = {
        'command': command,
        'return_code': completed.returncode,
        'request': {
            'method': 'GET',
            'path': ns.path,
        },
        'response': {
            'status_line': status_line,
            'status': int(status_match.group(1)) if status_match else 0,
            'headers': headers,
            'body': body,
        },
        'handshake_established': bool(status_line),
        'stderr': completed.stderr,
    }
    verify_code_match = re.search(r'Verification: (.+)', completed.stderr)
    negotiation = {
        'implementation': 'openssl',
        'protocol': 'tls',
        'alpn': ns.alpn,
        'tls_version': 'TLSv1.3' if ('TLSv1.3' in completed.stderr or 'TLSv1.3' in completed.stdout) else None,
        'verification': 'OK' if verification_ok else 'FAILED',
        'verification_detail': verify_code_match.group(1).strip() if verify_code_match else None,
        'client_auth_present': bool(ns.client_cert and ns.client_key),
    }
    _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps({'transcript': transcript, 'negotiation': negotiation}, sort_keys=True))
    return 0 if verification_ok and transcript['response']['status'] == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
