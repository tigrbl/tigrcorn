from __future__ import annotations

import socket


def configure_socket(sock, *, nodelay: bool = True) -> None:
    if sock is None:
        return
    if nodelay and sock.family in {socket.AF_INET, socket.AF_INET6} and sock.type == socket.SOCK_STREAM:
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
