from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import websockets


def _write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='external-websocket-client')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--path', default=os.environ.get('INTEROP_REQUEST_PATH', '/ws'))
    parser.add_argument('--text', default=os.environ.get('INTEROP_REQUEST_BODY', 'hello-websocket'))
    parser.add_argument('--compression', default=os.environ.get('INTEROP_WEBSOCKET_COMPRESSION', 'off'))
    return parser


async def _run(path: str, text: str, *, compression: str) -> int:
    host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    url = f'ws://{host}:{port}{path}'
    compression_arg = 'deflate' if compression == 'permessage-deflate' else None
    async with websockets.connect(url, compression=compression_arg) as websocket:
        await websocket.send(text)
        received = await websocket.recv()
        response = getattr(websocket, 'response', None)
        headers = response.headers if response is not None else websocket.response_headers
        protocol = getattr(websocket, 'protocol', websocket)
        extension_header = headers.get('Sec-WebSocket-Extensions', '')
        response_headers = list(headers.raw_items())
        negotiated_extensions = [type(extension).__name__ for extension in protocol.extensions]
        await websocket.close()
        transcript = {
            'request': {'path': path, 'text': text, 'url': url, 'compression': compression},
            'response': {
                'text': received,
                'headers': response_headers,
                'extension_header': extension_header,
            },
        }
        negotiation = {
            'implementation': 'websockets',
            'subprotocol': websocket.subprotocol,
            'compression_requested': compression,
            'negotiated_extensions': negotiated_extensions,
            'response_extension_header': extension_header,
            'close_code': websocket.close_code,
        }
        _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
        _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
        print(json.dumps({'transcript': transcript, 'negotiation': negotiation}, sort_keys=True))
        return 0 if received == text else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv or sys.argv[1:])
    if ns.version:
        print(f'websockets {websockets.__version__}')
        return 0
    return asyncio.run(_run(ns.path, ns.text, compression=str(ns.compression)))


if __name__ == '__main__':
    raise SystemExit(main())
