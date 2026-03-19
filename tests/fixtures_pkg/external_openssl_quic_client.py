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
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '
', encoding='utf-8')


def _extract(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-openssl-quic-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--cafile', default='tests/fixtures_certs/interop-localhost-cert.pem')
    parser.add_argument('--servername', default='localhost')
    parser.add_argument('--alpn', default='h3')
    parser.add_argument('--client-cert', default=os.environ.get('INTEROP_CLIENT_CERT'))
    parser.add_argument('--client-key', default=os.environ.get('INTEROP_CLIENT_KEY'))
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
        '-quic',
        '-alpn', ns.alpn,
        '-servername', ns.servername,
        '-CAfile', ns.cafile,
        '-verify_return_error',
    ]
    if ns.client_cert:
        command.extend(['-cert', ns.client_cert])
    if ns.client_key:
        command.extend(['-key', ns.client_key])
    completed = subprocess.run(command, input='', capture_output=True, text=True, timeout=20.0)
    stdout = completed.stdout
    stderr = completed.stderr
    transcript = {
        'command': command,
        'return_code': completed.returncode,
        'subject': _extract(r'^subject=(.+)$', stdout),
        'issuer': _extract(r'^issuer=(.+)$', stdout),
        'connected': 'CONNECTED(' in stdout,
        'client_auth_requested': 'Acceptable client certificate CA names' in stdout or 'CertificateRequest' in stderr,
        'client_certificate_supplied': bool(ns.client_cert and ns.client_key),
        'stderr': stderr,
    }
    verify_code_raw = _extract(r'^\s*Verify return code:\s*(\d+)', stdout)
    negotiation = {
        'implementation': 'openssl',
        'protocol': _extract(r'^Protocol:\s*(.+)$', stdout) or _extract(r'^Protocol version:\s*(.+)$', stderr),
        'tls_version': _extract(r'^(?:New,\s*)?(TLSv1\.3)', stdout),
        'cipher': _extract(r'^\s*Cipher(?: is)?\s*:?\s*(.+)$', stdout) or _extract(r'^Ciphersuite:\s*(.+)$', stderr),
        'alpn': _extract(r'^ALPN protocol:\s*(.+)$', stdout),
        'peer_temp_key': _extract(r'^Peer Temp Key:\s*(.+)$', stdout) or _extract(r'^Peer Temp Key:\s*(.+)$', stderr),
        'peer_signature_type': _extract(r'^Peer signature type:\s*(.+)$', stdout),
        'verification': 'OK' if 'Verification: OK' in stderr or 'Verify return code: 0 (ok)' in stdout else 'FAILED',
        'verify_return_code': int(verify_code_raw) if verify_code_raw is not None else None,
        'client_auth_present': bool(ns.client_cert and ns.client_key),
    }
    _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps({'transcript': transcript, 'negotiation': negotiation}, sort_keys=True))
    return 0 if completed.returncode == 0 and negotiation['verification'] == 'OK' else 1


if __name__ == '__main__':
    raise SystemExit(main())
