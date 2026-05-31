from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value)


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp_path.replace(path)


def header_pairs_to_text(headers: Iterable[tuple[bytes, bytes]]) -> list[list[str]]:
    pairs: list[list[str]] = []
    for raw_name, raw_value in headers:
        pairs.append([
            raw_name.decode('latin1', errors='replace'),
            raw_value.decode('latin1', errors='replace'),
        ])
    return pairs


def first_header_value(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> str | None:
    needle = name.lower()
    for raw_name, raw_value in headers:
        if raw_name.lower() == needle:
            return raw_value.decode('latin1', errors='replace')
    return None


class WebSocketInteropCapture:
    def __init__(
        self,
        *,
        protocol: str,
        path: str,
        request_headers: Iterable[tuple[bytes, bytes]],
        scheme: str,
        compression_config: str,
        compression_requested: str,
        connect_protocol_enabled: bool,
    ) -> None:
        self.transcript_path = _env_path('INTEROP_TRANSCRIPT_PATH')
        self.negotiation_path = _env_path('INTEROP_NEGOTIATION_PATH')
        self.enabled = self.transcript_path is not None or self.negotiation_path is not None
        request_header_pairs = list(request_headers)
        authority = first_header_value(request_header_pairs, b':authority') or first_header_value(request_header_pairs, b'host') or ''
        self.transcript: dict[str, Any] = {
            'request': {
                'path': path,
                'scheme': scheme,
                'authority': authority,
                'headers': header_pairs_to_text(request_header_pairs),
                'compression': compression_requested,
                'text': None,
                'bytes_length': None,
                'close_code': None,
                'close_reason': None,
            },
            'response': {
                'status': None,
                'headers': [],
                'subprotocol': None,
                'extension_header': '',
                'text': None,
                'bytes_length': None,
                'close_code': None,
                'close_reason': None,
            },
        }
        self.negotiation: dict[str, Any] = {
            'implementation': 'tigrcorn',
            'protocol': protocol,
            'scheme': scheme,
            'path': path,
            'server_name': authority,
            'handshake_complete': False,
            'connect_protocol_enabled': connect_protocol_enabled,
            'compression_configured': compression_config,
            'compression_requested': compression_requested,
            'permessage_deflate_offered': compression_requested == 'permessage-deflate',
            'negotiated_extensions': [],
            'response_extension_header': '',
            'response_subprotocol': None,
            'response_status': None,
        }

    def _flush(self) -> None:
        if not self.enabled:
            return
        _write_json(self.transcript_path, self.transcript)
        _write_json(self.negotiation_path, self.negotiation)

    def record_accept(
        self,
        *,
        status: int,
        response_headers: Iterable[tuple[bytes, bytes]],
        negotiated_extensions: list[str],
        selected_subprotocol: str | None,
    ) -> None:
        header_pairs = list(response_headers)
        extension_header = first_header_value(header_pairs, b'sec-websocket-extensions') or ''
        self.transcript['response']['status'] = int(status)
        self.transcript['response']['headers'] = header_pairs_to_text(header_pairs)
        self.transcript['response']['subprotocol'] = selected_subprotocol
        self.transcript['response']['extension_header'] = extension_header
        self.negotiation['handshake_complete'] = True
        self.negotiation['response_status'] = int(status)
        self.negotiation['negotiated_extensions'] = list(negotiated_extensions)
        self.negotiation['response_extension_header'] = extension_header
        self.negotiation['response_subprotocol'] = selected_subprotocol
        self._flush()

    def record_denial(self, *, status: int, response_headers: Iterable[tuple[bytes, bytes]]) -> None:
        header_pairs = list(response_headers)
        self.transcript['response']['status'] = int(status)
        self.transcript['response']['headers'] = header_pairs_to_text(header_pairs)
        self.negotiation['handshake_complete'] = False
        self.negotiation['response_status'] = int(status)
        self.negotiation['negotiated_extensions'] = []
        self.negotiation['response_extension_header'] = ''
        self.negotiation['response_subprotocol'] = None
        self._flush()

    def record_request_text(self, text: str) -> None:
        self.transcript['request']['text'] = text
        self.transcript['request']['bytes_length'] = len(text.encode('utf-8'))
        self._flush()

    def record_request_bytes(self, data: bytes) -> None:
        self.transcript['request']['bytes_length'] = len(data)
        self._flush()

    def record_response_text(self, text: str) -> None:
        self.transcript['response']['text'] = text
        self.transcript['response']['bytes_length'] = len(text.encode('utf-8'))
        self._flush()

    def record_response_bytes(self, data: bytes) -> None:
        self.transcript['response']['bytes_length'] = len(data)
        self._flush()

    def record_request_close(self, code: int, reason: str) -> None:
        self.transcript['request']['close_code'] = int(code)
        self.transcript['request']['close_reason'] = reason
        self._flush()

    def record_response_close(self, code: int, reason: str) -> None:
        self.transcript['response']['close_code'] = int(code)
        self.transcript['response']['close_reason'] = reason
        self._flush()

    def record_disconnect(self, code: int, reason: str) -> None:
        if self.transcript['response']['close_code'] is None:
            self.record_response_close(code, reason)
        else:
            self._flush()
