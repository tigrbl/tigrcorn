from __future__ import annotations

import socket


def _read_response(sock: socket.socket, *, initial: bytes = b'') -> tuple[bytes, dict[bytes, bytes], bytes, bytes]:
    data = bytearray(initial)
    while b'\r\n\r\n' not in data:
        chunk = sock.recv(65535)
        if not chunk:
            break
        data.extend(chunk)
    head, _sep, rest = bytes(data).partition(b'\r\n\r\n')
    head = head + b'\r\n\r\n'
    headers: dict[bytes, bytes] = {}
    for line in head.split(b'\r\n')[1:]:
        if not line:
            continue
        name, value = line.split(b':', 1)
        headers[name.strip().lower()] = value.strip()
    body = bytearray(rest)
    length = int(headers.get(b'content-length', b'0'))
    while len(body) < length:
        chunk = sock.recv(65535)
        if not chunk:
            break
        body.extend(chunk)
    return head, headers, bytes(body[:length]), bytes(body[length:])


def main(host: str = '127.0.0.1', port: int = 8000) -> None:
    with socket.create_connection((host, port)) as sock:
        sock.sendall(b'GET /early-hints HTTP/1.1\r\nHost: localhost\r\n\r\n')
        interim, _headers, _body, rest = _read_response(sock)
        print(interim.decode('latin1'))
        head, headers, body, _rest = _read_response(sock, initial=rest)
        print(head.decode('latin1'))
        print('alt-svc:', headers.get(b'alt-svc'))
        print(body.decode('utf-8'))

    with socket.create_connection((host, port)) as sock:
        sock.sendall(
            b'GET /static/app.js HTTP/1.1\r\n'
            b'Host: localhost\r\n'
            b'Accept-Encoding: gzip, br\r\n\r\n'
        )
        head, headers, body, _rest = _read_response(sock)
        print(head.decode('latin1'))
        print('content-encoding:', headers.get(b'content-encoding'))
        print('body-bytes:', len(body))


if __name__ == '__main__':  # pragma: no cover
    main()
