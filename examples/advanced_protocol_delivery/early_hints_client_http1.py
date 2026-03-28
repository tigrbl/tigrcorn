from __future__ import annotations

import socket


def _read_head(sock: socket.socket) -> bytes:
    data = bytearray()
    while b'\r\n\r\n' not in data:
        chunk = sock.recv(65535)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def main(host: str = '127.0.0.1', port: int = 8000) -> None:
    with socket.create_connection((host, port)) as sock:
        sock.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        interim = _read_head(sock)
        print('--- interim ---')
        print(interim.decode('latin1'))
        final_head = _read_head(sock)
        print('--- final ---')
        print(final_head.decode('latin1'))


if __name__ == '__main__':  # pragma: no cover
    main()
