from __future__ import annotations

import socket


def main(host: str = '127.0.0.1', port: int = 8000) -> None:
    with socket.create_connection((host, port)) as sock:
        sock.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = sock.recv(65535)
        print(response.decode('latin1'))


if __name__ == '__main__':  # pragma: no cover
    main()
