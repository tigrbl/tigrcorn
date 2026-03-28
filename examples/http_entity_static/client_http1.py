from __future__ import annotations

import gzip
import socket


def _read_response(sock: socket.socket) -> tuple[bytes, dict[bytes, bytes], bytes]:
    data = bytearray()
    while b'\r\n\r\n' not in data:
        chunk = sock.recv(65535)
        if not chunk:
            break
        data.extend(chunk)
    head, _, rest = bytes(data).partition(b'\r\n\r\n')
    headers: dict[bytes, bytes] = {}
    for line in head.split(b'\r\n')[1:]:
        if not line:
            continue
        name, value = line.split(b':', 1)
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get(b'content-length', b'0'))
    body = rest
    while len(body) < length:
        chunk = sock.recv(65535)
        if not chunk:
            break
        body += chunk
    return head, headers, body[:length]


def main(host: str = '127.0.0.1', port: int = 8000) -> None:
    with socket.create_connection((host, port)) as sock:
        sock.sendall(
            b'GET /hello.txt HTTP/1.1\r\n'
            b'Host: localhost\r\n'
            b'Accept-Encoding: gzip\r\n\r\n'
        )
        head, headers, body = _read_response(sock)
        print(head.decode('latin1'))
        etag = headers.get(b'etag')
        if headers.get(b'content-encoding') == b'gzip':
            body = gzip.decompress(body)
        print(body.decode('utf-8'))
        if etag is None:
            return

    with socket.create_connection((host, port)) as sock:
        sock.sendall(
            b'GET /hello.txt HTTP/1.1\r\n'
            b'Host: localhost\r\n'
            b'If-None-Match: ' + etag + b'\r\n\r\n'
        )
        head, _headers, _body = _read_response(sock)
        print(head.decode('latin1'))

    with socket.create_connection((host, port)) as sock:
        sock.sendall(
            b'GET /hello.txt HTTP/1.1\r\n'
            b'Host: localhost\r\n'
            b'Range: bytes=0-4\r\n\r\n'
        )
        head, _headers, body = _read_response(sock)
        print(head.decode('latin1'))
        print(body.decode('utf-8'))


if __name__ == '__main__':  # pragma: no cover
    main()
