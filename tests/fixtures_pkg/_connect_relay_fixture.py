from __future__ import annotations

import json
import socketserver
import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ObservedRelayRequest:
    method: str
    path: str
    headers: list[tuple[str, str]]
    body: bytes
    raw_request: bytes

    def to_json(self) -> dict[str, Any]:
        return {
            'method': self.method,
            'path': self.path,
            'headers': list(self.headers),
            'body': self.body.decode('utf-8', errors='replace'),
            'raw_request': self.raw_request.decode('utf-8', errors='replace'),
        }


@dataclass(slots=True)
class ParsedHTTPResponse:
    status: int
    status_line: str
    headers: list[tuple[str, str]]
    body: bytes

    def to_json(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'status_line': self.status_line,
            'headers': list(self.headers),
            'body': self.body.decode('utf-8', errors='replace'),
        }


class _ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class DeterministicRelayTarget(AbstractContextManager['DeterministicRelayTarget']):
    def __init__(self, *, host: str = '127.0.0.1') -> None:
        self.host = host
        self._observed: list[ObservedRelayRequest] = []
        self._observed_event = threading.Event()

        outer = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:  # pragma: no cover - exercised via wrappers/tests
                raw = bytearray()
                while b'\r\n\r\n' not in raw:
                    chunk = self.request.recv(65535)
                    if not chunk:
                        break
                    raw.extend(chunk)
                if b'\r\n\r\n' in raw:
                    head, remainder = bytes(raw).split(b'\r\n\r\n', 1)
                else:
                    head = bytes(raw)
                    remainder = b''
                lines = head.decode('iso-8859-1', errors='replace').split('\r\n') if head else []
                request_line = lines[0] if lines else ''
                parts = request_line.split(' ')
                method = parts[0] if len(parts) >= 1 else ''
                path = parts[1] if len(parts) >= 2 else ''
                headers: list[tuple[str, str]] = []
                content_length = 0
                for line in lines[1:]:
                    if ':' not in line:
                        continue
                    name, value = line.split(':', 1)
                    name = name.strip()
                    value = value.strip()
                    headers.append((name, value))
                    if name.lower() == 'content-length':
                        try:
                            content_length = int(value)
                        except ValueError:
                            content_length = 0
                body = bytearray(remainder)
                while len(body) < content_length:
                    chunk = self.request.recv(65535)
                    if not chunk:
                        break
                    body.extend(chunk)
                response_body = b'echo:' + bytes(body)
                response = (
                    b'HTTP/1.1 200 OK\r\n'
                    + b'Content-Type: text/plain\r\n'
                    + f'Content-Length: {len(response_body)}\r\n'.encode('ascii')
                    + b'Connection: close\r\n'
                    + b'X-Tunnel-Echo: deterministic\r\n\r\n'
                    + response_body
                )
                self.request.sendall(response)
                outer._observed.append(
                    ObservedRelayRequest(
                        method=method,
                        path=path,
                        headers=headers,
                        body=bytes(body),
                        raw_request=bytes(raw) + bytes(body[len(remainder):]),
                    )
                )
                outer._observed_event.set()

        self._server = _ThreadingTCPServer((self.host, 0), Handler)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, name='deterministic-relay-target', daemon=True)

    @property
    def authority(self) -> str:
        return f'{self.host}:{self.port}'

    @property
    def url(self) -> str:
        return f'http://{self.authority}/relay'

    def __enter__(self) -> 'DeterministicRelayTarget':
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
        return None

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)

    def wait_for_request(self, timeout: float = 5.0) -> ObservedRelayRequest | None:
        if not self._observed_event.wait(timeout):
            return None
        return self._observed[-1] if self._observed else None


def build_tunneled_http_request(*, path: str, body: bytes, host_header: str = 'relay.local') -> bytes:
    return (
        f'POST {path} HTTP/1.1\r\n'.encode('ascii')
        + f'Host: {host_header}\r\n'.encode('ascii')
        + f'Content-Length: {len(body)}\r\n'.encode('ascii')
        + b'Connection: close\r\n\r\n'
        + body
    )


def parse_tunneled_http_response(payload: bytes) -> ParsedHTTPResponse:
    head, _, remainder = payload.partition(b'\r\n\r\n')
    lines = head.decode('iso-8859-1', errors='replace').split('\r\n') if head else []
    status_line = lines[0] if lines else ''
    status = 0
    if status_line:
        parts = status_line.split(' ')
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
    headers: list[tuple[str, str]] = []
    content_length = None
    for line in lines[1:]:
        if ':' not in line:
            continue
        name, value = line.split(':', 1)
        name = name.strip()
        value = value.strip()
        headers.append((name, value))
        if name.lower() == 'content-length':
            try:
                content_length = int(value)
            except ValueError:
                content_length = None
    body = remainder
    if content_length is not None:
        body = body[:content_length]
    return ParsedHTTPResponse(status=status, status_line=status_line, headers=headers, body=body)


def observed_request_to_json(observed: ObservedRelayRequest | None) -> dict[str, Any] | None:
    return None if observed is None else observed.to_json()


def parsed_response_to_json(response: ParsedHTTPResponse) -> dict[str, Any]:
    return response.to_json()
